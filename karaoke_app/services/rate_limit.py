# rate limiting in-memory (TODO: passer sur redis pour multi-worker)
import time

# login
_login_attempts = {}  # ip -> (count, first_attempt_time)
MAX_ATTEMPTS = 5
LOGIN_WINDOW = 300  # 5min


def check_rate_limit(ip):
    now = time.time()
    if ip in _login_attempts:
        cnt, first = _login_attempts[ip]
        if now - first > LOGIN_WINDOW:
            _login_attempts[ip] = (1, now)
            return False
        if cnt >= MAX_ATTEMPTS:
            return True
        _login_attempts[ip] = (cnt + 1, first)
    else:
        _login_attempts[ip] = (1, now)
    return False


def reset_rate_limit(ip):
    _login_attempts.pop(ip, None)


# api rate limit
_api_hits = {}  # ip -> (count, window_start)
API_LIMIT = 30
API_WINDOW = 60


def check_api_rate(ip, limit=API_LIMIT, window=API_WINDOW):
    now = time.time()
    if ip not in _api_hits:
        _api_hits[ip] = (1, now)
        return False
    cnt, start = _api_hits[ip]
    if now - start > window:
        _api_hits[ip] = (1, now)
        return False
    if cnt >= limit:
        return True
    _api_hits[ip] = (cnt + 1, start)
    return False
