import os
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


class Config:
    """Flask config object"""
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
    PROCESSED_FOLDER = os.path.join(BASE_DIR, 'static', 'processed')
    ALLOWED_EXTENSIONS = {'mp3', 'wav', 'flac', 'm4a', 'ogg'}
    DATABASE_URI = DATABASE_URI
    MAX_CONTENT_LENGTH = 100 * 1024 * 1024
    SAMPLE_RATE = 44100
    CHANNELS = 2
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key')
    ADMIN_CODE = os.environ.get('ADMIN_CODE', '1234')


def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in Config.ALLOWED_EXTENSIONS

