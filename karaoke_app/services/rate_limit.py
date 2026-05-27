# rate limiting backed by redis (partage entre workers gunicorn)
from redis import Redis
from config import REDIS_URL

_redis = Redis.from_url(REDIS_URL, decode_responses=True)

MAX_LOGIN_ATTEMPTS = 5
LOGIN_WINDOW = 300

API_LIMIT = 30
API_WINDOW = 60


def _hit(key, limit, window):
    # fenetre fixe: TTL pose uniquement au premier increment du cycle
    count = _redis.incr(key)
    if count == 1:
        _redis.expire(key, window)
    return count > limit


def check_rate_limit(ip):
    return _hit(f"ratelimit:login:{ip}", MAX_LOGIN_ATTEMPTS, LOGIN_WINDOW)


def reset_rate_limit(ip):
    _redis.delete(f"ratelimit:login:{ip}")


def check_api_rate(ip, limit=API_LIMIT, window=API_WINDOW):
    return _hit(f"ratelimit:api:{ip}", limit, window)
