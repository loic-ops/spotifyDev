# alertes recherches non trouvees
# workflow: untreated -> in_progress -> added/unavailable/ignored
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, JSON, ForeignKey
from database.db_utils import Base


class Alert(Base):
    __tablename__ = 'alerts'

    id = Column(Integer, primary_key=True, autoincrement=True)
    term = Column(String(255), nullable=False)
    normalized_term = Column(String(255), nullable=False, unique=True, index=True)
    count = Column(Integer, default=1)
    status = Column(String(32), default='untreated')
    youtube_results = Column(JSON)  # 5 resultats yt-dlp pre-charges
    first_seen = Column(DateTime, default=datetime.utcnow)
    last_seen = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    resolved_at = Column(DateTime)
    resolved_by = Column(Integer, ForeignKey('admins.id'))
    resolved_song_id = Column(String(36), ForeignKey('songs.id'))
    notified_clients = Column(Integer, default=0)

    def __repr__(self):
        return f"<Alert(id={self.id}, term={self.term!r}, count={self.count}, status={self.status})>"
