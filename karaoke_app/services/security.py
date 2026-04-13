# chiffrement fernet + validation + sanitisation
import os, re
from cryptography.fernet import Fernet
from flask import abort, current_app

ALLOWED_AUDIO_EXT = {'.mp3', '.wav', '.flac', '.m4a', '.ogg'}
ALLOWED_IMAGE_EXT = {'.jpg', '.jpeg', '.png', '.webp'}
ALLOWED_LYRICS_EXT = {'.srt', '.lrc'}


def validate_file_extension(filename, allowed):
    ext = os.path.splitext(filename)[1].lower()
    return ext if ext in allowed else None


UUID_RE = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', re.I)

def validate_song_id(sid):
    if not UUID_RE.match(sid):
        abort(400, description="Invalid song ID format")
    return sid


def sanitize_text(txt):
    # strip + cap 500 chars, l'echappement html se fait au render
    if not txt:
        return txt
    return txt.strip()[:500]


def _get_fernet():
    try:
        key = current_app.config.get('ENCRYPTION_KEY')
    except RuntimeError:
        # hors contexte flask (rq worker)
        from config import Config
        key = Config.ENCRYPTION_KEY
    if not key:
        raise RuntimeError("ENCRYPTION_KEY not configured")
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt_data(data: str) -> str:
    f = _get_fernet()
    return f.encrypt(data.encode('utf-8')).decode('utf-8')

def decrypt_data(token: str) -> str:
    f = _get_fernet()
    return f.decrypt(token.encode('utf-8')).decode('utf-8')


def encrypt_file(filepath):
    f = _get_fernet()
    with open(filepath, 'rb') as fh:
        raw = fh.read()
    with open(filepath, 'wb') as fh:
        fh.write(f.encrypt(raw))


def decrypt_file_bytes(filepath) -> bytes:
    f = _get_fernet()
    with open(filepath, 'rb') as fh:
        enc = fh.read()
    return f.decrypt(enc)
