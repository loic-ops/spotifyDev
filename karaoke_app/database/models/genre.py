# modele Genre - couleur + emoji + ordre editorial
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Boolean
from database.db_utils import Base


class Genre(Base):
    __tablename__ = 'genres'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(80), unique=True, nullable=False)
    slug = Column(String(80), unique=True, nullable=False)
    color = Column(String(16), default='#7C4DFF')
    emoji = Column(String(8), default='\U0001f3b5')
    sort_order = Column(Integer, default=0)
    visible = Column(Boolean, default=True)
    songs_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Genre(id={self.id}, name={self.name})>"
