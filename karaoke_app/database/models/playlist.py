# playlists editoriales admin
from datetime import datetime
from sqlalchemy import (Column, Integer, String, Text, DateTime, Boolean, ForeignKey)
from database.db_utils import Base


class Playlist(Base):
    __tablename__ = 'playlists'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    cover_path = Column(String(500))
    editorial = Column(Boolean, default=True)
    sort_order = Column(Integer, default=0)
    visible = Column(Boolean, default=True)
    scheduled_from = Column(DateTime)
    scheduled_to = Column(DateTime)
    created_by = Column(Integer, ForeignKey('admins.id'))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<Playlist(id={self.id}, name={self.name})>"


class PlaylistSong(Base):
    # association playlist <-> song, pk composite
    __tablename__ = 'playlist_songs'

    playlist_id = Column(Integer, ForeignKey('playlists.id', ondelete='CASCADE'), primary_key=True)
    song_id = Column(String(36), ForeignKey('songs.id', ondelete='CASCADE'), primary_key=True)
    position = Column(Integer, nullable=False, default=0)
    added_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<PlaylistSong(playlist={self.playlist_id}, song={self.song_id}, pos={self.position})>"
