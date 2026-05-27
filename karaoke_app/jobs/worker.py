# rq worker entrypoint - run via python -m jobs.worker
import sys, os
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from redis import Redis
from rq import Worker, Queue
from config import REDIS_URL

logging.basicConfig(level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')
log = logging.getLogger('rq.worker')


def main():
    conn = Redis.from_url(REDIS_URL)
    queues = [Queue('default', connection=conn)]
    log.info(f"Starting RQ worker, listening on queues: {[q.name for q in queues]}")
    log.info(f"Redis: {REDIS_URL}")
    w = Worker(queues, connection=conn)
    w.work(with_scheduler=True)


if __name__ == '__main__':
    main()
