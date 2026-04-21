# db setup + fonctions utilitaires
from sqlalchemy import create_engine, Column, String, Integer, DateTime, Text, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from config import DATABASE_URI

engine = create_engine(DATABASE_URI, pool_pre_ping=True)
Base = declarative_base()
Session = sessionmaker(bind=engine)


class Processing(Base):
    # legacy, sera remplace par jobs
    __tablename__ = 'processing'
    id = Column(Integer, primary_key=True, autoincrement=True)
    song_id = Column(String(36), ForeignKey('songs.id'))
    method = Column(String(50))
    status = Column(String(50))
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Processing(id={self.id}, song_id={self.song_id}, method={self.method})>"


def _get_models():
    from database.models.song import Song
    from database.models.admin import Admin
    return Song, Admin


def init_db():
    import database.models  # noqa: F401
    _get_models()
    Base.metadata.create_all(engine)


def get_session():
    return Session()


def add_song(song_id, title, original_file, lyrics_file=None):
    Song, _ = _get_models()
    s = get_session()
    try:
        song = Song(id=song_id, title=title, original_file=original_file,
                    lyrics_file=lyrics_file, status='uploaded')
        s.add(song)
        s.commit()
    finally:
        s.close()


def update_song_title(song_id, title):
    Song, _ = _get_models()
    s = get_session()
    try:
        song = s.query(Song).filter_by(id=song_id).first()
        if song:
            song.title = title
            s.commit()
            return True
        return False
    finally:
        s.close()


ALLOWED_SONG_FIELDS = {'instrumental_file', 'vocals_file', 'lyrics_file'}


def update_song_status(song_id, status, **kwargs):
    Song, _ = _get_models()
    s = get_session()
    try:
        song = s.query(Song).filter_by(id=song_id).first()
        if song:
            song.status = status
            for k, v in kwargs.items():
                if k in ALLOWED_SONG_FIELDS:
                    setattr(song, k, v)
            s.commit()
    finally:
        s.close()


def get_song_by_id(song_id):
    Song, _ = _get_models()
    s = get_session()
    try:
        song = s.query(Song).filter_by(id=song_id).first()
        if song:
            return (song.id, song.title, song.original_file,
                    song.instrumental_file, song.vocals_file,
                    song.lyrics_file, song.created_at, song.status)
        return None
    finally:
        s.close()


def get_all_songs():
    Song, _ = _get_models()
    s = get_session()
    try:
        songs = s.query(Song).order_by(Song.created_at.desc()).all()
        return [(x.id, x.title, x.original_file, x.status) for x in songs]
    finally:
        s.close()


def delete_song(song_id):
    Song, _ = _get_models()
    s = get_session()
    try:
        s.query(Song).filter_by(id=song_id).delete()
        s.query(Processing).filter_by(song_id=song_id).delete()
        s.commit()
    finally:
        s.close()


def add_processing_record(song_id, method, status):
    s = get_session()
    try:
        rec = Processing(song_id=song_id, method=method, status=status)
        s.add(rec)
        s.commit()
    finally:
        s.close()


def update_song_lyrics(song_id, lyrics_file):
    Song, _ = _get_models()
    s = get_session()
    try:
        song = s.query(Song).filter_by(id=song_id).first()
        if song:
            song.lyrics_file = lyrics_file
            s.commit()
    finally:
        s.close()


# gestion admin

def create_admin(username, password):
    _, Admin = _get_models()
    s = get_session()
    try:
        if s.query(Admin).filter_by(username=username).first():
            return None
        adm = Admin(username=username)
        adm.set_password(password)
        s.add(adm)
        s.commit()
        return adm.id
    finally:
        s.close()


def authenticate_admin(username, password):
    _, Admin = _get_models()
    s = get_session()
    try:
        adm = s.query(Admin).filter_by(username=username).first()
        if adm and adm.check_password(password):
            return adm.id
        return None
    finally:
        s.close()


def admin_exists():
    _, Admin = _get_models()
    s = get_session()
    try:
        return s.query(Admin).count() > 0
    finally:
        s.close()


def get_admin_by_id(admin_id):
    _, Admin = _get_models()
    s = get_session()
    try:
        adm = s.query(Admin).filter_by(id=admin_id).first()
        if adm:
            return {'id': adm.id, 'username': adm.username}
        return None
    finally:
        s.close()


def get_admin_by_username(username):
    _, Admin = _get_models()
    s = get_session()
    try:
        adm = s.query(Admin).filter_by(username=username).first()
        if adm:
            return {'id': adm.id, 'username': adm.username}
        return None
    finally:
        s.close()


def reset_admin_password(username, new_password):
    _, Admin = _get_models()
    s = get_session()
    try:
        adm = s.query(Admin).filter_by(username=username).first()
        if not adm:
            return False
        adm.set_password(new_password)
        s.commit()
        return True
    finally:
        s.close()


def change_admin_password(admin_id, current_password, new_password):
    _, Admin = _get_models()
    s = get_session()
    try:
        adm = s.query(Admin).filter_by(id=admin_id).first()
        if not adm or not adm.check_password(current_password):
            return False
        adm.change_password(new_password)
        s.commit()
        return True
    finally:
        s.close()


# Global ads functions
def get_active_ad():
    from database.models.admin import Ad
    from datetime import datetime
    s = get_session()
    try:
        now = datetime.utcnow()
        ad = s.query(Ad).filter(
            Ad.active == True,
            Ad.start_time <= now,
            Ad.end_time >= now
        ).first()
        if ad:
            return {'id': ad.id, 'text': ad.text, 'active': True}
        return None
    finally:
        s.close()


def upsert_ad(data):
    from database.models.admin import Ad
    from datetime import datetime
    s = get_session()
    try:
        # Single global ad (id=1)
        ad = s.query(Ad).filter_by(id=1).first()
        if not ad:
            ad = Ad(id=1)
            s.add(ad)
        ad.text = data.get('text', '').strip()[:500]
        ad.active = bool(data.get('active', False))
        ad.start_time = datetime.fromisoformat(data.get('start_time')) if data.get('start_time') else None
        ad.end_time = datetime.fromisoformat(data.get('end_time')) if data.get('end_time') else None
        s.commit()
        return {'id': ad.id, 'text': ad.text, 'active': ad.active}
    finally:
        s.close()

