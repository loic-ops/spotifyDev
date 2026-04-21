# api admin - endpoints mutants proteges par session+csrf
import os, uuid, json, shutil

from flask import Blueprint, request, jsonify, current_app
from werkzeug.utils import secure_filename

from services.auth import admin_required, csrf_protected
from services.security import ( encrypt_data, decrypt_data, validate_song_id, sanitize_text,validate_file_extension, ALLOWED_AUDIO_EXT, ALLOWED_IMAGE_EXT, ALLOWED_LYRICS_EXT,)
from services.lyrics_helpers import save_lyrics_file, seconds_to_srt_time
from lyrics.sync_utils import srt_to_lrc

from database.db_utils import ( add_song, get_song_by_id, delete_song, update_song_title, update_song_status,)

api_admin_bp = Blueprint('api_admin', __name__, url_prefix='/api')


# upload chanson
@api_admin_bp.route('/upload', methods=['POST'])
@admin_required
@csrf_protected
def upload_song():
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    fname = secure_filename(file.filename)
    ext = validate_file_extension(fname, ALLOWED_AUDIO_EXT)
    if not ext:
        return jsonify({'error': 'File type not allowed'}), 400

    song_id = str(uuid.uuid4())
    name = os.path.splitext(fname)[0]
    artist = sanitize_text(request.form.get('artist', 'Unknown Artist'))

    orig_fname = f"{song_id}{ext}"
    orig_path = os.path.join(current_app.config['UPLOAD_FOLDER'], orig_fname)
    file.save(orig_path)

    song_dir = os.path.join(current_app.config['PROCESSED_FOLDER'], song_id)
    os.makedirs(song_dir, exist_ok=True)

    # meta chiffree
    meta = {'artist': artist, 'title': sanitize_text(name)}
    with open(os.path.join(song_dir, 'meta.json'), 'w') as f:
        f.write(encrypt_data(json.dumps(meta)))

    lyrics_db = None
    lf = request.files.get('lyrics_file')
    if lf and lf.filename:
        lext = validate_file_extension(lf.filename, ALLOWED_LYRICS_EXT)
        if lext:
            save_lyrics_file(lf, song_dir)
            lyrics_db = 'lyrics.lrc' if os.path.exists(os.path.join(song_dir, 'lyrics.lrc')) else 'lyrics.srt'

    # cover
    cf = request.files.get('cover_file')
    if cf and cf.filename:
        cext = validate_file_extension(cf.filename, ALLOWED_IMAGE_EXT)
        if cext:
            cf.save(os.path.join(song_dir, f'cover{cext}'))

    try:
        add_song(song_id, name, orig_fname, lyrics_file=lyrics_db)
    except Exception:
        return jsonify({'error': 'Database error'}), 500

    return jsonify({'song_id': song_id, 'title': name, 'artist': artist,
                    'message': 'Song uploaded successfully'})


# upload paroles separement
@api_admin_bp.route('/upload-lyrics/<song_id>', methods=['POST'])
@admin_required
@csrf_protected
def upload_lyrics(song_id):
    validate_song_id(song_id)

    if 'lyrics_file' not in request.files:
        return jsonify({'error': 'No lyrics file provided'}), 400

    lf = request.files['lyrics_file']
    if lf.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    lext = validate_file_extension(lf.filename, ALLOWED_LYRICS_EXT)
    if not lext:
        return jsonify({'error': 'File type not allowed. Use .srt or .lrc'}), 400

    song = get_song_by_id(song_id)
    if not song:
        return jsonify({'error': 'Song not found'}), 404

    song_dir = os.path.join(current_app.config['PROCESSED_FOLDER'], song_id)
    os.makedirs(song_dir, exist_ok=True)
    save_lyrics_file(lf, song_dir)

    lyrics_db = 'lyrics.lrc' if os.path.exists(os.path.join(song_dir, 'lyrics.lrc')) else 'lyrics.srt'
    update_song_status(song_id, song[7] or 'uploaded', lyrics_file=lyrics_db)

    return jsonify({'message': 'Lyrics uploaded successfully'})


