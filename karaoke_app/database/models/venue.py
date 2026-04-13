# config salle karaoke (multi-salles)
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, JSON
from database.db_utils import Base


class Venue(Base):
    __tablename__ = 'venues'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    slug = Column(String(255), unique=True, nullable=False)
    address = Column(String(500))
    timezone = Column(String(64), default='Africa/Lome')

    # config affichage
    welcome_msg = Column(Text)
    banner_text = Column(Text)  # bandeau pub defilant
    default_bg_mode = Column(String(32), default='dynamic')
    kiosk_mode = Column(Boolean, default=False)
    master_volume = Column(Integer, default=80)

    screen_config = Column(JSON)  # [{name, role, content_type}]

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<Venue(id={self.id}, name={self.name})>"
