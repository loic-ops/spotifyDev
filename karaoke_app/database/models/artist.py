# modele Artist - pages artistes auto-creees
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, JSON
from database.db_utils import Base


class Artist(Base):
    __tablename__ = 'artists'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False, index=True)
    slug = Column(String(255), unique=True, nullable=False)
    bio = Column(Text)
    photo_path = Column(String(500))
    socials = Column(JSON)  # {"instagram": "...", "youtube": "..."}
    songs_count = Column(Integer, default=0)  # cache denormalise
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Artist(id={self.id}, name={self.name})>"
