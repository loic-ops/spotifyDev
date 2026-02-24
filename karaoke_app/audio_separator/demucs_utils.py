import os
import subprocess
import tempfile
import warnings
warnings.filterwarnings('ignore')

import numpy as np
import torch
from demucs.pretrained import get_model
from demucs.apply import apply_model


def _load_audio_as_tensor(input_path, target_sr=44100, target_channels=2):
    """
    Load any audio file as a torch float32 tensor using ffmpeg + scipy.
    This avoids torchaudio backend issues entirely.

    Returns:
        (tensor [channels, samples], sample_rate)
    """
    from scipy.io import wavfile

    # Convert to WAV with exact specs via ffmpeg
    tmp = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
    tmp.close()

    cmd = [
        'ffmpeg', '-y', '-i', input_path,
        '-ar', str(target_sr),
        '-ac', str(target_channels),
        '-sample_fmt', 's16',   # 16-bit signed int
        '-f', 'wav',
        tmp.name
    ]

    print(f"[demucs] Converting audio: {input_path}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        os.unlink(tmp.name)
        raise RuntimeError(f"ffmpeg conversion failed:\n{result.stderr}")

    try:
        sr, data = wavfile.read(tmp.name)
    finally:
        os.unlink(tmp.name)

    print(f"[demucs] Loaded: sr={sr}, shape={data.shape}, dtype={data.dtype}")

    # data shape: (samples,) for mono or (samples, channels) for stereo
    if data.ndim == 1:
        data = data[:, np.newaxis]  # (samples, 1)

    # Convert int16 → float32 in [-1, 1] range
    audio = data.astype(np.float32) / 32768.0

    # Transpose to (channels, samples) for torch
    tensor = torch.from_numpy(audio.T)

    return tensor, sr


def separate_audio_demucs(input_path, output_dir, model_name='htdemucs'):
    """
    Separate audio into vocals and instrumental using Demucs 4.x

    Args:
        input_path: Path to input audio file
        output_dir: Directory to save separated files
        model_name: Demucs model name

    Returns:
        Dictionary with paths to separated files
    """
    from scipy.io import wavfile

    os.makedirs(output_dir, exist_ok=True)

    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    print(f"[demucs] Using device: {device}")

    # Load pretrained model
    print(f"[demucs] Loading model: {model_name}...")
    model = get_model(model_name)
    model.to(device)
    model.eval()

    # Load audio via ffmpeg+scipy (bypasses torchaudio backend issues)
    wav, sr = _load_audio_as_tensor(
        input_path,
        target_sr=model.samplerate,
        target_channels=model.audio_channels
    )
    print(f"[demucs] Audio tensor: shape={wav.shape}, sr={sr}")

    # Apply separation
    print("[demucs] Separating audio (this takes a while)...")
    with torch.no_grad():
        sources = apply_model(model, wav[None].to(device))

    # sources shape: [1, num_sources, channels, samples]
    # Default htdemucs sources: drums, bass, other, vocals
    source_names = model.sources  # e.g. ['drums', 'bass', 'other', 'vocals']
    print(f"[demucs] Sources: {source_names}")

    output_files = {}
    for idx, name in enumerate(source_names):
        source_audio = sources[0, idx].cpu().numpy()

        # Convert float32 to int16
        source_audio = (source_audio * 32767).clip(-32768, 32767).astype(np.int16)

        output_path = os.path.join(output_dir, f'{name}.wav')
        wavfile.write(output_path, model.samplerate, source_audio.T)

        output_files[name] = output_path
        print(f"[demucs] Saved: {output_path}")

    # Create instrumental = everything except vocals
    vocals_idx = source_names.index('vocals') if 'vocals' in source_names else -1
    if vocals_idx >= 0:
        instrumental = sum(
            sources[0, i] for i in range(len(source_names)) if i != vocals_idx
        ).cpu().numpy()
    else:
        instrumental = sources[0, 0].cpu().numpy()

    instrumental = (instrumental * 32767).clip(-32768, 32767).astype(np.int16)
    instrumental_path = os.path.join(output_dir, 'instrumental.wav')
    wavfile.write(instrumental_path, model.samplerate, instrumental.T)
    print(f"[demucs] Saved: {instrumental_path}")

    print("[demucs] Separation complete!")
    return {
        'vocals': output_files.get('vocals'),
        'instrumental': instrumental_path,
        'drums': output_files.get('drums'),
        'bass': output_files.get('bass'),
        'other': output_files.get('other')
    }


def get_demucs_models():
    """Get available Demucs models"""
    return {
        'htdemucs': 'Hybrid Transformer Demucs (default, best quality)',
        'htdemucs_ft': 'Hybrid Transformer Demucs (fine-tuned)',
        'mdx': 'MDX (Neural Network)',
        'mdx_extra': 'MDX with extra sources',
    }
