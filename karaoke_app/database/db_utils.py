from sqlalchemy import create_engine, Column, String, Integer, DateTime, Text, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import bcrypt
from config import DATABASE_URI

# Create engine
engine = create_engine(DATABASE_URI, pool_pre_ping=True)
Base = declarative_base()

# Session factory
Session = sessionmaker(bind=engine)


class Admin(Base):
    """Admin user model with bcrypt password hashing"""
    __tablename__ = 'admins'

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(80), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = bcrypt.hashpw(
            password.encode('utf-8'), bcrypt.gensalt()
        ).decode('utf-8')

    def check_password(self, password):
        return bcrypt.checkpw(
            password.encode('utf-8'),
            self.password_hash.encode('utf-8')
        )

    def __repr__(self):
        return f"<Admin(id={self.id}, username={self.username})>"


class Song(Base):
    """Song model"""
    __tablename__ = 'songs'

    id = Column(String(36), primary_key=True)
    title = Column(String(255), nullable=False)
    original_file = Column(String(255), nullable=False)
    instrumental_file = Column(String(255))
    vocals_file = Column(String(255))
    lyrics_file = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    status = Column(String(50), default='uploaded')

    def __repr__(self):
        return f"<Song(id={self.id}, title={self.title})>"


class Processing(Base):
    """Processing history model"""
    __tablename__ = 'processing'

    id = Column(Integer, primary_key=True, autoincrement=True)
    song_id = Column(String(36), ForeignKey('songs.id'))
    method = Column(String(50))
    status = Column(String(50))
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Processing(id={self.id}, song_id={self.song_id}, method={self.method})>"


def init_db():
    """Initialize database tables"""
    Base.metadata.create_all(engine)


def get_session():
    """Get database session"""
    return Session()


def add_song(song_id, title, original_file, lyrics_file=None):
    """Add a new song to the database"""
    session = get_session()
    try:
        song = Song(
            id=song_id,
            title=title,
            original_file=original_file,
            lyrics_file=lyrics_file,
            status='uploaded'
        )
        session.add(song)
        session.commit()
    finally:
        session.close()


def update_song_title(song_id, title):
    """Update song title in database"""
    session = get_session()
    try:
        song = session.query(Song).filter_by(id=song_id).first()
        if song:
            song.title = title
            session.commit()
            return True
        return False
    finally:
        session.close()


def update_song_status(song_id, status, **kwargs):
    """Update song status and optional file paths"""
    session = get_session()
    try:
        song = session.query(Song).filter_by(id=song_id).first()
        if song:
            song.status = status
            for key, value in kwargs.items():
                setattr(song, key, value)
            session.commit()
    finally:
        session.close()


def get_song_by_id(song_id):
    """Get song details by ID"""
    session = get_session()
    try:
        song = session.query(Song).filter_by(id=song_id).first()
        if song:
            return (song.id, song.title, song.original_file, 
                   song.instrumental_file, song.vocals_file, 
                   song.lyrics_file, song.created_at, song.status)
        return None
    finally:
        session.close()


def get_all_songs():
    """Get all songs"""
    session = get_session()
    try:
        songs = session.query(Song).order_by(Song.created_at.desc()).all()
        return [(s.id, s.title, s.original_file) for s in songs]
    finally:
        session.close()


def delete_song(song_id):
    """Delete a song from database"""
    session = get_session()
    try:
        session.query(Song).filter_by(id=song_id).delete()
        session.query(Processing).filter_by(song_id=song_id).delete()
        session.commit()
    finally:
        session.close()


def add_processing_record(song_id, method, status):
    """Add a processing record"""
    session = get_session()
    try:
        record = Processing(
            song_id=song_id,
            method=method,
            status=status
        )
        session.add(record)
        session.commit()
    finally:
        session.close()


def update_song_lyrics(song_id, lyrics_file):
    """Update song lyrics file path"""
    session = get_session()
    try:
        song = session.query(Song).filter_by(id=song_id).first()
        if song:
            song.lyrics_file = lyrics_file
            session.commit()
    finally:
        session.close()


# ─── Admin management ────────────────────────────────────────────────────────

def create_admin(username, password):
    """Create a new admin user with hashed password"""
    session = get_session()
    try:
        existing = session.query(Admin).filter_by(username=username).first()
        if existing:
            return None
        admin = Admin(username=username)
        admin.set_password(password)
        session.add(admin)
        session.commit()
        return admin.id
    finally:
        session.close()


def authenticate_admin(username, password):
    """Authenticate admin by username and password. Returns admin id or None."""
    session = get_session()
    try:
        admin = session.query(Admin).filter_by(username=username).first()
        if admin and admin.check_password(password):
            return admin.id
        return None
    finally:
        session.close()


def admin_exists():
    """Check if at least one admin account exists"""
    session = get_session()
    try:
        return session.query(Admin).count() > 0
    finally:
        session.close()


def get_admin_by_id(admin_id):
    """Get admin username by id"""
    session = get_session()
    try:
        admin = session.query(Admin).filter_by(id=admin_id).first()
        if admin:
            return {'id': admin.id, 'username': admin.username}
        return None
    finally:
        session.close()


def get_admin_by_username(username):
    """Get admin by username"""
    session = get_session()
    try:
        admin = session.query(Admin).filter_by(username=username).first()
        if admin:
            return {'id': admin.id, 'username': admin.username}
        return None
    finally:
        session.close()


def reset_admin_password(username, new_password):
    """Reset admin password. Returns True on success."""
    session = get_session()
    try:
        admin = session.query(Admin).filter_by(username=username).first()
        if not admin:
            return False
        admin.set_password(new_password)
        session.commit()
        return True
    finally:
        session.close()

