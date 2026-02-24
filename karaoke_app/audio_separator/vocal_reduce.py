import numpy as np
import warnings
warnings.filterwarnings('ignore')

from pydub import AudioSegment
from scipy import signal
import io


def reduce_vocal(input_path, instrumental_path, output_path, reduction_level=0.5):
    """
    Reduce vocals in original track by combining:
    1. Phase cancellation technique
    2. Mixing with instrumental track
    
    Args:
        input_path: Path to original audio file
        instrumental_path: Path to instrumental track
        output_path: Path to save reduced vocal audio
        reduction_level: 0.0 (no reduction) to 1.0 (maximum reduction)
    """
    print(f"Reducing vocals with level: {reduction_level}")
    
    # Load audio files
    original = AudioSegment.from_file(input_path)
    instrumental = AudioSegment.from_file(instrumental_path)
    
    # Match duration (take shorter)
    min_duration = min(len(original), len(instrumental))
    original = original[:min_duration]
    instrumental = instrumental[:min_duration]
    
    # Convert to numpy arrays
    original_np = np.array(original.get_array_of_samples())
    instrumental_np = np.array(instrumental.get_array_of_samples())
    
    # Handle stereo
    if original.channels == 2:
        original_left = original_np[::2]
        original_right = original_np[1::2]
    else:
        original_left = original_np
        original_right = original_np
    
    if instrumental.channels == 2:
        instrumental_left = instrumental_np[::2]
        instrumental_right = instrumental_np[1::2]
    else:
        instrumental_left = instrumental_np
        instrumental_right = instrumental_np
    
    # Apply phase cancellation to original
    # This works by inverting one channel and adding - helps remove center-panned vocals
    reduced_left, reduced_right = apply_phase_cancellation(
        original_left, original_right, reduction_level
    )
    
    # Mix with instrumental (adjustable ratio)
    # More instrumental = less vocals audible
    instrumental_ratio = 0.3 + (reduction_level * 0.4)  # 0.3 to 0.7
    vocal_ratio = 1.0 - instrumental_ratio
    
    # Mix the reduced vocals with instrumental
    final_left = (reduced_left * vocal_ratio + instrumental_left * instrumental_ratio).astype(np.int16)
    final_right = (reduced_right * vocal_ratio + instrumental_right * instrumental_ratio).astype(np.int16)
    
    # Interleave for stereo
    if original.channels == 2:
        final_audio = np.empty((len(final_left) * 2,), dtype=np.int16)
        final_audio[::2] = final_left
        final_audio[1::2] = final_right
    else:
        final_audio = final_left
    
    # Export as WAV
    from scipy.io import wavfile
    wavfile.write(
        output_path, 
        original.frame_rate, 
        final_audio
    )
    
    print(f"Saved reduced vocal audio to: {output_path}")
    return output_path


def apply_phase_cancellation(left_channel, right_channel, strength):
    """
    Apply phase cancellation to reduce center-panned vocals
    
    This technique works because:
    - Many vocals are centered (equal in both channels)
    - Instruments are often stereo/panned
    - By subtracting channels, center content gets cancelled
    """
    # Normalize to float
    left = left_channel.astype(np.float64)
    right = right_channel.astype(np.float64)
    
    # Calculate center (mono) and side
    center = (left + right) / 2
    side = (left - right) / 2
    
    # Reduce center component (where vocals usually are)
    reduced_center = center * (1 - strength * 0.8)  # Don't completely remove
    
    # Reconstruct
    new_left = reduced_center + side
    new_right = reduced_center - side
    
    return new_left.astype(np.int16), new_right.astype(np.int16)


def create_karaoke_track(original_path, instrumental_path, output_path, vocal_volume=0.1):
    """
    Create karaoke track by mixing original (reduced vocals) with instrumental
    
    Args:
        original_path: Path to original audio
        instrumental_path: Path to instrumental only
        output_path: Path to save karaoke track
        vocal_volume: Volume of original vocals (0.0 to 1.0)
    """
    original = AudioSegment.from_file(original_path)
    instrumental = AudioSegment.from_file(instrumental_path)
    
    # Match duration
    min_duration = min(len(original), len(instrumental))
    original = original[:min_duration]
    instrumental = instrumental[:min_duration]
    
    # Reduce original volume and apply low-pass filter to reduce vocal clarity
    original_reduced = original - 20  # Reduce by 20dB
    original_reduced = original_reduced.apply_gain(-20 * (1 - vocal_volume))
    
    # Mix with instrumental
    # Instrumental at 80%, original (reduced) at 20%
    karaoke = instrumental.overlay(original_reduced, position=0)
    
    # Export
    karaoke.export(output_path, format='wav')
    
    return output_path

