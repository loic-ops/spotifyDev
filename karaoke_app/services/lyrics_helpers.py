# helpers paroles: sauvegarde + conversion temps srt
import os
from lyrics.sync_utils import srt_to_lrc
from services.security import encrypt_data


def save_lyrics_file(lyrics_file, song_dir):
    content = lyrics_file.read().decode('utf-8')
    fname = lyrics_file.filename.lower()

    if fname.endswith('.srt'):
        with open(os.path.join(song_dir, 'lyrics.srt'), 'w', encoding='utf-8') as f:
            f.write(encrypt_data(content))
        lrc = srt_to_lrc(content)
        with open(os.path.join(song_dir, 'lyrics.lrc'), 'w', encoding='utf-8') as f:
            f.write(encrypt_data(lrc))
    elif fname.endswith('.lrc'):
        with open(os.path.join(song_dir, 'lyrics.lrc'), 'w', encoding='utf-8') as f:
            f.write(encrypt_data(content))
    else:
        # on devine le format
        if '-->' in content:
            with open(os.path.join(song_dir, 'lyrics.srt'), 'w', encoding='utf-8') as f:
                f.write(encrypt_data(content))
            lrc = srt_to_lrc(content)
            with open(os.path.join(song_dir, 'lyrics.lrc'), 'w', encoding='utf-8') as f:
                f.write(encrypt_data(lrc))
        else:
            with open(os.path.join(song_dir, 'lyrics.lrc'), 'w', encoding='utf-8') as f:
                f.write(encrypt_data(content))


def seconds_to_srt_time(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds % 1) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
