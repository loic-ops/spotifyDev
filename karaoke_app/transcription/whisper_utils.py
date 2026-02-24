import warnings
warnings.filterwarnings('ignore')

import whisper
import numpy as np
import torch


# Load Whisper model (cached after first load)
_model = None


def get_model(model_name='base'):
    """Get or load Whisper model"""
    global _model
    if _model is None:
        print(f"Loading Whisper model: {model_name}")
        _model = whisper.load_model(model_name)
    return _model


def transcribe_audio(audio_path, model_name='base', language=None):
    """
    Transcribe audio to text with timestamps using Whisper
    
    Args:
        audio_path: Path to audio file (wav, mp3, etc.)
        model_name: Whisper model size ('tiny', 'base', 'small', 'medium', 'large')
        language: Language code (None for auto-detect)
    
    Returns:
        Dictionary with 'text' and 'segments'
    """
    model = get_model(model_name)
    
    print(f"Transcribing: {audio_path}")
    
    # Run transcription
    if language:
        result = model.transcribe(
            audio_path, 
            language=language,
            word_timestamps=True,
            verbose=False
        )
    else:
        result = model.transcribe(
            audio_path,
            word_timestamps=True,
            verbose=False
        )
    
    # Extract text and segments with timestamps
    transcription = {
        'text': result['text'].strip(),
        'segments': []
    }
    
    # Process segments
    for segment in result['segments']:
        transcription['segments'].append({
            'start': segment['start'],
            'end': segment['end'],
            'text': segment['text'].strip(),
            'words': segment.get('words', [])
        })
    
    print(f"Transcription complete: {len(transcription['text'])} characters")
    
    return transcription


def transcribe_vocals_to_lrc(audio_path, model_name='base'):
    """
    Transcribe vocals and return LRC format directly
    
    Returns:
        LRC formatted string
    """
    result = transcribe_audio(audio_path, model_name)
    return create_lrc(result['segments'])


def create_lrc(segments):
    """
    Create LRC (Lyric) format from Whisper segments
    
    LRC format: [mm:ss.xx] lyrics text
    """
    lrc_lines = []
    
    for segment in segments:
        start_time = segment['start']
        text = segment['text']
        
        # Convert to LRC time format [mm:ss.xx]
        minutes = int(start_time // 60)
        seconds = int(start_time % 60)
        hundredths = int((start_time % 1) * 100)
        
        time_str = f"[{minutes:02d}:{seconds:02d}.{hundredths:02d}]"
        lrc_lines.append(f"{time_str}{text}")
    
    return '\n'.join(lrc_lines)


def get_available_models():
    """Get list of available Whisper models"""
    return {
        'tiny': '39M - fastest, lowest accuracy',
        'base': '74M - fast, good accuracy',
        'small': '244M - moderate speed, better accuracy',
        'medium': '769M - slow, high accuracy',
        'large': '1550M - slowest, highest accuracy'
    }

