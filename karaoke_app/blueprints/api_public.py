# api publique consommee par electron
import os, re, json, uuid, subprocess, logging

from flask import Blueprint, request, jsonify, send_file, current_app

from services.security import (encrypt_data, decrypt_data, validate_song_id, sanitize_text)
from services.rate_limit import check_api_rate
from services.auth import generate_csrf_token
from lyrics.sync_utils import parse_lrc, parse_srt
from database.db_utils import (get_all_songs, get_song_by_id, add_song, update_song_status)

log = logging.getLogger('karaoking')

api_public_bp = Blueprint('api_public', __name__)


@api_public_bp.route('/api/songs', methods=['GET'])
def list_songs():
    try:
        from database.db_utils import get_session
        from database.models.song import Song

        genre_id = request.args.get('genre_id', type=int)
        artist_id = request.args.get('artist_id', type=int)

        s = get_session()
        try:
            q = s.query(Song.id, Song.title, Song.original_file, Song.instrumental_file,
                        Song.vocals_file, Song.lyrics_file, Song.created_at, Song.status,
                        Song.source, Song.source_url, Song.artist_id, Song.genre_id,
                        Song.language, Song.album, Song.cover_path, Song.published_at,
                        Song.soft_disabled, Song.plays_count, Song.likes_count, Song.duration_sec,
                        Song.id3_raw, Song.banner_text, Song.created_by).order_by(Song.created_at.desc())
            if genre_id:
                q = q.filter(Song.genre_id == genre_id)
            if artist_id:
                q = q.filter(Song.artist_id == artist_id)
            db_songs = q.all()
        finally:
            s.close()

        # Pré-charger les noms d'artistes pour les songs avec artist_id
        artist_ids = {s.artist_id for s in db_songs if s.artist_id}
        artist_names = {}
        if artist_ids:
            from database.models.artist import Artist
            s2 = get_session()
            try:
                for a in s2.query(Artist).filter(Artist.id.in_(artist_ids)).all():
                    artist_names[a.id] = a.name
            finally:
                s2.close()

        result = []
        for song in db_songs:
            song_dir = os.path.join(current_app.config['PROCESSED_FOLDER'], song.id)

            title = song.title
            artist = artist_names.get(song.artist_id, 'Unknown Artist')
            duration = song.duration_sec or 0
            lyrics_offset = 0
            meta_path = os.path.join(song_dir, 'meta.json')
            if os.path.exists(meta_path):
                try:
                    with open(meta_path, 'r') as f:
                        meta = json.loads(decrypt_data(f.read()))
                        artist = meta.get('artist', artist)
                        title = meta.get('title', title)
                        duration = meta.get('duration', duration)
                        lyrics_offset = meta.get('lyrics_offset', 0)
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
            has_instr = any(os.path.exists(os.path.join(song_dir, f'instrumental{e}'))
                           for e in ['.wav', '.mp3'])
            has_vocals = any(os.path.exists(os.path.join(song_dir, f'vocals{e}'))
                            for e in ['.wav', '.mp3'])

            result.append({
                'id': song.id, 'title': title, 'artist': artist,
                'original_file': song.original_file,
                'banner_text': song.banner_text,
                'status': song.status or 'uploaded',
                'duration': duration, 'lyrics_offset': lyrics_offset,
                'genre_id': song.genre_id, 'artist_id': song.artist_id,
                'has_cover': has_cover, 'has_lyrics': has_lyrics,
                'has_instrumental': has_instr, 'has_vocals': has_vocals,
            })

        return jsonify(result)
    except Exception as e:
        log.error(f"list_songs error: {e}")
        return jsonify({'error': 'Failed to load songs'}), 500


@api_public_bp.route('/api/audio/<song_id>/<track_type>')
def stream_audio(song_id, track_type):
    validate_song_id(song_id)

    if track_type not in ['original', 'instrumental', 'vocals']:
        return jsonify({'error': 'Invalid track type'}), 400

    if track_type == 'original':
        song = get_song_by_id(song_id)
        if not song:
            return jsonify({'error': 'Song not found'}), 404
        fpath = os.path.join(current_app.config['UPLOAD_FOLDER'], song[2])
        if not os.path.exists(fpath):
            return jsonify({'error': 'Audio file not found'}), 404
    else:
        fpath = None
        for ext in ['.wav', '.mp3']:
            p = os.path.join(current_app.config['PROCESSED_FOLDER'], song_id, f'{track_type}{ext}')
            if os.path.exists(p):
                fpath = p
                break
        if not fpath:
            return jsonify({'error': 'Audio file not found'}), 404

    mime = 'audio/wav' if fpath.endswith('.wav') else 'audio/mpeg'
    return send_file(fpath, mimetype=mime, conditional=True)