# update metadata
@api_admin_bp.route('/songs/<song_id>', methods=['PUT'])
@admin_required
@csrf_protected
def update_song(song_id):
    validate_song_id(song_id)

    song = get_song_by_id(song_id)
    if not song:
        return jsonify({'error': 'Song not found'}), 404

    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    song_dir = os.path.join(current_app.config['PROCESSED_FOLDER'], song_id)
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
    if 'lyrics_offset' in data:
        try:
            meta['lyrics_offset'] = float(data['lyrics_offset'])
        except (TypeError, ValueError):
            pass

    os.makedirs(song_dir, exist_ok=True)
    with open(meta_path, 'w') as f:
        f.write(encrypt_data(json.dumps(meta)))

    # fk columns genre/artist + banner
    if 'genre_id' in data or 'artist_id' in data or 'banner_text' in data:
        from database.db_utils import get_session
        from database.models.song import Song
        sess = get_session()
        try:
            db_song = sess.query(Song).filter_by(id=song_id).first()
            if db_song:
                if 'genre_id' in data:
                    db_song.genre_id = data['genre_id'] or None
                if 'artist_id' in data:
                    db_song.artist_id = data['artist_id'] or None
                if 'banner_text' in data:
                    db_song.banner_text = sanitize_text(data['banner_text']) if data['banner_text'] else None
                sess.commit()
        finally:
            sess.close()

    return jsonify({'message': 'Song updated', 'meta': meta})


# upload cover
@api_admin_bp.route('/upload-cover/<song_id>', methods=['POST'])
@admin_required
@csrf_protected
def upload_cover(song_id):
    validate_song_id(song_id)

    song = get_song_by_id(song_id)
    if not song:
        return jsonify({'error': 'Song not found'}), 404

    cf = request.files.get('cover_file')
    if not cf or not cf.filename:
        return jsonify({'error': 'No cover file provided'}), 400

    cext = validate_file_extension(cf.filename, ALLOWED_IMAGE_EXT)
    if not cext:
        return jsonify({'error': 'File type not allowed (jpg, png, webp)'}), 400

    song_dir = os.path.join(current_app.config['PROCESSED_FOLDER'], song_id)
    os.makedirs(song_dir, exist_ok=True)

    # vire les anciennes covers
    for ext in ['.jpg', '.jpeg', '.png', '.webp']:
        old = os.path.join(song_dir, f'cover{ext}')
        if os.path.exists(old):
            os.remove(old)

    cf.save(os.path.join(song_dir, f'cover{cext}'))
    return jsonify({'message': 'Cover uploaded'})


# separation demucs via rq
@api_admin_bp.route('/separate/<song_id>', methods=['POST'])
@admin_required
@csrf_protected
def separate_audio(song_id):
    validate_song_id(song_id)
    song = get_song_by_id(song_id)
    if not song:
        return jsonify({'error': 'Song not found'}), 404

    from jobs.queue import enqueue_job
    d = request.get_json(silent=True) or {}
    jid = enqueue_job('separate', song_id, payload={'model': d.get('model', 'htdemucs')})
    return jsonify({'message': 'Separation job queued', 'job_id': jid})


# suppression
@api_admin_bp.route('/songs/<song_id>', methods=['DELETE'])
@admin_required
@csrf_protected
def delete_song_api(song_id):
    validate_song_id(song_id)
    try:
        song = get_song_by_id(song_id)
        if not song:
            return jsonify({'error': 'Song not found'}), 404

        orig_path = os.path.join(current_app.config['UPLOAD_FOLDER'], song[2])
        if os.path.exists(orig_path):
            os.remove(orig_path)

        song_dir = os.path.join(current_app.config['PROCESSED_FOLDER'], song_id)
        if os.path.exists(song_dir):
            shutil.rmtree(song_dir)

        delete_song(song_id)
        return jsonify({'message': 'Song deleted'})
    except Exception:
        return jsonify({'error': 'Delete failed'}), 500


