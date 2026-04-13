# journal actions admin
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, JSON, ForeignKey
from database.db_utils import Base


class AuditLog(Base):
    __tablename__ = 'audit_logs'

    id = Column(Integer, primary_key=True, autoincrement=True)
    admin_id = Column(Integer, ForeignKey('admins.id', ondelete='SET NULL'))
    action = Column(String(64), nullable=False, index=True)
    target_type = Column(String(32))
    target_id = Column(String(64))
    payload = Column(JSON)  # details avant/apres pour edits
    ip = Column(String(64))
    ts = Column(DateTime, default=datetime.utcnow, index=True)

    def __repr__(self):
        return f"<AuditLog(action={self.action}, admin={self.admin_id}, target={self.target_type}:{self.target_id})>"
