#!/bin/bash
set -e

# We start as root so that we can fix ownership of volume mount points
# (Docker named volumes are created as root:root by default, which would
# break the non-root 'karaoke' user). Then we drop privileges via gosu.

echo "Fixing volume permissions..."
mkdir -p /app/static/uploads /app/static/processed /app/data /home/karaoke/.cache/whisper /home/karaoke/.cache/torch
chown -R karaoke:karaoke /app/static/uploads /app/static/processed /app/data /home/karaoke/.cache

echo "Waiting for database..."
gosu karaoke python -c "
from config import Config
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
import time

for i in range(30):
    try:
        engine = create_engine(Config.DATABASE_URI)
        with engine.connect():
            print('Database connected!')
            break
    except OperationalError:
        print(f'Waiting... ({i+1}/30)')
        time.sleep(2)
else:
    print('WARNING: Could not connect to database')

from database.db_utils import init_db
init_db()
print('Database initialized!')
"

# Drop privileges and exec the main process (gunicorn)
exec gosu karaoke "$@"
