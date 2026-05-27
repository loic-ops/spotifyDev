#!/bin/sh
set -e

if [ "$1" = "gunicorn" ]; then
    echo "[entrypoint] init_db + alembic upgrade head"
    python -c "from database.db_utils import init_db; init_db()"
    alembic upgrade head
fi

exec "$@"
