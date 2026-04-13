# sse via redis pubsub
import json
import logging
from redis import Redis
from config import REDIS_URL

log = logging.getLogger('karaoking')

CHANNEL = 'karaoking:events'

_redis = Redis.from_url(REDIS_URL, decode_responses=True)


def publish_event(evt_type, data):
    try:
        msg = json.dumps({'type': evt_type, 'data': data})
        _redis.publish(CHANNEL, msg)
    except Exception as e:
        log.warning(f"[sse] publish error: {e}")


def event_stream():
    # generateur sse pour le dashboard admin
    ps = _redis.pubsub()
    ps.subscribe(CHANNEL)

    yield ": connected\n\n"

    try:
        for msg in ps.listen():
            if msg['type'] != 'message':
                continue
            yield f"data: {msg['data']}\n\n"
    finally:
        try:
            ps.unsubscribe(CHANNEL)
            ps.close()
        except Exception:
            pass
