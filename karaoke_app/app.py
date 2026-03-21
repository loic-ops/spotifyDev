import os
import uuid
import json
import time
import re
import secrets
import html
from functools import wraps
from flask import Flask, render_template, request, jsonify, send_file, session, redirect, url_for, abort
from werkzeug.utils import secure_filename
from config import Config
from lyrics.sync_utils import parse_lrc, parse_srt, srt_to_lrc
from database.db_utils import (
    init_db, add_song, get_all_songs, get_song_by_id, delete_song,
    update_song_title, update_song_status,
    create_admin, authenticate_admin, admin_exists, get_admin_by_id,
    get_admin_by_username, reset_admin_password
)

app = Flask(__name__)
app.config.from_object(Config)

# Secure session configuration
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

REMEMBER_ME_LIFETIME = 30 * 24 * 3600  # 30 days
DEFAULT_SESSION_LIFETIME = 3600  # 1 hour

# Ensure upload directories exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['PROCESSED_FOLDER'], exist_ok=True)


# ─── ENCRYPTION UTILS ─────────────────────────────────────────────────────────

from cryptography.fernet import Fernet

def _get_fernet():
    """Get Fernet instance from ENCRYPTION_KEY config."""
    key = app.config.get('ENCRYPTION_KEY')
    if not key:
        raise RuntimeError("ENCRYPTION_KEY not configured")
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt_data(data: str) -> str:
    """Encrypt a string and return base64-encoded ciphertext."""
    f = _get_fernet()
    return f.encrypt(data.encode('utf-8')).decode('utf-8')


def decrypt_data(token: str) -> str:
    """Decrypt a base64-encoded ciphertext and return plaintext."""
    f = _get_fernet()
    return f.decrypt(token.encode('utf-8')).decode('utf-8')


def encrypt_file(filepath):
    """Encrypt a file in-place."""
    f = _get_fernet()
    with open(filepath, 'rb') as fh:
        data = fh.read()
    encrypted = f.encrypt(data)
    with open(filepath, 'wb') as fh:
        fh.write(encrypted)


def decrypt_file_bytes(filepath) -> bytes:
    """Read and decrypt a file, returning raw bytes."""
    f = _get_fernet()
    with open(filepath, 'rb') as fh:
        encrypted = fh.read()
    return f.decrypt(encrypted)


# ─── SECURITY HELPERS ──────────────────────────────────────────────────────────

UUID_RE = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', re.I)

def validate_song_id(song_id):
    """Validate that song_id is a proper UUID to prevent path traversal."""
    if not UUID_RE.match(song_id):
        abort(400, description="Invalid song ID format")
    return song_id


def sanitize_text(text):
    """Sanitize user text input: strip and limit length. Escaping is done at render time."""
    if not text:
        return text
    return text.strip()[:500]


ALLOWED_AUDIO_EXT = {'.mp3', '.wav', '.flac', '.m4a', '.ogg'}
ALLOWED_IMAGE_EXT = {'.jpg', '.jpeg', '.png', '.webp'}
ALLOWED_LYRICS_EXT = {'.srt', '.lrc'}


def validate_file_extension(filename, allowed_exts):
    """Validate file extension against whitelist."""
    ext = os.path.splitext(filename)[1].lower()
    if ext not in allowed_exts:
        return None
    return ext


# ─── RATE LIMITING (in-memory, simple) ─────────────────────────────────────────

_login_attempts = {}  # ip -> (count, first_attempt_time)
MAX_LOGIN_ATTEMPTS = 5
LOGIN_WINDOW = 300  # 5 minutes


def check_rate_limit(ip):
    """Return True if the IP is rate-limited."""
    now = time.time()
    if ip in _login_attempts:
        count, first_time = _login_attempts[ip]
        if now - first_time > LOGIN_WINDOW:
            _login_attempts[ip] = (1, now)
            return False
        if count >= MAX_LOGIN_ATTEMPTS:
            return True
        _login_attempts[ip] = (count + 1, first_time)
    else:
        _login_attempts[ip] = (1, now)
    return False


def reset_rate_limit(ip):
    _login_attempts.pop(ip, None)


# ─── CSRF PROTECTION ──────────────────────────────────────────────────────────

def generate_csrf_token():
    if '_csrf_token' not in session:
        session['_csrf_token'] = secrets.token_hex(32)
    return session['_csrf_token']