# sauvegarde paroles editees
@api_admin_bp.route('/lyrics-save/<song_id>', methods=['PUT'])
@admin_required
@csrf_protected
def save_lyrics(song_id):
    validate_song_id(song_id)
    song = get_song_by_id(song_id)
    if not song:
        return jsonify({'error': 'Song not found'}), 404

    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    segs = data.get('segments', [])
    song_dir = os.path.join(current_app.config['PROCESSED_FOLDER'], song_id)
    os.makedirs(song_dir, exist_ok=True)

    srt_lines = []
    for i, seg in enumerate(segs, 1):
        start = seconds_to_srt_time(seg['time'])
        end = seconds_to_srt_time(seg['end_time'])
        srt_lines.append(f"{i}")
        srt_lines.append(f"{start} --> {end}")
        srt_lines.append(sanitize_text(seg['text']))
        srt_lines.append("")

    srt_content = '\n'.join(srt_lines)

    with open(os.path.join(song_dir, 'lyrics.srt'), 'w', encoding='utf-8') as f:
        f.write(encrypt_data(srt_content))

    lrc = srt_to_lrc(srt_content)
    with open(os.path.join(song_dir, 'lyrics.lrc'), 'w', encoding='utf-8') as f:
        f.write(encrypt_data(lrc))

    update_song_status(song_id, song[7] or 'uploaded', lyrics_file='lyrics.lrc')
    return jsonify({'message': 'Lyrics saved successfully'})


# reduction vocale (legacy)
@api_admin_bp.route('/vocal-reduce/<song_id>', methods=['POST'])
@admin_required
@csrf_protected
def reduce_vocals(song_id):
    validate_song_id(song_id)
    from audio_separator.vocal_reduce import reduce_vocal

    data = request.get_json()
    lvl = data.get('level', 0.5) if data else 0.5
    try:
        lvl = max(0.0, min(1.0, float(lvl)))
    except (ValueError, TypeError):
        lvl = 0.5

    song = get_song_by_id(song_id)
    if not song:
        return jsonify({'error': 'Song not found'}), 404

    instr_path = None
    for ext in ['.wav', '.mp3']:
        p = os.path.join(current_app.config['PROCESSED_FOLDER'], song_id, f'instrumental{ext}')
        if os.path.exists(p):
            instr_path = p
            break

    if not instr_path:
        return jsonify({'error': 'Instrumental not found'}), 400

    orig_path = os.path.join(current_app.config['UPLOAD_FOLDER'], song[2])
    if not os.path.exists(orig_path):
        return jsonify({'error': 'Original file not found'}), 400

    out_path = os.path.join(current_app.config['PROCESSED_FOLDER'], song_id, 'karaoke.wav')
    try:
        reduce_vocal(orig_path, instr_path, out_path, lvl)
        return jsonify({'message': 'Vocal reduced successfully'})
    except Exception:
        return jsonify({'error': 'Vocal reduction failed'}), 500


# transcription whisper via rq
@api_admin_bp.route('/transcribe/<song_id>', methods=['POST'])
@admin_required
@csrf_protected
def transcribe_song(song_id):
    validate_song_id(song_id)
    song = get_song_by_id(song_id)
    if not song:
        return jsonify({'error': 'Song not found'}), 404

    from jobs.queue import enqueue_job
    d = request.get_json() or {}
    mdl = d.get('model', 'base')
    if mdl not in ('tiny', 'base', 'small', 'medium', 'large'):
        mdl = 'base'

    jid = enqueue_job('transcribe', song_id, payload={'model': mdl})
    return jsonify({'message': 'Transcription job queued', 'job_id': jid})


# lyrics brutes (admin only)
@api_admin_bp.route('/lyrics-raw/<song_id>')
@admin_required
def get_lyrics_raw(song_id):
    validate_song_id(song_id)
    song_dir = os.path.join(current_app.config['PROCESSED_FOLDER'], song_id)

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


