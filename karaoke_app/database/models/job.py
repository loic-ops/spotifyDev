# file de traitement persistante
# types: separate, transcribe, yt_download, waveform
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, JSON, Text, ForeignKey, Index
from database.db_utils import Base


class Job(Base):
    __tablename__ = 'jobs'

    id = Column(String(36), primary_key=True)  # uuid partage avec rq
    type = Column(String(32), nullable=False, index=True)
    song_id = Column(String(36), ForeignKey('songs.id', ondelete='SET NULL'))
    status = Column(String(16), default='queued', index=True)
    progress = Column(Integer, default=0)  # 0-100
    payload = Column(JSON)
    result = Column(JSON)
    error = Column(Text)
    worker_id = Column(String(64))
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    started_at = Column(DateTime)
    finished_at = Column(DateTime)

    __table_args__ = (
        Index('ix_jobs_song_type', 'song_id', 'type'),
        Index('ix_jobs_status_created', 'status', 'created_at'),
    )

    def __repr__(self):
        return f"<Job(id={self.id[:8]}, type={self.type}, status={self.status}, progress={self.progress}%)>"
