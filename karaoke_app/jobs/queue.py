# gestion de la file de jobs RQ
import uuid
from datetime import datetime

from redis import Redis
from rq import Queue

from config import REDIS_URL
from database.db_utils import get_session
from database.models.job import Job

conn = Redis.from_url(REDIS_URL)
q = Queue('default', connection=conn)

TASKS = {
    'separate': 'jobs.tasks.run_separate',
    'transcribe': 'jobs.tasks.run_transcribe',
    'yt_download': 'jobs.tasks.run_yt_download',
    'waveform': 'jobs.tasks.run_waveform',
}


def get_redis():
    return conn

def get_queue():
    return q


def enqueue_job(job_type, song_id, payload=None, admin_id=None):
    jid = str(uuid.uuid4())

    s = get_session()
    try:
        s.add(Job(
            id=jid, type=job_type, song_id=song_id,
            status='queued', progress=0,
            payload=payload or {},
            created_at=datetime.utcnow(),
        ))
        s.commit()
    finally:
        s.close()

    func = TASKS.get(job_type)
    if not func:
        raise ValueError(f"unknown job type: {job_type}")

    q.enqueue(func, jid, song_id, payload or {}, job_id=jid, job_timeout='30m')
    return jid


def get_job_status(job_id):
    s = get_session()
    try:
        j = s.query(Job).filter_by(id=job_id).first()
        if not j:
            return None
        return {
            'id': j.id, 'type': j.type, 'song_id': j.song_id,
            'status': j.status, 'progress': j.progress,
            'error': j.error, 'result': j.result,
            'created_at': j.created_at.isoformat() if j.created_at else None,
            'started_at': j.started_at.isoformat() if j.started_at else None,
            'finished_at': j.finished_at.isoformat() if j.finished_at else None,
        }
    finally:
        s.close()


def get_jobs_for_song(song_id):
    s = get_session()
    try:
        rows = s.query(Job).filter_by(song_id=song_id).order_by(Job.created_at.desc()).all()
        return [{
            'id': j.id, 'type': j.type, 'status': j.status,
            'progress': j.progress, 'error': j.error,
            'created_at': j.created_at.isoformat() if j.created_at else None,
            'finished_at': j.finished_at.isoformat() if j.finished_at else None,
        } for j in rows]
    finally:
        s.close()
