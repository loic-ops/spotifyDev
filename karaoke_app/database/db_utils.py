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
def get_all_ads():
    """Récupère toutes les pubs, triées par date de création (plus récente en premier)"""
    from database.models.admin import Ad
    s = get_session()
    try:
        ads = s.query(Ad).order_by(Ad.id.desc()).all()
        result = []
        for ad in ads:
            result.append({
                'id': ad.id,
                'text': ad.text,
                'active': ad.active,
                'start_time': ad.start_time.isoformat() if ad.start_time else None,
                'end_time': ad.end_time.isoformat() if ad.end_time else None,
                'updated_at': ad.updated_at.isoformat() if ad.updated_at else None
            })
        return result
    finally:
        s.close()


def get_active_ad():
    """Récupère la pub actuellement ACTIVE (une seule parmi toutes)"""
    from database.models.admin import Ad
    from sqlalchemy import func
    s = get_session()
    try:
        # Comparaison côté MySQL en UTC pour éviter les problèmes de timezone.
        # Tolérant: si start/end sont NULL, la pub est active "tout le temps".
        # On priorise les pubs les plus récemment mises à jour / créées.
        ad = (
            s.query(Ad)
            .filter(Ad.active == True)
            .filter((Ad.start_time.is_(None)) | (Ad.start_time <= func.utc_timestamp()))
            .filter((Ad.end_time.is_(None)) | (Ad.end_time >= func.utc_timestamp()))
            .order_by(Ad.updated_at.desc(), Ad.id.desc())
            .first()
        )
        if ad:
            return {
                'id': ad.id,
                'text': ad.text,
                'active': True,
                'start_time': ad.start_time.isoformat() if ad.start_time else None,
                'end_time': ad.end_time.isoformat() if ad.end_time else None,
                'updated_at': ad.updated_at.isoformat() if ad.updated_at else None,
            }
        return None
    finally:
        s.close()


def create_ad(data):
    """Crée une nouvelle pub"""
    from database.models.admin import Ad
    from datetime import datetime, timezone
    s = get_session()
    try:
        def _parse_dt(val):
            if not val:
                return None
            # Supporte ISO avec 'Z' (UTC) ou offsets.
            if isinstance(val, str):
                v = val.strip()
                if v.endswith('Z'):
                    v = v[:-1] + '+00:00'
                try:
                    dt = datetime.fromisoformat(v)
                    # MySQL DATETIME ne stocke pas de timezone → on normalise en UTC naïf.
                    if dt.tzinfo is not None:
                        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
                    return dt
                except Exception:
                    return None
            return None

        ad = Ad()
        ad.text = data.get('text', '').strip()[:500]
        ad.active = bool(data.get('active', False))
        ad.start_time = _parse_dt(data.get('start_time'))
        ad.end_time = _parse_dt(data.get('end_time'))

        # Enforce: une seule pub active à la fois.
        if ad.active:
            s.query(Ad).filter(Ad.active == True).update({'active': False})

        s.add(ad)
        s.commit()
        return {
            'id': ad.id,
            'text': ad.text,
            'active': ad.active,
            'start_time': ad.start_time.isoformat() if ad.start_time else None,
            'end_time': ad.end_time.isoformat() if ad.end_time else None,
            'updated_at': ad.updated_at.isoformat() if ad.updated_at else None
        }
    finally:
        s.close()


def update_ad(ad_id, data):
    """Met à jour une pub existante"""
    from database.models.admin import Ad
    from datetime import datetime, timezone
    s = get_session()
    try:
        def _parse_dt(val):
            if not val:
                return None
            if isinstance(val, str):
                v = val.strip()
                if v.endswith('Z'):
                    v = v[:-1] + '+00:00'
                try:
                    dt = datetime.fromisoformat(v)
                    if dt.tzinfo is not None:
                        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
                    return dt
                except Exception:
                    return None
            return None

        ad = s.query(Ad).filter_by(id=ad_id).first()
        if not ad:
            return None
        
        ad.text = data.get('text', ad.text).strip()[:500]
        new_active = bool(data.get('active', ad.active))
        ad.active = new_active

        if 'start_time' in data:
            ad.start_time = _parse_dt(data.get('start_time'))
        if 'end_time' in data:
            ad.end_time = _parse_dt(data.get('end_time'))

        if new_active:
            # désactive toutes les autres
            s.query(Ad).filter(Ad.id != ad_id, Ad.active == True).update({'active': False})
        
        s.commit()
        return {
            'id': ad.id,
            'text': ad.text,
            'active': ad.active,
            'start_time': ad.start_time.isoformat() if ad.start_time else None,
            'end_time': ad.end_time.isoformat() if ad.end_time else None,
            'updated_at': ad.updated_at.isoformat() if ad.updated_at else None
        }
    finally:
        s.close()


def delete_ad(ad_id):
    """Supprime une pub"""
    from database.models.admin import Ad
    s = get_session()
    try:
        ad = s.query(Ad).filter_by(id=ad_id).first()
        if not ad:
            return False
        s.delete(ad)
        s.commit()
        return True
    finally:
        s.close()


def upsert_ad(data):
    """Legacy: crée une nouvelle pub (pour compatibilité)"""
    return create_ad(data)

