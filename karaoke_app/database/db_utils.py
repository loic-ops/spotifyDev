from sqlalchemy import create_engine, Column, String, Integer, DateTime, Text, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
from config import DATABASE_URI

# Create engine
engine = create_engine(DATABASE_URI, pool_pre_ping=True)
Base = declarative_base()

# Session factory
Session = sessionmaker(bind=engine)


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


def add_song(song_id, title, original_file):
    """Add a new song to the database"""
    session = get_session()
    try:
        song = Song(
            id=song_id,
            title=title,
            original_file=original_file,
            status='uploaded'
        )
        session.add(song)
        session.commit()
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

