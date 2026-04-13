# log recherches client - alimente alertes + analytics
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Index
from database.db_utils import Base


class SearchLog(Base):
    __tablename__ = 'search_logs'

    id = Column(Integer, primary_key=True, autoincrement=True)
    term = Column(String(255), nullable=False)
    normalized_term = Column(String(255), nullable=False, index=True)
    found = Column(Boolean, default=False, nullable=False, index=True)
    user_id = Column(Integer)           # nullable, sessions anonymes
    session_id = Column(String(64))
    ip = Column(String(64))             # tronquee pour analytics
    user_agent_hash = Column(String(64))  # hash, pas le ua brut (rgpd)
    ts = Column(DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (
        Index('ix_search_logs_term_ts', 'normalized_term', 'ts'),
        Index('ix_search_logs_found_ts', 'found', 'ts'),
    )

    def __repr__(self):
        return f"<SearchLog(term={self.term!r}, found={self.found}, ts={self.ts})>"