@api_public_bp.route('/api/cover/<song_id>')
def get_cover(song_id):
    validate_song_id(song_id)
    song_dir = os.path.join(current_app.config['PROCESSED_FOLDER'], song_id)
    for ext in ['.jpg', '.jpeg', '.png', '.webp']:
        p = os.path.join(song_dir, f'cover{ext}')
        if os.path.exists(p):
            return send_file(p)
    return jsonify({'error': 'No cover art'}), 404


@api_public_bp.route('/api/lyrics/<song_id>')
def get_lyrics(song_id):
    validate_song_id(song_id)
    song_dir = os.path.join(current_app.config['PROCESSED_FOLDER'], song_id)

    lrc_path = os.path.join(song_dir, 'lyrics.lrc')
    if os.path.exists(lrc_path):
        with open(lrc_path, 'r', encoding='utf-8') as f:
            try:
                content = decrypt_data(f.read())
            except Exception:
                f.seek(0)
                content = f.read()
        segs = parse_lrc(content)
        return jsonify({'segments': segs, 'lrc': content})

    srt_path = os.path.join(song_dir, 'lyrics.srt')
    if os.path.exists(srt_path):
        with open(srt_path, 'r', encoding='utf-8') as f:
            try:
                content = decrypt_data(f.read())
            except Exception:
                f.seek(0)
                content = f.read()
        return jsonify({'segments': parse_srt(content)})

    return jsonify({'error': 'Lyrics not found'}), 404


