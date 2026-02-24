import os
import uuid
import json
import time
from flask import Flask, render_template, request, jsonify, send_file, session, redirect, url_for
from werkzeug.utils import secure_filename
from config import Config
from lyrics.sync_utils import parse_lrc, parse_srt, srt_to_lrc
from database.db_utils import init_db, add_song, get_all_songs, get_song_by_id, delete_song

app = Flask(__name__)
app.config.from_object(Config)

# Ensure upload directories exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['PROCESSED_FOLDER'], exist_ok=True)


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


# ─── PLAYER INTERFACE (Spotify-like) ─────────────────────────────────────────

@app.route('/')
def player():
    return render_template('player.html')


# ─── ADMIN AUTH ─────────────────────────────────────────────────────────────

def admin_required():
    if not session.get('admin_auth'):
        return redirect(url_for('admin_login'))
    return None


@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    error = None
    if request.method == 'POST':
        code = request.form.get('code', '')
        if code == app.config.get('ADMIN_CODE', '1234'):
            session['admin_auth'] = True
            return redirect(url_for('admin'))
        error = 'Code incorrect'
    return render_template('admin_login.html', error=error)


@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_auth', None)
    return redirect(url_for('player'))


# ─── ADMIN INTERFACE ─────────────────────────────────────────────────────────

@app.route('/admin')
def admin():
    auth_check = admin_required()
    if auth_check:
        return auth_check
    return render_template('admin.html')


@app.route('/admin/upload')
def admin_upload():
    auth_check = admin_required()
    if auth_check:
        return auth_check
    return render_template('admin_upload.html')


# ─── API ENDPOINTS ───────────────────────────────────────────────────────────

@app.route('/api/upload', methods=['POST'])
def upload_song():
    """Handle song upload with optional lyrics (SRT or LRC)"""
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    song_id = str(uuid.uuid4())
    filename = secure_filename(file.filename)
    name, ext = os.path.splitext(filename)
    artist = request.form.get('artist', 'Unknown Artist')

    # Save original file
    original_filename = f"{song_id}{ext}"
    original_path = os.path.join(app.config['UPLOAD_FOLDER'], original_filename)
    file.save(original_path)

    # Create processed directory
    song_dir = os.path.join(app.config['PROCESSED_FOLDER'], song_id)
    os.makedirs(song_dir, exist_ok=True)

    # Save metadata
    meta_path = os.path.join(song_dir, 'meta.json')
    with open(meta_path, 'w') as f:
        json.dump({'artist': artist, 'title': name}, f)

    # Handle lyrics file (SRT or LRC)
    lyrics_file = request.files.get('lyrics_file')
    if lyrics_file and lyrics_file.filename:
        _save_lyrics_file(lyrics_file, song_dir)

    # Handle cover image
    cover_file = request.files.get('cover_file')
    if cover_file and cover_file.filename:
        cover_ext = os.path.splitext(cover_file.filename)[1]
        cover_file.save(os.path.join(song_dir, f'cover{cover_ext}'))

    try:
        add_song(song_id, name, original_filename)
    except Exception as e:
        return jsonify({'error': f'Database error: {str(e)}'}), 500

    return jsonify({
        'song_id': song_id, 'title': name, 'artist': artist,
        'message': 'Song uploaded successfully'
    })


def _save_lyrics_file(lyrics_file, song_dir):
    """Save a lyrics file (SRT or LRC) and ensure both formats exist."""
    content = lyrics_file.read().decode('utf-8')
    fname = lyrics_file.filename.lower()

    if fname.endswith('.srt'):
        with open(os.path.join(song_dir, 'lyrics.srt'), 'w', encoding='utf-8') as f:
            f.write(content)
        lrc_content = srt_to_lrc(content)
        with open(os.path.join(song_dir, 'lyrics.lrc'), 'w', encoding='utf-8') as f:
            f.write(lrc_content)
    elif fname.endswith('.lrc'):
        with open(os.path.join(song_dir, 'lyrics.lrc'), 'w', encoding='utf-8') as f:
            f.write(content)
    else:
        # Try to detect format
        if '-->' in content:
            with open(os.path.join(song_dir, 'lyrics.srt'), 'w', encoding='utf-8') as f:
                f.write(content)
            lrc_content = srt_to_lrc(content)
            with open(os.path.join(song_dir, 'lyrics.lrc'), 'w', encoding='utf-8') as f:
                f.write(lrc_content)
        else:
            with open(os.path.join(song_dir, 'lyrics.lrc'), 'w', encoding='utf-8') as f:
                f.write(content)


