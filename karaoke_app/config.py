import json
import os
import secrets
from dotenv import load_dotenv

# Load .env file if exists (for local development)
load_dotenv()

# Base directories
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# MySQL Database Configuration (defaults for Docker)
MYSQL_HOST = os.environ.get('MYSQL_HOST', 'mysql')
MYSQL_PORT = os.environ.get('MYSQL_PORT', '3306')
MYSQL_USER = os.environ.get('MYSQL_USER', 'karaoke')
MYSQL_PASSWORD = os.environ.get('MYSQL_PASSWORD', 'karaoke_password')
MYSQL_DATABASE = os.environ.get('MYSQL_DATABASE', 'karaoke_db')

DATABASE_URI = f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DATABASE}"


def _get_or_create_keys():
    """
    Auto-generate and persist SECRET_KEY and ENCRYPTION_KEY.

    Priority:
    1. Environment variable / .env  (explicit override)
    2. Persisted keys file in the data volume (survives container rebuilds)
    3. Generate new keys and save them to the keys file
    """
    from cryptography.fernet import Fernet

    keys_dir = os.path.join(BASE_DIR, 'static', 'processed')
    os.makedirs(keys_dir, exist_ok=True)
    keys_file = os.path.join(keys_dir, '.keys.json')

    # Load previously persisted keys (if any)
    persisted = {}
    if os.path.exists(keys_file):
        try:
            with open(keys_file, 'r') as f:
                persisted = json.load(f)
        except (json.JSONDecodeError, OSError):
            persisted = {}

    # Resolve SECRET_KEY
    secret_key = (os.environ.get('SECRET_KEY')
                  or persisted.get('SECRET_KEY')
                  or secrets.token_hex(32))

    # Resolve ENCRYPTION_KEY
    encryption_key = (os.environ.get('ENCRYPTION_KEY')
                      or persisted.get('ENCRYPTION_KEY')
                      or Fernet.generate_key().decode())

    # Persist for next startup (only write if something changed)
    new_persisted = {'SECRET_KEY': secret_key, 'ENCRYPTION_KEY': encryption_key}
    if new_persisted != persisted:
        try:
            with open(keys_file, 'w') as f:
                json.dump(new_persisted, f)
            os.chmod(keys_file, 0o600)
        except OSError:
            pass  # Read-only filesystem — keys will still work for this session

    return secret_key, encryption_key


_SECRET_KEY, _ENCRYPTION_KEY = _get_or_create_keys()


class Config:
    """Flask config object"""
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
    PROCESSED_FOLDER = os.path.join(BASE_DIR, 'static', 'processed')
    ALLOWED_EXTENSIONS = {'mp3', 'wav', 'flac', 'm4a', 'ogg'}
    DATABASE_URI = DATABASE_URI
    MAX_CONTENT_LENGTH = 100 * 1024 * 1024
    SAMPLE_RATE = 44100
    CHANNELS = 2

    SECRET_KEY = _SECRET_KEY
    ENCRYPTION_KEY = _ENCRYPTION_KEY


def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in Config.ALLOWED_EXTENSIONS