# recherche youtube
@api_public_bp.route('/api/yt-search', methods=['GET'])
def yt_search():
    if check_api_rate(request.remote_addr, limit=20, window=60):
        return jsonify({'error': 'Too many requests'}), 429
    query = request.args.get('q', '').strip()
    if not query or len(query) > 200:
        return jsonify({'error': 'Invalid query'}), 400

    try:
        cmd = [
            'yt-dlp', '--dump-json', '--default-search', 'ytsearch5',
            '--no-playlist', '--no-warnings', '--flat-playlist',
            '--', f'ytsearch5:{query}'
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        if res.returncode != 0:
            return jsonify({'error': 'YouTube search failed'}), 502

        results = []
        for line in res.stdout.strip().split('\n'):
            if not line:
                continue
            try:
                d = json.loads(line)
                results.append({
                    'id': d.get('id', ''),
                    'title': d.get('title', ''),
                    'channel': d.get('channel', d.get('uploader', '')),
                    'duration': d.get('duration', 0),
                    'thumbnail': d.get('thumbnail', ''),
                    'url': f"https://www.youtube.com/watch?v={d.get('id', '')}"
                })
            except json.JSONDecodeError:
                continue
        return jsonify(results)

    except subprocess.TimeoutExpired:
        return jsonify({'error': 'Search timed out'}), 504
    except FileNotFoundError:
        return jsonify({'error': 'yt-dlp not installed on server'}), 500
    except Exception as e:
        log.error(f"yt-search error: {e}")
        return jsonify({'error': 'Search failed'}), 500


_YT_SUFFIXES = [
    '(Official Video)', '(Official Music Video)', '(Lyrics)',
    '(Official Audio)', '[Official Video]', '[Official Music Video]',
    '(Clip Officiel)', '(Audio)', '(Visualizer)',
    '(Official Lyric Video)', '(Paroles/Lyrics)', '(MV)',
]

def _parse_yt_title(yt_title, yt_uploader):
    for sep in [' - ', ' \u2013 ', ' \u2014 ', ' | ']:
        if sep in yt_title:
            parts = yt_title.split(sep, 1)
            a = parts[0].strip()
            t = parts[1].strip()
            for suf in _YT_SUFFIXES:
                t = t.replace(suf, '').strip()
            return t, a

    t = yt_title
    for suf in _YT_SUFFIXES:
        t = t.replace(suf, '').strip()
    a = yt_uploader or 'Unknown Artist'
    for suf in [' - Topic', 'VEVO', ' Official']:
        a = a.replace(suf, '').strip()
    return t, a


# download youtube + import
@api_public_bp.route('/api/yt-download', methods=['POST'])
def yt_download():
    # TODO: passer en file rq quand device-token sera pret
    if check_api_rate(request.remote_addr, limit=10, window=300):
        return jsonify({'error': 'Too many downloads, please wait'}), 429
    try:
        data = request.get_json(silent=True)
        if not data or not data.get('url'):
            return jsonify({'error': 'URL required'}), 400

        yt_url = data['url']
        log.info(f"yt-download: starting download for {yt_url}")

        if not re.match(r'^https?://(www\.)?(youtube\.com|youtu\.be|music\.youtube\.com)/[a-zA-Z0-9_\-?&=%./]*$', yt_url):
            log.info(f"yt-download: invalid URL: {yt_url}")
            return jsonify({'error': 'Invalid YouTube URL'}), 400

        song_id = str(uuid.uuid4())
        upload_dir = current_app.config['UPLOAD_FOLDER']
        output_path = os.path.join(upload_dir, f"{song_id}.%(ext)s")
        thumb_dir = os.path.join(current_app.config['PROCESSED_FOLDER'], song_id)
        os.makedirs(thumb_dir, exist_ok=True)

        cmd = [
            'yt-dlp',
            '--extract-audio', '--audio-format', 'mp3',
            '--audio-quality', '0',
            '-o', output_path,
            '--write-thumbnail', '--convert-thumbnails', 'jpg',
            '-o', f'thumbnail:{os.path.join(thumb_dir, "cover.%(ext)s")}',
            '--print', 'after_move:filepath',
            '--print', '%(title)s|||%(uploader)s|||%(duration)s',
            '--no-playlist', '--', yt_url
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

        if res.returncode != 0:
            log.info(f"yt-download: yt-dlp failed, stderr={res.stderr}")
            return jsonify({'error': 'Download failed'}), 502

        stdout_lines = [l.strip() for l in res.stdout.strip().split('\n') if l.strip()]

        downloaded = None
        yt_title = 'Unknown'
        yt_uploader = 'Unknown Artist'
        yt_duration = 0

        for line in stdout_lines:
            if '|||' in line:
                parts = line.split('|||')
                yt_title = parts[0].strip()
                yt_uploader = parts[1].strip() if len(parts) > 1 else 'Unknown Artist'
                try:
                    yt_duration = int(float(parts[2].strip())) if len(parts) > 2 else 0
                except (ValueError, IndexError):
                    yt_duration = 0
            elif os.path.sep in line or line.endswith('.mp3') or line.endswith('.m4a') or line.endswith('.webm') or line.endswith('.opus'):
                downloaded = line

        title, artist = _parse_yt_title(yt_title, yt_uploader)

        if not downloaded or not os.path.exists(downloaded):
            for f in os.listdir(upload_dir):
                if f.startswith(song_id):
                    downloaded = os.path.join(upload_dir, f)
                    break

        if not downloaded or not os.path.exists(downloaded):
            return jsonify({'error': 'Download file not found'}), 500

        orig_fname = os.path.basename(downloaded)
        song_dir = os.path.join(current_app.config['PROCESSED_FOLDER'], song_id)
        os.makedirs(song_dir, exist_ok=True)

        # renomme thumbnails (yt-dlp ecrit parfois cover.jpg.jpg)
        for f in os.listdir(song_dir):
            if f.startswith('cover') and not f.startswith('cover.'):
                ext = os.path.splitext(f)[1]
                proper = os.path.join(song_dir, f'cover{ext}')
                if os.path.join(song_dir, f) != proper:
                    os.rename(os.path.join(song_dir, f), proper)
                break

        meta = {'artist': sanitize_text(artist), 'title': sanitize_text(title), 'duration': yt_duration}
        with open(os.path.join(song_dir, 'meta.json'), 'w') as f:
            f.write(encrypt_data(json.dumps(meta)))

        add_song(song_id, sanitize_text(title), orig_fname)
        update_song_status(song_id, 'youtube')

        log.info(f"yt-download: success! {title} - {artist} ({song_id})")
        return jsonify({
            'song_id': song_id, 'title': title, 'artist': artist,
            'message': 'Song downloaded and imported'
        })

    except subprocess.TimeoutExpired:
        return jsonify({'error': 'Download timed out (5min max)'}), 504
    except FileNotFoundError:
        return jsonify({'error': 'yt-dlp not installed on server'}), 500
    except Exception:
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Internal error'}), 500


# search log pour les alertes
@api_public_bp.route('/api/search-log', methods=['POST'])
def log_search():
    if check_api_rate(request.remote_addr, limit=60, window=60):
        return jsonify({'error': 'Too many requests'}), 429

    data = request.get_json(silent=True)
    if not data or not data.get('term'):
        return jsonify({'error': 'term required'}), 400

    term = data['term'].strip()[:255]
    found = bool(data.get('found', False))

    try:
        from database.db_utils import get_session
        from database.models.search_log import SearchLog
        import unicodedata

        normalized = unicodedata.normalize('NFKD', term.lower()).encode('ascii', 'ignore').decode('ascii').strip()

        s = get_session()
        try:
            entry = SearchLog(term=term, normalized_term=normalized,
                              found=found, ip=request.remote_addr)
            s.add(entry)
            s.commit()
        finally:
            s.close()

        # pas trouve -> upsert alert + push sse
        if not found:
            from database.models.alert import Alert
            from services.sse import publish_event
            s = get_session()
            try:
                alert = s.query(Alert).filter_by(normalized_term=normalized).first()
                is_new = alert is None
                if alert:
                    alert.count += 1
                else:
                    alert = Alert(term=term, normalized_term=normalized,
                                  count=1, status='untreated')
                    s.add(alert)
                s.commit()
                publish_event('alert.new' if is_new else 'alert.update', {
                    'id': alert.id, 'term': alert.term,
                    'count': alert.count, 'status': alert.status,
                })
            finally:
                s.close()

        return jsonify({'ok': True})
    except Exception as e:
        log.error(f"search-log error: {e}")
        return jsonify({'error': 'Internal error'}), 500


@api_public_bp.route('/api/play-log', methods=['POST'])
def log_play():
    data = request.get_json(silent=True)
    if not data or not data.get('song_id'):
        return jsonify({'error': 'song_id required'}), 400

    sid = data['song_id'].strip()
    try:
        from database.db_utils import get_session
        from database.models.song import Song
        s = get_session()
        try:
            song = s.query(Song).filter_by(id=sid).first()
            if song:
                song.plays_count = (song.plays_count or 0) + 1
                s.commit()
                return jsonify({'ok': True, 'plays': song.plays_count})
            return jsonify({'error': 'Song not found'}), 404
        finally:
            s.close()
    except Exception as e:
        log.error(f"play-log error: {e}")
        return jsonify({'error': 'Internal error'}), 500


# catalogue public (electron)

@api_public_bp.route('/api/genres', methods=['GET'])
def list_public_genres():
    from database.db_utils import get_session
    from database.models.genre import Genre
    s = get_session()
    try:
        genres = s.query(Genre).filter_by(visible=True).order_by(Genre.sort_order, Genre.name).all()
        return jsonify([{'id': g.id, 'name': g.name, 'slug': g.slug,
                         'color': g.color, 'emoji': g.emoji} for g in genres])
    finally:
        s.close()


@api_public_bp.route('/api/playlists', methods=['GET'])
def list_public_playlists():
    from database.db_utils import get_session
    from database.models.playlist import Playlist
    s = get_session()
    try:
        pls = s.query(Playlist).filter_by(visible=True).order_by(Playlist.sort_order).all()
        return jsonify([{'id': p.id, 'name': p.name, 'description': p.description,
                         'cover_path': p.cover_path} for p in pls])
    finally:
        s.close()


@api_public_bp.route('/api/artists', methods=['GET'])
def list_public_artists():
    from database.db_utils import get_session
    from database.models.artist import Artist
    s = get_session()
    try:
        artists = s.query(Artist).order_by(Artist.name).all()
        return jsonify([{'id': a.id, 'name': a.name, 'slug': a.slug,
                         'photo_path': a.photo_path,
                         'songs_count': a.songs_count or 0} for a in artists])
    finally:
        s.close()


@api_public_bp.route('/api/csrf-token', methods=['GET'])
def get_csrf_token():
    return jsonify({'csrf_token': generate_csrf_token()})


@api_public_bp.route('/health')
def health():
    try:
        from database.db_utils import get_session
        from sqlalchemy import text
        s = get_session()
        s.execute(text('SELECT 1'))
        s.close()
        return jsonify({'status': 'healthy'}), 200
    except Exception:
        return jsonify({'status': 'unhealthy'}), 503