@app.route('/api/upload-lyrics/<song_id>', methods=['POST'])
def upload_lyrics(song_id):
    """Upload lyrics (SRT or LRC) for an existing song"""
    if 'lyrics_file' not in request.files:
        return jsonify({'error': 'No lyrics file provided'}), 400

    lyrics_file = request.files['lyrics_file']
    if lyrics_file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    song = get_song_by_id(song_id)
    if not song:
        return jsonify({'error': 'Song not found'}), 404

    song_dir = os.path.join(app.config['PROCESSED_FOLDER'], song_id)
    os.makedirs(song_dir, exist_ok=True)

    _save_lyrics_file(lyrics_file, song_dir)
    return jsonify({'message': 'Lyrics uploaded successfully'})


@app.route('/api/songs/<song_id>', methods=['PUT'])
def update_song(song_id):
    """Update song metadata (title, artist)"""
    song = get_song_by_id(song_id)
    if not song:
        return jsonify({'error': 'Song not found'}), 404

    data = request.get_json()
    song_dir = os.path.join(app.config['PROCESSED_FOLDER'], song_id)
    meta_path = os.path.join(song_dir, 'meta.json')

    meta = {}
    if os.path.exists(meta_path):
        with open(meta_path, 'r') as f:
            meta = json.load(f)

    if 'title' in data:
        meta['title'] = data['title']
    if 'artist' in data:
        meta['artist'] = data['artist']

    os.makedirs(song_dir, exist_ok=True)
    with open(meta_path, 'w') as f:
        json.dump(meta, f)

    return jsonify({'message': 'Song updated', 'meta': meta})


@app.route('/api/separate/<song_id>', methods=['POST'])
def separate_audio(song_id):
    """Separate vocals from instrumental using Demucs"""
    song = get_song_by_id(song_id)
    if not song:
        return jsonify({'error': 'Song not found'}), 404

    original_path = os.path.join(app.config['UPLOAD_FOLDER'], song[2])
    output_dir = os.path.join(app.config['PROCESSED_FOLDER'], song_id)

    try:
        from audio_separator.demucs_utils import separate_audio_demucs
        separate_audio_demucs(original_path, output_dir)
        return jsonify({'message': 'Audio separated successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500



@app.route('/api/songs', methods=['GET'])
def list_songs():
    """Get all uploaded songs with metadata"""
    try:
        songs = get_all_songs()
        result = []
        for s in songs:
            song_dir = os.path.join(app.config['PROCESSED_FOLDER'], s[0])

            artist = 'Unknown Artist'
            meta_path = os.path.join(song_dir, 'meta.json')
            if os.path.exists(meta_path):
                with open(meta_path, 'r') as f:
                    meta = json.load(f)
                    artist = meta.get('artist', 'Unknown Artist')

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
                'id': s[0], 'title': s[1], 'artist': artist,
                'original_file': s[2], 'has_cover': has_cover,
                'has_lyrics': has_lyrics, 'has_instrumental': has_instrumental,
                'has_vocals': has_vocals
            })

        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/audio/<song_id>/<track_type>')
def stream_audio(song_id, track_type):
    """Stream audio file"""
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
    song_dir = os.path.join(app.config['PROCESSED_FOLDER'], song_id)
    for ext in ['.jpg', '.jpeg', '.png', '.webp']:
        cover_path = os.path.join(song_dir, f'cover{ext}')
        if os.path.exists(cover_path):
            return send_file(cover_path)
    return jsonify({'error': 'No cover art'}), 404


@app.route('/api/lyrics/<song_id>')
def get_lyrics(song_id):
    song_dir = os.path.join(app.config['PROCESSED_FOLDER'], song_id)

    lrc_path = os.path.join(song_dir, 'lyrics.lrc')
    if os.path.exists(lrc_path):
        with open(lrc_path, 'r', encoding='utf-8') as f:
            lrc_content = f.read()
        segments = parse_lrc(lrc_content)
        return jsonify({'segments': segments, 'lrc': lrc_content})

    srt_path = os.path.join(song_dir, 'lyrics.srt')
    if os.path.exists(srt_path):
        with open(srt_path, 'r', encoding='utf-8') as f:
            srt_content = f.read()
        segments = parse_srt(srt_content)
        return jsonify({'segments': segments})

    return jsonify({'error': 'Lyrics not found'}), 404


@app.route('/api/vocal-reduce/<song_id>', methods=['POST'])
def reduce_vocals(song_id):
    from audio_separator.vocal_reduce import reduce_vocal

    data = request.get_json()
    reduction_level = data.get('level', 0.5)

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
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/songs/<song_id>', methods=['DELETE'])
def delete_song_api(song_id):
    import shutil
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
    except Exception as e:
        return jsonify({'error': str(e)}), 500


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

    app.run(debug=True, host='0.0.0.0', port=5000)
