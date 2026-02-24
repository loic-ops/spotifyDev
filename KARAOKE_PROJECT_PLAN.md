# Karaoke System Project Plan

## Project Overview
A web-based karaoke system built with Python (Flask) that allows users to upload songs, separate vocals from instrumentals using AI, transcribe lyrics with Whisper, and display synchronized scrolling lyrics like Spotify with voice reduction capabilities.

## Technology Stack
- **Backend**: Flask (Python)
- **Audio Separation**: Spleeter & Demucs
- **Speech-to-Text**: Whisper (OpenAI)
- **Frontend**: HTML/CSS/JavaScript
- **Database**: SQLite (for storing songs/metadata)

## Architecture

### Directory Structure
```
karaoke_app/
├── app.py                 # Main Flask application
├── config.py              # Configuration settings
├── requirements.txt       # Python dependencies
├── templates/
│   ├── index.html         # Main karaoke player
│   ├── upload.html       # Song upload page
│   └── lyrics_editor.html # Lyrics editing page
├── static/
│   ├── css/
│   │   └── style.css      # Player styling
│   ├── js/
│   │   └── player.js      # Karaoke player logic
│   └── uploads/          # Uploaded files storage
│   └── processed/        # Separated audio files
├── audio_separator/
│   ├── __init__.py
│   ├── spleeter_utils.py  # Spleeter separation
│   └── demucs_utils.py    # Demucs separation
├── transcription/
│   ├── __init__.py
│   └── whisper_utils.py   # Whisper transcription
└── lyrics/
    ├── __init__.py
    └── sync_utils.py      # LRC/synchronized lyrics
```

## Features & Implementation

### 1. Song Upload
- Accept audio files (MP3, WAV, FLAC, M4A)
- Store original file
- Queue for processing

### 2. Audio Separation (Vocals/Instrumental)
- **Spleeter**: Pre-trained model (2-stem: vocals/accompaniment)
- **Demucs**: Neural network-based separation (better quality)
- Output: instrumental.wav, vocals.wav

### 3. Whisper Transcription
- Transcribe vocal track to get lyrics
- Generate timestamped segments
- Create LRC format for sync

### 4. Karaoke Player Interface
- Play instrumental track
- Display scrolling synchronized lyrics
- Highlight current word/line
- Progress bar with seek functionality
- Volume controls

### 5. Voice Reduction
- Apply audio processing to reduce vocal in original track
- Use phase cancellation or AI-based reduction
- Mix with instrumental for karaoke backing

### 6. Lyrics Sync
- LRC format parsing
- Real-time synchronization with audio
- Word-by-word highlighting option

## API Endpoints
- `POST /upload` - Upload song
- `POST /separate` - Run audio separation
- `POST /transcribe` - Transcribe vocals to lyrics
- `GET /songs` - List all songs
- `GET /player/<filename>` - Stream audio
- `GET /lyrics/<filename>` - Get synchronized lyrics

## Implementation Steps

### Phase 1: Setup & Upload
1. Create Flask app structure
2. Implement file upload handling
3. Setup static file serving

### Phase 2: Audio Separation
1. Install Spleeter
2. Implement separation logic
3. Add Demucs as alternative

### Phase 3: Transcription
1. Integrate Whisper
2. Process vocals to text
3. Generate timestamped lyrics

### Phase 4: Player Interface
1. Create HTML player
2. Implement lyrics display
3. Add synchronization logic

### Phase 5: Voice Reduction
1. Implement vocal reduction
2. Add mixing controls
3. Test quality

## Dependencies
```
flask
spleeter
demucs
openai-whisper
numpy
scipy
pydub
sqlalchemy
```

## Notes
- Large model files will be downloaded (Spleeter, Demucs, Whisper)
- Processing time depends on audio length
- Consider using GPU for better performance