# Make csrf_token available in all templates
app.jinja_env.globals['csrf_token'] = generate_csrf_token


def verify_csrf():
    """Verify CSRF token for state-changing requests. Returns error response or None."""
    token = request.form.get('_csrf_token') or request.headers.get('X-CSRF-Token')
    if not token or token != session.get('_csrf_token'):
        abort(403, description="CSRF token missing or invalid")


# ─── SECURITY HEADERS ─────────────────────────────────────────────────────────

@app.after_request
def set_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['Content-Security-Policy'] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com; "
        "style-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com; "
        "font-src 'self' https://cdnjs.cloudflare.com; "
        "img-src 'self' data:; "
        "media-src 'self'"
    )
    return response


# ─── DATABASE INIT ─────────────────────────────────────────────────────────────

def wait_for_database(max_retries=30, delay=2):
    """Wait for MySQL to be ready"""
    from sqlalchemy import create_engine
    from sqlalchemy.exc import OperationalError

    for i in range(max_retries):
        try:
            engine = create_engine(Config.DATABASE_URI)
            with engine.connect():
                print("Database connected successfully!")
                return True
        except OperationalError:
            print(f"Waiting for database... ({i+1}/{max_retries})")
            time.sleep(delay)
    return False


@app.before_request
def initialize_database():
    """Initialize database on first request"""
    if not hasattr(app, 'db_initialized'):
        try:
            init_db()
            app.db_initialized = True
            print("Database initialized successfully!")
        except Exception as e:
            print(f"Database initialization error: {e}")


@app.before_request
def apply_session_lifetime():
    """Set session lifetime based on remember_me preference."""
    from datetime import timedelta
    if session.get('remember_me'):
        app.permanent_session_lifetime = timedelta(seconds=REMEMBER_ME_LIFETIME)
    else:
        app.permanent_session_lifetime = timedelta(seconds=DEFAULT_SESSION_LIFETIME)


# ─── AUTH DECORATORS ───────────────────────────────────────────────────────────