# download fichiers (admin)
@api_admin_bp.route('/download/<song_id>/<file_type>')
@admin_required
def download_file(song_id, file_type):
    from flask import send_file
    from io import BytesIO

    validate_song_id(song_id)

    if file_type not in ['original', 'instrumental', 'vocals', 'lyrics']:
        return jsonify({'error': 'Invalid file type'}), 400

    song = get_song_by_id(song_id)
    if not song:
        return jsonify({'error': 'Song not found'}), 404

    title = song[1].replace(' ', '_') if song[1] else song_id

    if file_type == 'original':
        fpath = os.path.join(current_app.config['UPLOAD_FOLDER'], song[2])
        if not os.path.exists(fpath):
            return jsonify({'error': 'File not found'}), 404
        ext = os.path.splitext(song[2])[1]
        return send_file(fpath, as_attachment=True, download_name=f'{title}_original{ext}')

    if file_type in ('instrumental', 'vocals'):
        for ext in ['.wav', '.mp3']:
            p = os.path.join(current_app.config['PROCESSED_FOLDER'], song_id, f'{file_type}{ext}')
            if os.path.exists(p):
                return send_file(p, as_attachment=True, download_name=f'{title}_{file_type}{ext}')
        return jsonify({'error': 'File not found'}), 404

    if file_type == 'lyrics':
        sdir = os.path.join(current_app.config['PROCESSED_FOLDER'], song_id)
        for fmt, ext in [('lyrics.srt', '.srt'), ('lyrics.lrc', '.lrc')]:
            fp = os.path.join(sdir, fmt)
            if os.path.exists(fp):
                with open(fp, 'r', encoding='utf-8') as f:
                    try:
                        content = decrypt_data(f.read())
                    except Exception:
                        f.seek(0)
                        content = f.read()
                buf = BytesIO(content.encode('utf-8'))
                return send_file(buf, as_attachment=True,
                                 download_name=f'{title}_lyrics{ext}', mimetype='text/plain')
        return jsonify({'error': 'Lyrics not found'}), 404

    return jsonify({'error': 'Invalid request'}), 400


# jobs status
@api_admin_bp.route('/admin/jobs', methods=['GET'])
@admin_required
def list_jobs():
    from database.db_utils import get_session
    from database.models.job import Job

    s = get_session()
    try:
        q = s.query(Job).order_by(Job.created_at.desc())
        sid = request.args.get('song_id')
        st = request.args.get('status')
        if sid:
            q = q.filter_by(song_id=sid)
        if st:
            q = q.filter_by(status=st)
        jobs = q.limit(100).all()
        return jsonify([{
            'id': j.id, 'type': j.type, 'song_id': j.song_id,
            'status': j.status, 'progress': j.progress,
            'error': j.error, 'result': j.result,
            'created_at': j.created_at.isoformat() if j.created_at else None,
            'started_at': j.started_at.isoformat() if j.started_at else None,
            'finished_at': j.finished_at.isoformat() if j.finished_at else None,
        } for j in jobs])
    finally:
        s.close()


@api_admin_bp.route('/admin/jobs/<job_id>', methods=['GET'])
@admin_required
def get_job(job_id):
    from jobs.queue import get_job_status
    result = get_job_status(job_id)
    if not result:
        return jsonify({'error': 'Job not found'}), 404
    return jsonify(result)


# waveform via rq
@api_admin_bp.route('/admin/songs/<song_id>/waveform', methods=['POST'])
@admin_required
@csrf_protected
def generate_waveform(song_id):
    validate_song_id(song_id)
    song = get_song_by_id(song_id)
    if not song:
        return jsonify({'error': 'Song not found'}), 404

    from jobs.queue import enqueue_job
    jid = enqueue_job('waveform', song_id, payload={})
    return jsonify({'message': 'Waveform job queued', 'job_id': jid})


# alertes

