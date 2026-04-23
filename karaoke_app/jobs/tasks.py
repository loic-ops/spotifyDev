# taches rq - demucs, whisper, yt-dlp
import os
import re
import json
import uuid
import subprocess
import logging
from datetime import datetime

from config import Config
from database.db_utils import get_session, update_song_status
from database.models.job import Job
from services.security import encrypt_data, sanitize_text

log = logging.getLogger('rq.tasks')


def _update_job(job_id, **kw):
    s = get_session()
    try:
        j = s.query(Job).filter_by(id=job_id).first()
        if j:
            for k, v in kw.items():
                setattr(j, k, v)
            s.commit()
    finally:
        s.close()


def _fail_job(job_id, err_msg):
    _update_job(job_id, status='failed', error=str(err_msg)[:4000],
                finished_at=datetime.utcnow())
    log.error(f"Job {job_id} failed: {err_msg}")
    try:
        from services.sse import publish_event
        publish_event('job.failed', {'job_id': job_id, 'error': str(err_msg)[:200]})
    except Exception:
        pass


def _publish_done(job_id, song_id, job_type, title=None):
    try:
        from services.sse import publish_event
        publish_event('job.done', {
            'job_id': job_id, 'song_id': song_id,
            'type': job_type, 'title': title or '',
        })
    except Exception:
        pass


def _get_song_title(song_id):
    # essaie meta.json d'abord
    try:
        meta_path = os.path.join(Config.PROCESSED_FOLDER, song_id, 'meta.json')
        if os.path.exists(meta_path):
            from services.security import decrypt_data
            with open(meta_path) as f:
                meta = json.loads(decrypt_data(f.read()))
                return meta.get('title', '')
    except Exception:
        pass
    return ''


# separation demucs
def run_separate(job_id, song_id, payload):
    _update_job(job_id, status='started', started_at=datetime.utcnow(), progress=5)
    try:
        from database.models.song import Song
        s = get_session()
        try:
            song = s.query(Song).filter_by(id=song_id).first()
            if not song:
                return _fail_job(job_id, f"Song {song_id} not found")
            orig_file = song.original_file
        finally:
            s.close()

        orig_path = os.path.join(Config.UPLOAD_FOLDER, orig_file)
        out_dir = os.path.join(Config.PROCESSED_FOLDER, song_id)

        if not os.path.exists(orig_path):
            return _fail_job(job_id, f"Original file not found: {orig_path}")

        _update_job(job_id, progress=10)

        from audio_separator.demucs_utils import separate_audio_demucs
        mdl = payload.get('model', 'htdemucs')
        result = separate_audio_demucs(orig_path, out_dir, model_name=mdl)

        _update_job(job_id, progress=90)

        vocals_f = None
        instr_f = None
        for ext in ['.wav', '.mp3']:
            vp = os.path.join(out_dir, f'vocals{ext}')
            ip = os.path.join(out_dir, f'instrumental{ext}')
            if os.path.exists(vp) and not vocals_f:
                vocals_f = f'vocals{ext}'
            if os.path.exists(ip) and not instr_f:
                instr_f = f'instrumental{ext}'

        update_song_status(song_id, 'separated',
                           vocals_file=vocals_f, instrumental_file=instr_f)

        _update_job(job_id, status='finished', progress=100,
                    result={'vocals': vocals_f, 'instrumental': instr_f},
                    finished_at=datetime.utcnow())
        log.info(f"Job {job_id}: separation complete for {song_id}")
        _publish_done(job_id, song_id, 'separate', _get_song_title(song_id))

    except Exception as e:
        import traceback
        _fail_job(job_id, traceback.format_exc())


