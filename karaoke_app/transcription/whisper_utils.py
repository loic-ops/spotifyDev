# transcription audio via faster-whisper (CTranslate2)
import warnings
warnings.filterwarnings('ignore')

import logging
from faster_whisper import WhisperModel

log = logging.getLogger('karaoking')

_model = None
_model_name = None


def get_model(name='base'):
    global _model, _model_name
    if _model is not None and _model_name == name:
        return _model

    print(f"[whisper] Loading model: {name} (faster-whisper)")
    _model = WhisperModel(name, device="cpu", compute_type="int8")
    _model_name = name
    return _model


def transcribe_audio(audio_path, model_name='base', language=None):
    mdl = get_model(model_name)
    print(f"[whisper] Transcribing: {audio_path}")

    kw = {
        'beam_size': 5,
        'word_timestamps': True,
        'vad_filter': True,
        'vad_parameters': dict(min_silence_duration_ms=500),
    }
    if language:
        kw['language'] = language

    segs_iter, info = mdl.transcribe(audio_path, **kw)
    segs = list(segs_iter)
    print(f"[whisper] Detected language: {info.language} (prob {info.language_probability:.2f})")

    out = {'text': ' '.join(s.text.strip() for s in segs), 'segments': []}

    for s in segs:
        out['segments'].append({
            'start': s.start, 'end': s.end,
            'text': s.text.strip(),
            'words': [{'word': w.word, 'start': w.start, 'end': w.end, 'probability': w.probability}
                      for w in (s.words or [])]
        })

    print(f"[whisper] Transcription complete: {len(out['text'])} chars, {len(out['segments'])} segments")
    return out


def transcribe_vocals_to_lrc(audio_path, model_name='base'):
    result = transcribe_audio(audio_path, model_name)
    return create_lrc(result['segments'])


def create_lrc(segments):
    lines = []
    for seg in segments:
        t = seg['start']
        mins = int(t // 60)
        secs = int(t % 60)
        hs = int((t % 1) * 100)
        lines.append(f"[{mins:02d}:{secs:02d}.{hs:02d}]{seg['text']}")
    return '\n'.join(lines)


def get_available_models():
    return {
        'tiny': '39M - fastest, lowest accuracy',
        'base': '74M - fast, good accuracy',
        'small': '244M - moderate speed, better accuracy',
        'medium': '769M - slow, high accuracy',
        'large': '1550M - slowest, highest accuracy',
    }