@api_admin_bp.route('/admin/alerts', methods=['GET'])
@admin_required
def list_alerts():
    from database.db_utils import get_session
    from database.models.alert import Alert

    s = get_session()
    try:
        status_filter = request.args.get('status')
        q = s.query(Alert).order_by(Alert.count.desc())
        if status_filter:
            q = q.filter_by(status=status_filter)
        alerts = q.limit(200).all()
        return jsonify([{
            'id': a.id, 'term': a.term, 'normalized_term': a.normalized_term,
            'count': a.count, 'status': a.status,
            'youtube_results': a.youtube_results,
            'first_seen': a.first_seen.isoformat() if a.first_seen else None,
            'last_seen': a.last_seen.isoformat() if a.last_seen else None,
            'resolved_at': a.resolved_at.isoformat() if a.resolved_at else None,
        } for a in alerts])
    finally:
        s.close()


@api_admin_bp.route('/admin/alerts/bulk-delete', methods=['POST'])
@admin_required
@csrf_protected
def bulk_delete_alerts():
    from database.db_utils import get_session
    from database.models.alert import Alert

    data = request.get_json() or {}
    ids = data.get('ids', [])
    if not isinstance(ids, list) or not ids:
        return jsonify({'error': 'ids array required'}), 400

    s = get_session()
    try:
        deleted = s.query(Alert).filter(Alert.id.in_(ids)).delete(synchronize_session=False)
        s.commit()
        return jsonify({'ok': True, 'deleted': deleted})
    finally:
        s.close()


@api_admin_bp.route('/admin/alerts/<int:alert_id>/status', methods=['PATCH'])
@admin_required
@csrf_protected
def update_alert_status(alert_id):
    from database.db_utils import get_session
    from database.models.alert import Alert
    from datetime import datetime

    data = request.get_json()
    if not data or 'status' not in data:
        return jsonify({'error': 'status required'}), 400

    new_st = data['status']
    valid = ('untreated', 'in_progress', 'added', 'unavailable', 'ignored')
    if new_st not in valid:
        return jsonify({'error': f'Invalid status. Must be one of: {valid}'}), 400

    s = get_session()
    try:
        alert = s.query(Alert).filter_by(id=alert_id).first()
        if not alert:
            return jsonify({'error': 'Alert not found'}), 404
        alert.status = new_st
        if new_st in ('added', 'unavailable', 'ignored'):
            alert.resolved_at = datetime.utcnow()
            alert.resolved_by = _get_admin_id()
        s.commit()
        return jsonify({'ok': True})
    finally:
        s.close()


def _get_admin_id():
    from flask import session as flask_session
    return flask_session.get('admin_id')

# keep old name for compatibility
session_admin_id = _get_admin_id


def _slugify(text):
    import re, unicodedata
    text = unicodedata.normalize('NFKD', text or '').encode('ascii', 'ignore').decode('ascii')
    text = re.sub(r'[^\w\s-]', '', text.lower()).strip()
    return re.sub(r'[-\s]+', '-', text)


# genres crud

@api_admin_bp.route('/admin/genres', methods=['GET'])
@admin_required
def list_genres():
    from database.db_utils import get_session
    from database.models.genre import Genre
    from database.models.song import Song
    from sqlalchemy import func

    s = get_session()
    try:
        counts = dict(s.query(Song.genre_id, func.count(Song.id)).group_by(Song.genre_id).all())
        genres = s.query(Genre).order_by(Genre.sort_order, Genre.name).all()
        return jsonify([{
            'id': g.id, 'name': g.name, 'slug': g.slug,
            'color': g.color, 'emoji': g.emoji,
            'sort_order': g.sort_order, 'visible': g.visible,
            'songs_count': counts.get(g.id, 0),
        } for g in genres])
    finally:
        s.close()


@api_admin_bp.route('/admin/genres', methods=['POST'])
@admin_required
@csrf_protected
def create_genre():
    from database.db_utils import get_session
    from database.models.genre import Genre

    data = request.get_json()
    if not data or not data.get('name'):
        return jsonify({'error': 'name required'}), 400

    s = get_session()
    try:
        g = Genre(
            name=sanitize_text(data['name']),
            slug=_slugify(data['name']),
            color=data.get('color', '#7C4DFF'),
            emoji=data.get('emoji', '\U0001f3b5'),
            sort_order=data.get('sort_order', 0),
            visible=data.get('visible', True),
        )
        s.add(g)
        s.commit()
        return jsonify({'id': g.id, 'message': 'Genre created'})
    except Exception as e:
        s.rollback()
        return jsonify({'error': str(e)}), 400
    finally:
        s.close()