def admin_required_decorator(f):
    """Decorator to protect routes requiring admin auth."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('admin_id'):
            if request.is_json or request.path.startswith('/api/'):
                return jsonify({'error': 'Authentication required'}), 401
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated


def csrf_protected(f):
    """Decorator for CSRF protection on state-changing API endpoints."""
    @wraps(f)
    def decorated(*args, **kwargs):
        verify_csrf()
        return f(*args, **kwargs)
    return decorated


# ─── PLAYER INTERFACE (public, no auth needed) ────────────────────────────────

@app.route('/')
def player():
    return render_template('player.html')


@app.route('/library')
def library():
    return render_template('library.html')


# ─── ADMIN AUTH ────────────────────────────────────────────────────────────────

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    # If no admin exists, redirect to setup
    if not admin_exists():
        return redirect(url_for('admin_setup'))

    error = None
    if request.method == 'POST':
        ip = request.remote_addr
        if check_rate_limit(ip):
            error = 'Trop de tentatives. Attendez 5 minutes.'
            return render_template('admin_login.html', error=error)

        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        remember_me = request.form.get('remember_me') == 'on'

        admin_id = authenticate_admin(username, password)
        if admin_id:
            reset_rate_limit(ip)
            session.permanent = True
            session['admin_id'] = admin_id
            session['admin_username'] = username
            session['remember_me'] = remember_me
            session.modified = True
            return redirect(url_for('admin'))
        error = 'Identifiants incorrects'

    return render_template('admin_login.html', error=error)


@app.route('/admin/forgot-password', methods=['GET', 'POST'])
def admin_forgot_password():
    """Password reset using ENCRYPTION_KEY as proof of server access."""
    if not admin_exists():
        return redirect(url_for('admin_setup'))

    error = None
    success = None

    if request.method == 'POST':
        ip = request.remote_addr
        if check_rate_limit(ip):
            error = 'Trop de tentatives. Attendez 5 minutes.'
            return render_template('admin_forgot_password.html', error=error, success=success)

        username = request.form.get('username', '').strip()
        encryption_key = request.form.get('encryption_key', '').strip()
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')

        # Verify the user exists
        admin = get_admin_by_username(username)
        if not admin:
            error = "Nom d'utilisateur introuvable"
        # Verify the encryption key matches (proof of server access)
        elif encryption_key != app.config.get('ENCRYPTION_KEY', ''):
            error = "Cle de recuperation incorrecte"
        elif len(new_password) < 8:
            error = "Le nouveau mot de passe doit contenir au moins 8 caracteres"
        elif new_password != confirm_password:
            error = "Les mots de passe ne correspondent pas"
        else:
            if reset_admin_password(username, new_password):
                reset_rate_limit(ip)
                success = "Mot de passe reinitialise avec succes ! Vous pouvez vous connecter."
            else:
                error = "Erreur lors de la reinitialisation"

    return render_template('admin_forgot_password.html', error=error, success=success)


@app.route('/admin/setup', methods=['GET', 'POST'])
def admin_setup():
    """First-time admin account creation. Only works when no admin exists."""
    if admin_exists():
        return redirect(url_for('admin_login'))

    error = None
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        confirm = request.form.get('confirm_password', '')

        if len(username) < 3:
            error = "Le nom d'utilisateur doit contenir au moins 3 caracteres"
        elif len(password) < 8:
            error = "Le mot de passe doit contenir au moins 8 caracteres"
        elif password != confirm:
            error = "Les mots de passe ne correspondent pas"
        else:
            admin_id = create_admin(username, password)
            if admin_id:
                session.permanent = True
                session['admin_id'] = admin_id
                session['admin_username'] = username
                return redirect(url_for('admin'))
            error = "Erreur lors de la creation du compte"

    return render_template('admin_setup.html', error=error)


@app.route('/admin/logout')
def admin_logout():
    session.clear()
    return redirect(url_for('player'))


# ─── ADMIN INTERFACE ──────────────────────────────────────────────────────────

@app.route('/admin')
@admin_required_decorator
def admin():
    return render_template('admin.html')


@app.route('/admin/upload')
@admin_required_decorator
def admin_upload():
    return render_template('admin_upload.html')


# ─── API ENDPOINTS (Admin-only, state-changing) ──────────────────────────────

@app.route('/api/upload', methods=['POST'])
@admin_required_decorator
@csrf_protected
def upload_song():
    """Handle song upload with optional lyrics (SRT or LRC)"""
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    filename = secure_filename(file.filename)
    ext = validate_file_extension(filename, ALLOWED_AUDIO_EXT)
    if not ext:
        return jsonify({'error': 'File type not allowed'}), 400

    song_id = str(uuid.uuid4())
    name = os.path.splitext(filename)[0]
    artist = sanitize_text(request.form.get('artist', 'Unknown Artist'))

    # Save original file
    original_filename = f"{song_id}{ext}"
    original_path = os.path.join(app.config['UPLOAD_FOLDER'], original_filename)
    file.save(original_path)

    # Create processed directory
    song_dir = os.path.join(app.config['PROCESSED_FOLDER'], song_id)
    os.makedirs(song_dir, exist_ok=True)

    # Save metadata (encrypted)
    meta = {'artist': artist, 'title': sanitize_text(name)}
    meta_path = os.path.join(song_dir, 'meta.json')
    encrypted_meta = encrypt_data(json.dumps(meta))
    with open(meta_path, 'w') as f:
        f.write(encrypted_meta)

    # Handle lyrics file (SRT or LRC)
    lyrics_db_file = None
    lyrics_file = request.files.get('lyrics_file')
    if lyrics_file and lyrics_file.filename:
        lyrics_ext = validate_file_extension(lyrics_file.filename, ALLOWED_LYRICS_EXT)
        if lyrics_ext:
            _save_lyrics_file(lyrics_file, song_dir)
            lyrics_db_file = 'lyrics.lrc' if os.path.exists(os.path.join(song_dir, 'lyrics.lrc')) else 'lyrics.srt'

    # Handle cover image
    cover_file = request.files.get('cover_file')
    if cover_file and cover_file.filename:
        cover_ext = validate_file_extension(cover_file.filename, ALLOWED_IMAGE_EXT)
        if cover_ext:
            cover_path = os.path.join(song_dir, f'cover{cover_ext}')
            cover_file.save(cover_path)

    try:
        add_song(song_id, name, original_filename, lyrics_file=lyrics_db_file)
    except Exception:
        return jsonify({'error': 'Database error'}), 500

    return jsonify({
        'song_id': song_id, 'title': name, 'artist': artist,
        'message': 'Song uploaded successfully'
    })


def _save_lyrics_file(lyrics_file, song_dir):
    """Save a lyrics file (SRT or LRC), encrypt at rest, and ensure both formats exist."""
    content = lyrics_file.read().decode('utf-8')
    fname = lyrics_file.filename.lower()

    if fname.endswith('.srt'):
        srt_path = os.path.join(song_dir, 'lyrics.srt')
        with open(srt_path, 'w', encoding='utf-8') as f:
            f.write(encrypt_data(content))
        lrc_content = srt_to_lrc(content)
        lrc_path = os.path.join(song_dir, 'lyrics.lrc')
        with open(lrc_path, 'w', encoding='utf-8') as f:
            f.write(encrypt_data(lrc_content))
    elif fname.endswith('.lrc'):
        lrc_path = os.path.join(song_dir, 'lyrics.lrc')
        with open(lrc_path, 'w', encoding='utf-8') as f:
            f.write(encrypt_data(content))
    else:
        # Try to detect format
        if '-->' in content:
            srt_path = os.path.join(song_dir, 'lyrics.srt')
            with open(srt_path, 'w', encoding='utf-8') as f:
                f.write(encrypt_data(content))
            lrc_content = srt_to_lrc(content)
            lrc_path = os.path.join(song_dir, 'lyrics.lrc')
            with open(lrc_path, 'w', encoding='utf-8') as f:
                f.write(encrypt_data(lrc_content))
        else:
            lrc_path = os.path.join(song_dir, 'lyrics.lrc')
            with open(lrc_path, 'w', encoding='utf-8') as f:
                f.write(encrypt_data(content))


@app.route('/api/upload-lyrics/<song_id>', methods=['POST'])
@admin_required_decorator
@csrf_protected
def upload_lyrics(song_id):
    """Upload lyrics (SRT or LRC) for an existing song"""
    validate_song_id(song_id)

    if 'lyrics_file' not in request.files:
        return jsonify({'error': 'No lyrics file provided'}), 400

    lyrics_file = request.files['lyrics_file']
    if lyrics_file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    lyrics_ext = validate_file_extension(lyrics_file.filename, ALLOWED_LYRICS_EXT)
    if not lyrics_ext:
        return jsonify({'error': 'File type not allowed. Use .srt or .lrc'}), 400

    song = get_song_by_id(song_id)
    if not song:
        return jsonify({'error': 'Song not found'}), 404

    song_dir = os.path.join(app.config['PROCESSED_FOLDER'], song_id)
    os.makedirs(song_dir, exist_ok=True)

    _save_lyrics_file(lyrics_file, song_dir)

    # Update lyrics_file in DB
    lyrics_db_file = 'lyrics.lrc' if os.path.exists(os.path.join(song_dir, 'lyrics.lrc')) else 'lyrics.srt'
    update_song_status(song_id, song[7] or 'uploaded', lyrics_file=lyrics_db_file)

    return jsonify({'message': 'Lyrics uploaded successfully'})


@app.route('/api/songs/<song_id>', methods=['PUT'])
@admin_required_decorator
@csrf_protected
def update_song(song_id):
    """Update song metadata (title, artist)"""
    validate_song_id(song_id)

    song = get_song_by_id(song_id)
    if not song:
        return jsonify({'error': 'Song not found'}), 404

    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    song_dir = os.path.join(app.config['PROCESSED_FOLDER'], song_id)
    meta_path = os.path.join(song_dir, 'meta.json')

    meta = {}
    if os.path.exists(meta_path):
        with open(meta_path, 'r') as f:
            try:
                meta = json.loads(decrypt_data(f.read()))
            except Exception:
                meta = {}

    if 'title' in data:
        meta['title'] = sanitize_text(data['title'])
        update_song_title(song_id, meta['title'])
    if 'artist' in data:
        meta['artist'] = sanitize_text(data['artist'])

    os.makedirs(song_dir, exist_ok=True)
    with open(meta_path, 'w') as f:
        f.write(encrypt_data(json.dumps(meta)))

    return jsonify({'message': 'Song updated', 'meta': meta})


@app.route('/api/separate/<song_id>', methods=['POST'])
@admin_required_decorator
@csrf_protected
def separate_audio(song_id):
    """Separate vocals from instrumental using Demucs"""
    validate_song_id(song_id)

    song = get_song_by_id(song_id)
    if not song:
        return jsonify({'error': 'Song not found'}), 404

    original_path = os.path.join(app.config['UPLOAD_FOLDER'], song[2])
    output_dir = os.path.join(app.config['PROCESSED_FOLDER'], song_id)

    try:
        from audio_separator.demucs_utils import separate_audio_demucs
        separate_audio_demucs(original_path, output_dir)

        # Detect generated files and update DB
        vocals_file = None
        instrumental_file = None
        for ext in ['.wav', '.mp3']:
            vpath = os.path.join(output_dir, f'vocals{ext}')
            ipath = os.path.join(output_dir, f'instrumental{ext}')
            if os.path.exists(vpath) and not vocals_file:
                vocals_file = f'vocals{ext}'
            if os.path.exists(ipath) and not instrumental_file:
                instrumental_file = f'instrumental{ext}'

        update_song_status(song_id, 'separated',
                           vocals_file=vocals_file,
                           instrumental_file=instrumental_file)

        return jsonify({'message': 'Audio separated successfully'})
    except Exception:
        return jsonify({'error': 'Audio separation failed'}), 500


@app.route('/api/songs/<song_id>', methods=['DELETE'])
@admin_required_decorator
@csrf_protected
def delete_song_api(song_id):
    """Delete a song and all its files"""
    import shutil
    validate_song_id(song_id)

    try:
        song = get_song_by_id(song_id)
        if not song:
            return jsonify({'error': 'Song not found'}), 404

        original_path = os.path.join(app.config['UPLOAD_FOLDER'], song[2])
        if os.path.exists(original_path):
            os.remove(original_path)

        song_dir = os.path.join(app.config['PROCESSED_FOLDER'], song_id)
        if os.path.exists(song_dir):
            shutil.rmtree(song_dir)

        delete_song(song_id)
        return jsonify({'message': 'Song deleted'})
    except Exception:
        return jsonify({'error': 'Delete failed'}), 500


@app.route('/api/lyrics-save/<song_id>', methods=['PUT'])
@admin_required_decorator
@csrf_protected
def save_lyrics(song_id):
    """Save edited lyrics (receives JSON array of segments)"""
    validate_song_id(song_id)

    song = get_song_by_id(song_id)
    if not song:
        return jsonify({'error': 'Song not found'}), 404

    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    segments = data.get('segments', [])

    song_dir = os.path.join(app.config['PROCESSED_FOLDER'], song_id)
    os.makedirs(song_dir, exist_ok=True)

    # Build SRT content from segments
    srt_lines = []
    for i, seg in enumerate(segments, 1):
        start = _seconds_to_srt_time(seg['time'])
        end = _seconds_to_srt_time(seg['end_time'])
        srt_lines.append(f"{i}")
        srt_lines.append(f"{start} --> {end}")
        srt_lines.append(sanitize_text(seg['text']))
        srt_lines.append("")

    srt_content = '\n'.join(srt_lines)

    # Save SRT (encrypted)
    with open(os.path.join(song_dir, 'lyrics.srt'), 'w', encoding='utf-8') as f:
        f.write(encrypt_data(srt_content))

    # Regenerate LRC (encrypted)
    lrc_content = srt_to_lrc(srt_content)
    with open(os.path.join(song_dir, 'lyrics.lrc'), 'w', encoding='utf-8') as f:
        f.write(encrypt_data(lrc_content))

    update_song_status(song_id, song[7] or 'uploaded', lyrics_file='lyrics.lrc')

    return jsonify({'message': 'Lyrics saved successfully'})


@app.route('/api/vocal-reduce/<song_id>', methods=['POST'])
@admin_required_decorator
@csrf_protected
def reduce_vocals(song_id):
    """Reduce vocals in a song"""
    validate_song_id(song_id)

    from audio_separator.vocal_reduce import reduce_vocal

    data = request.get_json()
    reduction_level = data.get('level', 0.5) if data else 0.5
    # Validate reduction_level is a number between 0 and 1
    try:
        reduction_level = float(reduction_level)
        reduction_level = max(0.0, min(1.0, reduction_level))
    except (ValueError, TypeError):
        reduction_level = 0.5

    song = get_song_by_id(song_id)
    if not song:
        return jsonify({'error': 'Song not found'}), 404

    instrumental_path = None
    for ext in ['.wav', '.mp3']:
        path = os.path.join(app.config['PROCESSED_FOLDER'], song_id, f'instrumental{ext}')
        if os.path.exists(path):
            instrumental_path = path
            break

    if not instrumental_path:
        return jsonify({'error': 'Instrumental not found'}), 400

    original_path = os.path.join(app.config['UPLOAD_FOLDER'], song[2])
    if not os.path.exists(original_path):
        return jsonify({'error': 'Original file not found'}), 400

    output_path = os.path.join(app.config['PROCESSED_FOLDER'], song_id, 'karaoke.wav')

    try:
        reduce_vocal(original_path, instrumental_path, output_path, reduction_level)
        return jsonify({'message': 'Vocal reduced successfully'})
    except Exception:
        return jsonify({'error': 'Vocal reduction failed'}), 500


@app.route('/api/transcribe/<song_id>', methods=['POST'])
@admin_required_decorator
@csrf_protected
def transcribe_song(song_id):
    """Transcribe audio to lyrics using Whisper"""
    validate_song_id(song_id)

    song = get_song_by_id(song_id)
    if not song:
        return jsonify({'error': 'Song not found'}), 404

    data = request.get_json() or {}
    model_name = data.get('model', 'base')
    # Whitelist model names
    if model_name not in ('tiny', 'base', 'small', 'medium', 'large'):
        model_name = 'base'

    # Prefer vocals file for cleaner transcription, fallback to original
    song_dir = os.path.join(app.config['PROCESSED_FOLDER'], song_id)
    audio_path = None

    # Try vocals first
    for ext in ['.wav', '.mp3']:
        vpath = os.path.join(song_dir, f'vocals{ext}')
        if os.path.exists(vpath):
            audio_path = vpath
            break

    # Fallback to original
    if not audio_path:
        audio_path = os.path.join(app.config['UPLOAD_FOLDER'], song[2])

    if not os.path.exists(audio_path):
        return jsonify({'error': 'Audio file not found'}), 404

    try:
        from transcription.whisper_utils import transcribe_audio

        result = transcribe_audio(audio_path, model_name=model_name)

        if not result or not result.get('segments'):
            return jsonify({'error': 'Transcription produced no results'}), 500

        # Build SRT from Whisper segments
        srt_lines = []
        for i, seg in enumerate(result['segments'], 1):
            start = _seconds_to_srt_time(seg['start'])
            end = _seconds_to_srt_time(seg['end'])
            srt_lines.append(f"{i}")
            srt_lines.append(f"{start} --> {end}")
            srt_lines.append(seg['text'])
            srt_lines.append("")

        srt_content = '\n'.join(srt_lines)

        # Save SRT (encrypted)
        os.makedirs(song_dir, exist_ok=True)
        with open(os.path.join(song_dir, 'lyrics.srt'), 'w', encoding='utf-8') as f:
            f.write(encrypt_data(srt_content))

        # Generate and save LRC (encrypted)
        lrc_content = srt_to_lrc(srt_content)
        with open(os.path.join(song_dir, 'lyrics.lrc'), 'w', encoding='utf-8') as f:
            f.write(encrypt_data(lrc_content))

        # Update DB
        update_song_status(song_id, song[7] or 'uploaded', lyrics_file='lyrics.lrc')

        return jsonify({
            'message': 'Transcription completed',
            'segments': len(result['segments']),
            'text_preview': result['text'][:200]
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Transcription failed: {str(e)}'}), 500


# ─── PUBLIC API ENDPOINTS (read-only, for the player) ─────────────────────────

@app.route('/api/songs', methods=['GET'])
def list_songs():
    """Get all uploaded songs with metadata"""
    try:
        songs = get_all_songs()
        result = []
        for s in songs:
            song_dir = os.path.join(app.config['PROCESSED_FOLDER'], s[0])

            title = s[1]
            artist = 'Unknown Artist'
            meta_path = os.path.join(song_dir, 'meta.json')
            if os.path.exists(meta_path):
                try:
                    with open(meta_path, 'r') as f:
                        meta = json.loads(decrypt_data(f.read()))
                        artist = meta.get('artist', 'Unknown Artist')
                        title = meta.get('title', title)
                except Exception:
                    pass

            has_cover = any(
                os.path.exists(os.path.join(song_dir, f'cover{ext}'))
                for ext in ['.jpg', '.jpeg', '.png', '.webp']
            )
            has_lyrics = (
                os.path.exists(os.path.join(song_dir, 'lyrics.lrc')) or
                os.path.exists(os.path.join(song_dir, 'lyrics.srt'))
            )
            has_instrumental = any(
                os.path.exists(os.path.join(song_dir, f'instrumental{e}'))
                for e in ['.wav', '.mp3']
            )
            has_vocals = any(
                os.path.exists(os.path.join(song_dir, f'vocals{e}'))
                for e in ['.wav', '.mp3']
            )

            result.append({
                'id': s[0], 'title': title, 'artist': artist,
                'original_file': s[2], 'has_cover': has_cover,
                'has_lyrics': has_lyrics, 'has_instrumental': has_instrumental,
                'has_vocals': has_vocals
            })

        return jsonify(result)
    except Exception:
        return jsonify({'error': 'Failed to load songs'}), 500


@app.route('/api/audio/<song_id>/<track_type>')
def stream_audio(song_id, track_type):
    """Stream audio file"""
    validate_song_id(song_id)

    valid_types = ['original', 'instrumental', 'vocals']
    if track_type not in valid_types:
        return jsonify({'error': 'Invalid track type'}), 400

    if track_type == 'original':
        song = get_song_by_id(song_id)
        if not song:
            return jsonify({'error': 'Song not found'}), 404
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], song[2])
        if not os.path.exists(filepath):
            return jsonify({'error': 'Audio file not found'}), 404
    else:
        filepath = None
        for ext in ['.wav', '.mp3']:
            path = os.path.join(app.config['PROCESSED_FOLDER'], song_id, f'{track_type}{ext}')
            if os.path.exists(path):
                filepath = path
                break
        if not filepath:
            return jsonify({'error': 'Audio file not found'}), 404

    mimetype = 'audio/wav' if filepath.endswith('.wav') else 'audio/mpeg'
    return send_file(filepath, mimetype=mimetype, conditional=True)


@app.route('/api/cover/<song_id>')
def get_cover(song_id):
    """Get cover art for a song"""
    validate_song_id(song_id)

    song_dir = os.path.join(app.config['PROCESSED_FOLDER'], song_id)
    for ext in ['.jpg', '.jpeg', '.png', '.webp']:
        cover_path = os.path.join(song_dir, f'cover{ext}')
        if os.path.exists(cover_path):
            return send_file(cover_path)
    return jsonify({'error': 'No cover art'}), 404


@app.route('/api/lyrics/<song_id>')
def get_lyrics(song_id):
    """Get parsed lyrics for player display"""
    validate_song_id(song_id)

    song_dir = os.path.join(app.config['PROCESSED_FOLDER'], song_id)

    lrc_path = os.path.join(song_dir, 'lyrics.lrc')
    if os.path.exists(lrc_path):
        with open(lrc_path, 'r', encoding='utf-8') as f:
            try:
                lrc_content = decrypt_data(f.read())
            except Exception:
                # Fallback: file might not be encrypted (legacy)
                f.seek(0)
                lrc_content = f.read()
        segments = parse_lrc(lrc_content)
        return jsonify({'segments': segments, 'lrc': lrc_content})

    srt_path = os.path.join(song_dir, 'lyrics.srt')
    if os.path.exists(srt_path):
        with open(srt_path, 'r', encoding='utf-8') as f:
            try:
                srt_content = decrypt_data(f.read())
            except Exception:
                f.seek(0)
                srt_content = f.read()
        segments = parse_srt(srt_content)
        return jsonify({'segments': segments})

    return jsonify({'error': 'Lyrics not found'}), 404


@app.route('/api/lyrics-raw/<song_id>')
@admin_required_decorator
def get_lyrics_raw(song_id):
    """Get raw SRT content for editing (admin only)"""
    validate_song_id(song_id)

    song_dir = os.path.join(app.config['PROCESSED_FOLDER'], song_id)
    srt_path = os.path.join(song_dir, 'lyrics.srt')

    if os.path.exists(srt_path):
        with open(srt_path, 'r', encoding='utf-8') as f:
            try:
                content = decrypt_data(f.read())
            except Exception:
                f.seek(0)
                content = f.read()
        return jsonify({'format': 'srt', 'content': content})

    lrc_path = os.path.join(song_dir, 'lyrics.lrc')
    if os.path.exists(lrc_path):
        with open(lrc_path, 'r', encoding='utf-8') as f:
            try:
                content = decrypt_data(f.read())
            except Exception:
                f.seek(0)
                content = f.read()
        return jsonify({'format': 'lrc', 'content': content})

    return jsonify({'error': 'Lyrics not found'}), 404


@app.route('/api/download/<song_id>/<file_type>')
@admin_required_decorator
def download_file(song_id, file_type):
    """Download song files (admin only)"""
    validate_song_id(song_id)

    valid_types = ['original', 'instrumental', 'vocals', 'lyrics']
    if file_type not in valid_types:
        return jsonify({'error': 'Invalid file type'}), 400

    song = get_song_by_id(song_id)
    if not song:
        return jsonify({'error': 'Song not found'}), 404

    title = song[1].replace(' ', '_') if song[1] else song_id

    if file_type == 'original':
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], song[2])
        if not os.path.exists(filepath):
            return jsonify({'error': 'File not found'}), 404
        ext = os.path.splitext(song[2])[1]
        return send_file(filepath, as_attachment=True,
                         download_name=f'{title}_original{ext}')

    if file_type in ('instrumental', 'vocals'):
        for ext in ['.wav', '.mp3']:
            path = os.path.join(app.config['PROCESSED_FOLDER'], song_id, f'{file_type}{ext}')
            if os.path.exists(path):
                return send_file(path, as_attachment=True,
                                 download_name=f'{title}_{file_type}{ext}')
        return jsonify({'error': 'File not found'}), 404

    if file_type == 'lyrics':
        song_dir = os.path.join(app.config['PROCESSED_FOLDER'], song_id)
        for fmt, ext in [('lyrics.srt', '.srt'), ('lyrics.lrc', '.lrc')]:
            fpath = os.path.join(song_dir, fmt)
            if os.path.exists(fpath):
                with open(fpath, 'r', encoding='utf-8') as f:
                    try:
                        content = decrypt_data(f.read())
                    except Exception:
                        f.seek(0)
                        content = f.read()
                from io import BytesIO
                buf = BytesIO(content.encode('utf-8'))
                return send_file(buf, as_attachment=True,
                                 download_name=f'{title}_lyrics{ext}',
                                 mimetype='text/plain')
        return jsonify({'error': 'Lyrics not found'}), 404

    return jsonify({'error': 'Invalid request'}), 400


# ─── CSRF TOKEN API ───────────────────────────────────────────────────────────

@app.route('/api/csrf-token', methods=['GET'])
def get_csrf_token():
    """Return a CSRF token for AJAX requests."""
    return jsonify({'csrf_token': generate_csrf_token()})


# ─── HELPERS ──────────────────────────────────────────────────────────────────

def _seconds_to_srt_time(seconds):
    """Convert seconds (float) to SRT timestamp HH:MM:SS,mmm"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds % 1) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


# ─── ERROR HANDLERS ───────────────────────────────────────────────────────────

@app.errorhandler(400)
def bad_request(e):
    return jsonify({'error': str(e.description) if hasattr(e, 'description') else 'Bad request'}), 400

@app.errorhandler(401)
def unauthorized(e):
    return jsonify({'error': 'Authentication required'}), 401

@app.errorhandler(403)
def forbidden(e):
    return jsonify({'error': str(e.description) if hasattr(e, 'description') else 'Forbidden'}), 403

@app.errorhandler(404)
def not_found(e):
    return jsonify({'error': 'Not found'}), 404

@app.errorhandler(413)
def too_large(e):
    return jsonify({'error': 'File too large (max 100MB)'}), 413

@app.errorhandler(500)
def internal_error(e):
    return jsonify({'error': 'Internal server error'}), 500


# ─── MAIN ─────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    print("Waiting for database...")
    if wait_for_database():
        try:
            init_db()
            print("Database tables created successfully!")
        except Exception as e:
            print(f"Could not initialize database: {e}")
    else:
        print("Warning: Could not connect to database. Starting anyway...")

    debug_mode = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    app.run(debug=debug_mode, host='0.0.0.0', port=5000)