# paroles: online d'abord, whisper en fallback
def run_transcribe(job_id, song_id, payload):
    _update_job(job_id, status='started', started_at=datetime.utcnow(), progress=5)
    try:
        from database.models.song import Song
        s = get_session()
        try:
            song = s.query(Song).filter_by(id=song_id).first()
            if not song:
                return _fail_job(job_id, f"Song {song_id} not found")
            orig_file = song.original_file
            song_title = song.title
        finally:
            s.close()

        song_dir = os.path.join(Config.PROCESSED_FOLDER, song_id)
        os.makedirs(song_dir, exist_ok=True)

        artist = 'Unknown Artist'
        duration = 0
        meta_path = os.path.join(song_dir, 'meta.json')
        if os.path.exists(meta_path):
            try:
                from services.security import decrypt_data
                with open(meta_path, 'r') as f:
                    meta = json.loads(decrypt_data(f.read()))
                    artist = meta.get('artist', artist)
                    song_title = meta.get('title', song_title)
                    duration = meta.get('duration', 0)
            except Exception:
                pass

        _update_job(job_id, progress=10)

        # essai lyrics en ligne
        log.info(f"Job {job_id}: trying online lyrics for '{artist} - {song_title}'")
        lrc_content = None
        try:
            from services.lyrics_fetch import fetch_synced_lyrics
            lrc_content = fetch_synced_lyrics(song_title, artist, duration_sec=duration)
        except Exception as e:
            log.warning(f"Job {job_id}: lyrics fetch error: {e}")

        if lrc_content:
            _update_job(job_id, progress=80)

            with open(os.path.join(song_dir, 'lyrics.lrc'), 'w', encoding='utf-8') as f:
                f.write(encrypt_data(lrc_content))

            update_song_status(song_id, 'transcribed', lyrics_file='lyrics.lrc')
            _update_job(job_id, status='finished', progress=100,
                        result={'source': 'online', 'method': 'lrclib/syncedlyrics'},
                        finished_at=datetime.utcnow())
            log.info(f"Job {job_id}: online lyrics saved for {song_id} (skipped Whisper)")
            _publish_done(job_id, song_id, 'transcribe', song_title)
            return

        # fallback whisper
        log.info(f"Job {job_id}: no online lyrics found, falling back to Whisper")
        _update_job(job_id, progress=20)

        audio_path = None
        for ext in ['.wav', '.mp3']:
            vp = os.path.join(song_dir, f'vocals{ext}')
            if os.path.exists(vp):
                audio_path = vp
                break

        if not audio_path:
            audio_path = os.path.join(Config.UPLOAD_FOLDER, orig_file)

        if not os.path.exists(audio_path):
            return _fail_job(job_id, f"Audio file not found: {audio_path}")

        mdl_name = payload.get('model', 'base')
        if mdl_name not in ('tiny', 'base', 'small', 'medium', 'large'):
            mdl_name = 'base'

        from transcription.whisper_utils import transcribe_audio
        result = transcribe_audio(audio_path, model_name=mdl_name)

        if not result or not result.get('segments'):
            return _fail_job(job_id, "Transcription produced no results")

        _update_job(job_id, progress=80)

        from services.lyrics_helpers import seconds_to_srt_time
        from lyrics.sync_utils import srt_to_lrc

        srt_lines = []
        for i, seg in enumerate(result['segments'], 1):
            start = seconds_to_srt_time(seg['start'])
            end = seconds_to_srt_time(seg['end'])
            srt_lines.append(f"{i}")
            srt_lines.append(f"{start} --> {end}")
            srt_lines.append(seg['text'])
            srt_lines.append("")

        srt_content = '\n'.join(srt_lines)
        with open(os.path.join(song_dir, 'lyrics.srt'), 'w', encoding='utf-8') as f:
            f.write(encrypt_data(srt_content))

        lrc_content = srt_to_lrc(srt_content)
        with open(os.path.join(song_dir, 'lyrics.lrc'), 'w', encoding='utf-8') as f:
            f.write(encrypt_data(lrc_content))

        update_song_status(song_id, 'transcribed', lyrics_file='lyrics.lrc')

        _update_job(job_id, status='finished', progress=100,
                    result={'segments': len(result['segments']),
                            'text_preview': result['text'][:200]},
                    finished_at=datetime.utcnow())
        log.info(f"Job {job_id}: transcription complete for {song_id}")
        _publish_done(job_id, song_id, 'transcribe', song_title)

    except Exception as e:
        import traceback
        _fail_job(job_id, traceback.format_exc())


# yt-dlp suffixes a virer
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
            artist = parts[0].strip()
            title = parts[1].strip()
            for suf in _YT_SUFFIXES:
                title = title.replace(suf, '').strip()
            return title, artist

    title = yt_title
    for suf in _YT_SUFFIXES:
        title = title.replace(suf, '').strip()
    artist = yt_uploader or 'Unknown Artist'
    for suf in [' - Topic', 'VEVO', ' Official']:
        artist = artist.replace(suf, '').strip()
    return title, artist