@api_admin_bp.route('/admin/genres/<int:genre_id>', methods=['PATCH'])
@admin_required
@csrf_protected
def update_genre(genre_id):
    from database.db_utils import get_session
    from database.models.genre import Genre

    data = request.get_json() or {}
    s = get_session()
    try:
        g = s.query(Genre).filter_by(id=genre_id).first()
        if not g:
            return jsonify({'error': 'Genre not found'}), 404
        for field in ('name', 'color', 'emoji', 'sort_order', 'visible'):
            if field in data:
                setattr(g, field, data[field])
        if 'name' in data:
            g.slug = _slugify(data['name'])
        s.commit()
        return jsonify({'ok': True})
    finally:
        s.close()


@api_admin_bp.route('/admin/genres/<int:genre_id>', methods=['DELETE'])
@admin_required
@csrf_protected
def delete_genre(genre_id):
    from database.db_utils import get_session
    from database.models.genre import Genre

    s = get_session()
    try:
        g = s.query(Genre).filter_by(id=genre_id).first()
        if not g:
            return jsonify({'error': 'Genre not found'}), 404
        s.delete(g)
        s.commit()
        return jsonify({'ok': True})
    finally:
        s.close()


# artistes crud

@api_admin_bp.route('/admin/artists', methods=['GET'])
@admin_required
def list_artists():
    from database.db_utils import get_session
    from database.models.artist import Artist

    s = get_session()
    try:
        artists = s.query(Artist).order_by(Artist.name).all()
        return jsonify([{
            'id': a.id, 'name': a.name, 'slug': a.slug,
            'bio': a.bio, 'photo_path': a.photo_path,
            'socials': a.socials, 'songs_count': a.songs_count or 0,
        } for a in artists])
    finally:
        s.close()


@api_admin_bp.route('/admin/artists', methods=['POST'])
@admin_required
@csrf_protected
def create_artist():
    from database.db_utils import get_session
    from database.models.artist import Artist

    data = request.get_json()
    if not data or not data.get('name'):
        return jsonify({'error': 'name required'}), 400

    s = get_session()
    try:
        a = Artist(
            name=sanitize_text(data['name']), slug=_slugify(data['name']),
            bio=data.get('bio'), photo_path=data.get('photo_path'),
            socials=data.get('socials'),
        )
        s.add(a)
        s.commit()
        return jsonify({'id': a.id, 'message': 'Artist created'})
    except Exception as e:
        s.rollback()
        return jsonify({'error': str(e)}), 400
    finally:
        s.close()


@api_admin_bp.route('/admin/artists/<int:artist_id>', methods=['PATCH'])
@admin_required
@csrf_protected
def update_artist(artist_id):
    from database.db_utils import get_session
    from database.models.artist import Artist

    data = request.get_json() or {}
    s = get_session()
    try:
        a = s.query(Artist).filter_by(id=artist_id).first()
        if not a:
            return jsonify({'error': 'Artist not found'}), 404
        for field in ('name', 'bio', 'photo_path', 'socials'):
            if field in data:
                setattr(a, field, data[field])
        if 'name' in data:
            a.slug = _slugify(data['name'])
        s.commit()
        return jsonify({'ok': True})
    finally:
        s.close()


@api_admin_bp.route('/admin/artists/<int:artist_id>', methods=['DELETE'])
@admin_required
@csrf_protected
def delete_artist(artist_id):
    from database.db_utils import get_session
    from database.models.artist import Artist

    s = get_session()
    try:
        a = s.query(Artist).filter_by(id=artist_id).first()
        if not a:
            return jsonify({'error': 'Artist not found'}), 404
        s.delete(a)
        s.commit()
        return jsonify({'ok': True})
    finally:
        s.close()


