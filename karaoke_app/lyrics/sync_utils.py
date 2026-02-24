import re
from datetime import datetime


def parse_srt(srt_content):
    """
    Parse SRT subtitle format to get time-tagged lyrics

    Args:
        srt_content: SRT formatted string

    Returns:
        List of dictionaries with 'time', 'end_time', and 'text'
    """
    # Normalize line endings (Windows \r\n → \n, stray \r → \n)
    srt_content = srt_content.replace('\r\n', '\n').replace('\r', '\n')

    segments = []
    timestamp_pattern = r'(\d{1,2}):(\d{2}):(\d{2})[,.](\d{3})\s*-->\s*(\d{1,2}):(\d{2}):(\d{2})[,.](\d{3})'

    # Parse line by line with a state machine (more robust than blank-line splitting)
    lines = srt_content.strip().split('\n')
    i = 0
    while i < len(lines):
        line = lines[i].strip()

        # Look for a timestamp line
        match = re.match(timestamp_pattern, line)
        if match:
            # Parse start time
            h, m, s, ms = int(match.group(1)), int(match.group(2)), int(match.group(3)), int(match.group(4))
            start_time = h * 3600 + m * 60 + s + ms / 1000

            # Parse end time
            h2, m2, s2, ms2 = int(match.group(5)), int(match.group(6)), int(match.group(7)), int(match.group(8))
            end_time = h2 * 3600 + m2 * 60 + s2 + ms2 / 1000

            # Collect all text lines until blank line, next block number, or end
            i += 1
            text_parts = []
            while i < len(lines):
                tline = lines[i].strip()
                # Stop at blank line or a line that is just a number (next block index)
                if tline == '' or (tline.isdigit() and i + 1 < len(lines) and re.match(timestamp_pattern, lines[i + 1].strip())):
                    break
                text_parts.append(tline)
                i += 1

            text = ' '.join(text_parts).strip()
            if text:
                segments.append({
                    'time': start_time,
                    'end_time': end_time,
                    'text': text
                })
        else:
            i += 1

    segments.sort(key=lambda x: x['time'])
    return segments


def srt_to_lrc(srt_content):
    """Convert SRT content to LRC format"""
    segments = parse_srt(srt_content)
    lrc_lines = []

    for seg in segments:
        minutes = int(seg['time'] // 60)
        seconds = int(seg['time'] % 60)
        hundredths = int((seg['time'] % 1) * 100)
        time_str = f"[{minutes:02d}:{seconds:02d}.{hundredths:02d}]"
        lrc_lines.append(f"{time_str}{seg['text']}")

    return '\n'.join(lrc_lines)


def parse_lrc(lrc_content):
    """
    Parse LRC format to get time-tagged lyrics
    
    Args:
        lrc_content: LRC formatted string
    
    Returns:
        List of dictionaries with 'time' and 'text'
    """
    # Normalize line endings
    lrc_content = lrc_content.replace('\r\n', '\n').replace('\r', '\n')

    lines = lrc_content.strip().split('\n')
    lyrics = []

    # Regex to match LRC format: [mm:ss.xx] or [mm:ss:xx] text
    pattern = r'\[(\d{2}):(\d{2})\.(\d{2,3})\](.*)'
    
    for line in lines:
        match = re.match(pattern, line)
        if match:
            minutes = int(match.group(1))
            seconds = int(match.group(2))
            # Handle both 2-digit (centiseconds) and 3-digit (milliseconds)
            centiseconds = match.group(3)
            if len(centiseconds) == 2:
                centiseconds = int(centiseconds) * 10  # Convert to milliseconds
            else:
                centiseconds = int(centiseconds)
            
            text = match.group(4).strip()
            
            # Calculate time in seconds
            time_seconds = minutes * 60 + seconds + centiseconds / 1000
            
            lyrics.append({
                'time': time_seconds,
                'minutes': minutes,
                'seconds': seconds,
                'milliseconds': centiseconds,
                'text': text
            })
    
    # Sort by time
    lyrics.sort(key=lambda x: x['time'])
    
    return lyrics


def create_lrc(segments):
    """
    Create LRC format from Whisper segments
    
    Args:
        segments: List of segment dictionaries with 'start', 'end', 'text'
    
    Returns:
        LRC formatted string
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


def create_word_level_lrc(segments):
    """
    Create word-level LRC for karaoke with word highlighting
    
    Args:
        segments: List of segments with word timestamps
    
    Returns:
        LRC formatted string with word-level timing
    """
    lrc_lines = []
    
    for segment in segments:
        if 'words' in segment and segment['words']:
            # Create combined word+timing line
            for word_info in segment['words']:
                start_time = word_info['start']
                word = word_info['word'].strip()
                
                minutes = int(start_time // 60)
                seconds = int(start_time % 60)
                hundredths = int((start_time % 1) * 100)
                
                time_str = f"[{minutes:02d}:{seconds:02d}.{hundredths:02d}]"
                lrc_lines.append(f"{time_str}{word}")
        else:
            # Fall back to segment-level timing
            start_time = segment['start']
            text = segment['text']
            
            minutes = int(start_time // 60)
            seconds = int(start_time % 60)
            hundredths = int((start_time % 1) * 100)
            
            time_str = f"[{minutes:02d}:{seconds:02d}.{hundredths:02d}]"
            lrc_lines.append(f"{time_str}{text}")
    
    return '\n'.join(lrc_lines)


def get_current_line(lyrics, current_time):
    """
    Get the current line based on playback time
    
    Args:
        lyrics: List of parsed LRC lyrics
        current_time: Current playback time in seconds
    
    Returns:
        Index of current line, or -1 if before first line
    """
    if not lyrics:
        return -1
    
    for i, line in enumerate(lyrics):
        if i == len(lyrics) - 1:
            # Last line - check if we're past it
            if current_time >= line['time']:
                return i
        else:
            # Check if we're between this line and next
            next_time = lyrics[i + 1]['time']
            if line['time'] <= current_time < next_time:
                return i
    
    return -1


def generate_lrc_from_text(text, duration):
    """
    Generate simple LRC with evenly spaced lines
    
    Use this as fallback when Whisper transcription isn't available
    
    Args:
        text: Lyrics text (one line per newline)
        duration: Total duration in seconds
    
    Returns:
        LRC formatted string
    """
    lines = text.strip().split('\n')
    
    if not lines:
        return ""
    
    # Calculate time per line
    time_per_line = duration / len(lines)
    
    lrc_lines = []
    for i, line in enumerate(lines):
        start_time = i * time_per_line
        minutes = int(start_time // 60)
        seconds = int(start_time % 60)
        hundredths = int((start_time % 1) * 100)
        
        time_str = f"[{minutes:02d}:{seconds:02d}.{hundredths:02d}]"
        lrc_lines.append(f"{time_str}{line.strip()}")
    
    return '\n'.join(lrc_lines)