def run_yt_download(job_id, song_id, payload):
    _update_job(job_id, status='started', started_at=datetime.utcnow(), progress=5)
    try:
        yt_url = payload.get('url', '')
        if not yt_url:
            return _fail_job(job_id, "No YouTube URL provided")

        if not re.match(r'^https?://(www\.)?(youtube\.com|youtu\.be|music\.youtube\.com)/[a-zA-Z0-9_\-?&=%./]*$', yt_url):
            return _fail_job(job_id, f"Invalid YouTube URL: {yt_url}")

        upload_dir = Config.UPLOAD_FOLDER
        output_path = os.path.join(upload_dir, f"{song_id}.%(ext)s")
        thumb_dir = os.path.join(Config.PROCESSED_FOLDER, song_id)
        os.makedirs(thumb_dir, exist_ok=True)

        _update_job(job_id, progress=10)

        cmd = [
            'yt-dlp',
            '--extract-audio', '--audio-format', 'mp3',
            '--audio-quality', '0',
            '-o', output_path,
            '--write-thumbnail', '--convert-thumbnails', 'jpg',
            '-o', f'thumbnail:{os.path.join(thumb_dir, "cover.%(ext)s")}',
            '--print', 'after_move:filepath',
            '--print', '%(title)s|||%(uploader)s|||%(duration)s',
            '--no-playlist',
            '--', yt_url
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=600)

        if res.returncode != 0:
            return _fail_job(job_id, f"yt-dlp failed: {res.stderr[:2000]}")

        _update_job(job_id, progress=70)

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
            elif os.path.sep in line or line.endswith('.mp3') or line.endswith('.m4a'):
                downloaded = line

        title, artist = _parse_yt_title(yt_title, yt_uploader)

        if not downloaded or not os.path.exists(downloaded):
            for f in os.listdir(upload_dir):
                if f.startswith(song_id):
                    downloaded = os.path.join(upload_dir, f)
                    break

        if not downloaded or not os.path.exists(downloaded):
            return _fail_job(job_id, "Downloaded file not found")

        orig_fname = os.path.basename(downloaded)
        song_dir = os.path.join(Config.PROCESSED_FOLDER, song_id)
        os.makedirs(song_dir, exist_ok=True)

        # fix thumbnail naming (yt-dlp ajoute parfois des trucs bizarres)
        for f in os.listdir(song_dir):
            if f.startswith('cover') and not f.startswith('cover.'):
                ext = os.path.splitext(f)[1]
                proper = os.path.join(song_dir, f'cover{ext}')
                if os.path.join(song_dir, f) != proper:
                    os.rename(os.path.join(song_dir, f), proper)
                break

        _update_job(job_id, progress=85)

        meta = {'artist': sanitize_text(artist), 'title': sanitize_text(title), 'duration': yt_duration}
        with open(os.path.join(song_dir, 'meta.json'), 'w') as f:
            f.write(encrypt_data(json.dumps(meta)))

        from database.db_utils import add_song
        add_song(song_id, sanitize_text(title), orig_fname)
        update_song_status(song_id, 'youtube')

        _update_job(job_id, status='finished', progress=100,
                    result={'song_id': song_id, 'title': title, 'artist': artist},
                    finished_at=datetime.utcnow())
        log.info(f"Job {job_id}: yt-download complete -- {title} - {artist}")

    except subprocess.TimeoutExpired:
        _fail_job(job_id, "Download timed out (5min max)")
    except Exception:
        import traceback
        _fail_job(job_id, traceback.format_exc())


# waveform peaks pour l'editeur paroles
def run_waveform(job_id, song_id, payload):
    _update_job(job_id, status='started', started_at=datetime.utcnow(), progress=5)
    try:
        song_dir = os.path.join(Config.PROCESSED_FOLDER, song_id)
        audio_path = None

        for name in ['vocals.wav', 'vocals.mp3']:
            p = os.path.join(song_dir, name)
            if os.path.exists(p):
                audio_path = p
                break

        if not audio_path:
            from database.models.song import Song
            s = get_session()
            try:
                song = s.query(Song).filter_by(id=song_id).first()
                if song:
                    audio_path = os.path.join(Config.UPLOAD_FOLDER, song.original_file)
            finally:
                s.close()

        if not audio_path or not os.path.exists(audio_path):
            return _fail_job(job_id, "Audio file not found for waveform")

        _update_job(job_id, progress=20)

        # extract peaks via ffmpeg: mono 8kHz raw pcm
        num_peaks = payload.get('num_peaks', 2000)
        cmd = [
            'ffmpeg', '-y', '-i', audio_path,
            '-ac', '1', '-ar', '8000',
            '-f', 's16le', '-'
        ]
        res = subprocess.run(cmd, capture_output=True, timeout=60)
        if res.returncode != 0:
            return _fail_job(job_id, "ffmpeg waveform extraction failed")

        import numpy as np
        samples = np.frombuffer(res.stdout, dtype=np.int16).astype(np.float32) / 32768.0

        chunk_sz = max(1, len(samples) // num_peaks)
        peaks = []
        for i in range(0, len(samples), chunk_sz):
            chunk = samples[i:i + chunk_sz]
            peaks.append(round(float(np.max(np.abs(chunk))), 4))

        _update_job(job_id, progress=80)

        # sauvegarde peaks chiffre
        peaks_path = os.path.join(song_dir, 'waveform.json')
        with open(peaks_path, 'w') as f:
            f.write(encrypt_data(json.dumps({'peaks': peaks, 'length': len(samples) / 8000})))

        _update_job(job_id, status='finished', progress=100,
                    result={'num_peaks': len(peaks)},
                    finished_at=datetime.utcnow())
        log.info(f"Job {job_id}: waveform complete for {song_id} ({len(peaks)} peaks)")

    except Exception:
        import traceback
        _fail_job(job_id, traceback.format_exc())