# playlists crud

@api_admin_bp.route('/admin/playlists', methods=['GET'])
@admin_required
def list_playlists():
    from database.db_utils import get_session
    from database.models.playlist import Playlist, PlaylistSong

    s = get_session()
    try:
        pls = s.query(Playlist).order_by(Playlist.sort_order, Playlist.name).all()
        result = []
        for p in pls:
            cnt = s.query(PlaylistSong).filter_by(playlist_id=p.id).count()
            result.append({
                'id': p.id, 'name': p.name, 'description': p.description,
                'cover_path': p.cover_path, 'editorial': p.editorial,
                'sort_order': p.sort_order, 'visible': p.visible,
                'song_count': cnt,
            })
        return jsonify(result)
    finally:
        s.close()


@api_admin_bp.route('/admin/playlists', methods=['POST'])
@admin_required
@csrf_protected
def create_playlist():
    from database.db_utils import get_session
    from database.models.playlist import Playlist

    data = request.get_json()
    if not data or not data.get('name'):
        return jsonify({'error': 'name required'}), 400

    s = get_session()
    try:
        pl = Playlist(
            name=sanitize_text(data['name']),
            description=data.get('description'),
            cover_path=data.get('cover_path'),
            editorial=data.get('editorial', True),
            sort_order=data.get('sort_order', 0),
            visible=data.get('visible', True),
            created_by=_get_admin_id(),
        )
        s.add(pl)
        s.commit()
        return jsonify({'id': pl.id, 'message': 'Playlist created'})
    finally:
        s.close()


@api_admin_bp.route('/admin/playlists/<int:playlist_id>', methods=['GET'])
@admin_required
def get_playlist(playlist_id):
    from database.db_utils import get_session
    from database.models.playlist import Playlist, PlaylistSong

    s = get_session()
    try:
        pl = s.query(Playlist).filter_by(id=playlist_id).first()
        if not pl:
            return jsonify({'error': 'Playlist not found'}), 404
        songs = s.query(PlaylistSong).filter_by(playlist_id=playlist_id).order_by(PlaylistSong.position).all()
        return jsonify({
            'id': pl.id, 'name': pl.name, 'description': pl.description,
            'cover_path': pl.cover_path, 'visible': pl.visible,
            'songs': [{'song_id': x.song_id, 'position': x.position} for x in songs],
        })
    finally:
        s.close()


@api_admin_bp.route('/admin/playlists/<int:playlist_id>', methods=['PATCH'])
@admin_required
@csrf_protected
def update_playlist(playlist_id):
    from database.db_utils import get_session
    from database.models.playlist import Playlist

    data = request.get_json() or {}
    s = get_session()
    try:
        pl = s.query(Playlist).filter_by(id=playlist_id).first()
        if not pl:
            return jsonify({'error': 'Playlist not found'}), 404
        for field in ('name', 'description', 'cover_path', 'sort_order', 'visible'):
            if field in data:
                setattr(pl, field, data[field])
        s.commit()
        return jsonify({'ok': True})
    finally:
        s.close()


@api_admin_bp.route('/admin/playlists/<int:playlist_id>', methods=['DELETE'])
@admin_required
@csrf_protected
def delete_playlist(playlist_id):
    from database.db_utils import get_session
    from database.models.playlist import Playlist

    s = get_session()
    try:
        pl = s.query(Playlist).filter_by(id=playlist_id).first()
        if not pl:
            return jsonify({'error': 'Playlist not found'}), 404
        s.delete(pl)
        s.commit()
        return jsonify({'ok': True})
    finally:
        s.close()


