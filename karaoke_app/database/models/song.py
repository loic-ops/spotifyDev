# modele Song
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, DateTime, Text, Boolean, Float,
    ForeignKey, Index, JSON,
)
from database.db_utils import Base


class Song(Base):
    __tablename__ = 'songs'

    id = Column(String(36), primary_key=True)
    title = Column(String(255), nullable=False)
    original_file = Column(String(255), nullable=False)
    instrumental_file = Column(String(255))
    vocals_file = Column(String(255))
    lyrics_file = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    status = Column(String(50), default='uploaded')

    source = Column(String(16), default='upload')        # upload | youtube
    source_url = Column(String(500))
    artist_id = Column(Integer, ForeignKey('artists.id', ondelete='SET NULL'))
    genre_id = Column(Integer, ForeignKey('genres.id', ondelete='SET NULL'))
    language = Column(String(8))       # fr, en, wo, bm...
    album = Column(String(255))
    cover_path = Column(String(500))
    published_at = Column(DateTime)
    soft_disabled = Column(Boolean, default=False)
    plays_count = Column(Integer, default=0)
    likes_count = Column(Integer, default=0)
    duration_sec = Column(Float, default=0)
    id3_raw = Column(Text)             # json chiffre, dump mutagen
    banner_text = Column(String(500))   # texte pub/annonce configurable par admin
    created_by = Column(Integer, ForeignKey('admins.id', ondelete='SET NULL'))

    __table_args__ = (
        Index('ix_songs_status', 'status'),
        Index('ix_songs_artist', 'artist_id'),
        Index('ix_songs_genre', 'genre_id'),
        Index('ix_songs_created', 'created_at'),
    )

    def __repr__(self):
        return f"<Song(id={self.id}, title={self.title}, status={self.status})>"
