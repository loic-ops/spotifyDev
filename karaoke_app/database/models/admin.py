# modele Admin
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Boolean
import bcrypt
from database.db_utils import Base


class Admin(Base):
    __tablename__ = 'admins'

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(80), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # rbac + securite
    role = Column(String(20), default='admin')  # super_admin | admin | operateur
    totp_secret = Column(String(64))
    totp_enabled = Column(Boolean, default=False)
    last_login_at = Column(DateTime)
    last_ip = Column(String(45))
    failed_attempts = Column(Integer, default=0)

    def set_password(self, pwd):
        self.password_hash = bcrypt.hashpw(
            pwd.encode('utf-8'), bcrypt.gensalt()
        ).decode('utf-8')

    def check_password(self, pwd):
        return bcrypt.checkpw(pwd.encode('utf-8'),
                              self.password_hash.encode('utf-8'))
    def change_password(self, new_pwd):
        self.set_password(new_pwd)

    def __repr__(self):
        return f"<Admin(id={self.id}, username={self.username}, role={self.role})>"


class Ad(Base):
    __tablename__ = 'ads'

    id = Column(Integer, primary_key=True, autoincrement=True)
    text = Column(String(500))
    active = Column(Boolean, default=False)
    start_time = Column(DateTime)
    end_time = Column(DateTime)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<Ad(id={self.id}, active={self.active}, text={self.text[:50]}...>"
