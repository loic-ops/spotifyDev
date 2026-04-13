# comptes clients electron + sessions analytics
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey
from database.db_utils import Base


class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True, autoincrement=True)
    anon_id = Column(String(64), unique=True, index=True)  # uuid device si pas de compte
    display_name = Column(String(80))
    email = Column(String(255), unique=True)
    password_hash = Column(String(255))
    avatar_path = Column(String(500))
    banned = Column(Boolean, default=False, index=True)
    banned_reason = Column(String(255))
    created_at = Column(DateTime, default=datetime.utcnow)
    last_seen = Column(DateTime, default=datetime.utcnow)
    sessions_count = Column(Integer, default=0)
    songs_played_count = Column(Integer, default=0)

    def __repr__(self):
        return f"<User(id={self.id}, name={self.display_name or self.anon_id[:8]})>"


class UserSession(Base):
    __tablename__ = 'user_sessions'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'))
    venue_id = Column(Integer, ForeignKey('venues.id', ondelete='SET NULL'))
    session_token = Column(String(64), unique=True, index=True)
    started_at = Column(DateTime, default=datetime.utcnow)
    ended_at = Column(DateTime)
    songs_played = Column(Integer, default=0)
    ip = Column(String(64))

    def __repr__(self):
        return f"<UserSession(id={self.id}, user={self.user_id}, started={self.started_at})>"