@api_admin_bp.route('/admin/playlists/<int:playlist_id>/songs', methods=['PUT'])
@admin_required
@csrf_protected
def update_playlist_songs(playlist_id):
    from database.db_utils import get_session
    from database.models.playlist import Playlist, PlaylistSong

    data = request.get_json() or {}
    song_ids = data.get('song_ids', [])

    s = get_session()
    try:
        pl = s.query(Playlist).filter_by(id=playlist_id).first()
        if not pl:
            return jsonify({'error': 'Playlist not found'}), 404
        s.query(PlaylistSong).filter_by(playlist_id=playlist_id).delete()
        for i, sid in enumerate(song_ids):
            s.add(PlaylistSong(playlist_id=playlist_id, song_id=sid, position=i))
        s.commit()
        return jsonify({'ok': True, 'count': len(song_ids)})
    finally:
        s.close()


# analytics

@api_admin_bp.route('/admin/analytics/overview', methods=['GET'])
@admin_required
def analytics_overview():
    from database.db_utils import get_session
    from database.models.song import Song
    from database.models.search_log import SearchLog
    from database.models.alert import Alert
    from sqlalchemy import func

    s = get_session()
    try:
        total = s.query(Song).count()
        ready = s.query(Song).filter(
            Song.lyrics_file.isnot(None), Song.instrumental_file.isnot(None)
        ).count()

        from datetime import datetime, timedelta
        week_ago = datetime.utcnow() - timedelta(days=7)
        top_searches = s.query(
            SearchLog.normalized_term,
            func.count(SearchLog.id).label('cnt')
        ).filter(SearchLog.ts >= week_ago).group_by(
            SearchLog.normalized_term
        ).order_by(func.count(SearchLog.id).desc()).limit(10).all()

        from sqlalchemy import case
        top_played = s.query(Song).order_by(
            case((Song.plays_count.is_(None), 0), else_=Song.plays_count).desc()
        ).limit(10).all()

        alerts_pending = s.query(Alert).filter_by(status='untreated').count()

        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        searches_today = s.query(SearchLog).filter(SearchLog.ts >= today_start).count()
        miss_today = s.query(SearchLog).filter(SearchLog.ts >= today_start, SearchLog.found == False).count()

        return jsonify({
            'total_songs': total, 'karaoke_ready': ready,
            'alerts_untreated': alerts_pending,
            'searches_today': searches_today,
            'searches_miss_today': miss_today,
            'top_searches': [{'term': t.normalized_term, 'count': t.cnt} for t in top_searches],
            'top_played': [{'id': x.id, 'title': x.title, 'plays': x.plays_count or 0} for x in top_played],
        })
    finally:
        s.close()


# Global ads API (CRUD)
@api_admin_bp.route('/admin/ads', methods=['GET', 'POST'])
@admin_required
@csrf_protected
def manage_ads():
    """GET: liste toutes les pubs | POST: crée une nouvelle pub"""
    if request.method == 'GET':
        from database.db_utils import get_all_ads
        ads = get_all_ads()
        return jsonify({'ads': ads})
    
    # POST
    data = request.get_json() or {}
    from database.db_utils import create_ad
    result = create_ad(data)
    return jsonify(result), 201


@api_admin_bp.route('/admin/ads/<int:ad_id>', methods=['GET', 'PUT', 'DELETE'])
@admin_required
@csrf_protected
def manage_ad_detail(ad_id):
    """GET: récupère une pub | PUT: met à jour | DELETE: supprime"""
    from database.db_utils import get_all_ads, update_ad, delete_ad
    
    if request.method == 'GET':
        ads = get_all_ads()
        ad = next((a for a in ads if a['id'] == ad_id), None)
        if not ad:
            return jsonify({'error': 'Ad not found'}), 404
        return jsonify(ad)
    
    if request.method == 'PUT':
        data = request.get_json() or {}
        result = update_ad(ad_id, data)
        if not result:
            return jsonify({'error': 'Ad not found'}), 404
        return jsonify(result)
    
    if request.method == 'DELETE':
        if delete_ad(ad_id):
            return jsonify({'status': 'deleted'}), 204
        return jsonify({'error': 'Ad not found'}), 404


@api_admin_bp.route('/ads/active')
def get_active_ad_api():
    """Récupère la pub ACTIVE (sans authentification, pour le player)"""
    from database.db_utils import get_active_ad
    ad = get_active_ad()
    return jsonify(ad or {})

