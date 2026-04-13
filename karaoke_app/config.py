# config principale
import json, os, secrets
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# mysql (defaults docker)
MYSQL_HOST = os.environ.get('MYSQL_HOST', 'mysql')
MYSQL_PORT = os.environ.get('MYSQL_PORT', '3306')
MYSQL_USER = os.environ.get('MYSQL_USER', 'karaoke')
MYSQL_PASSWORD = os.environ.get('MYSQL_PASSWORD', 'karaoke_password')
MYSQL_DATABASE = os.environ.get('MYSQL_DATABASE', 'karaoke_db')

DATABASE_URI = f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DATABASE}"


def _get_or_create_keys():
    from cryptography.fernet import Fernet

    keys_dir = os.path.join(BASE_DIR, 'data')
    os.makedirs(keys_dir, exist_ok=True)
    keys_file = os.path.join(keys_dir, '.keys.json')

    persisted = {}
    if os.path.exists(keys_file):
        try:
            with open(keys_file, 'r') as f:
                persisted = json.load(f)
        except (json.JSONDecodeError, OSError):
            persisted = {}

    secret_key = (os.environ.get('SECRET_KEY')
                  or persisted.get('SECRET_KEY')
                  or secrets.token_hex(32))

    enc_key = (os.environ.get('ENCRYPTION_KEY')
               or persisted.get('ENCRYPTION_KEY')
               or Fernet.generate_key().decode())

    new_data = {'SECRET_KEY': secret_key, 'ENCRYPTION_KEY': enc_key}
    if new_data != persisted:
        try:
            with open(keys_file, 'w') as f:
                json.dump(new_data, f)
            os.chmod(keys_file, 0o600)
        except OSError:
            pass  # read-only fs, pas grave

    return secret_key, enc_key


_SECRET_KEY, _ENCRYPTION_KEY = _get_or_create_keys()

REDIS_URL = os.environ.get('REDIS_URL', 'redis://redis:6379/0')


class Config:
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
    PROCESSED_FOLDER = os.path.join(BASE_DIR, 'static', 'processed')
    ALLOWED_EXTENSIONS = {'mp3', 'wav', 'flac', 'm4a', 'ogg'}
    DATABASE_URI = DATABASE_URI
    REDIS_URL = REDIS_URL
    MAX_CONTENT_LENGTH = 100 * 1024 * 1024  # 100MB
    SAMPLE_RATE = 44100
    CHANNELS = 2
    SESSION_LIFETIME = 4 * 3600  # 4h
    SECRET_KEY = _SECRET_KEY
    ENCRYPTION_KEY = _ENCRYPTION_KEY


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in Config.ALLOWED_EXTENSIONS
