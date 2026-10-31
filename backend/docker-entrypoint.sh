#!/bin/sh
set -e

DB_HOST="$(python -c "from urllib.parse import urlparse; import os; print(urlparse(os.environ['DATABASE_URL'].replace('+asyncpg', '')).hostname or 'postgres')")"
DB_PORT="$(python -c "from urllib.parse import urlparse; import os; print(urlparse(os.environ['DATABASE_URL'].replace('+asyncpg', '')).port or 5432)")"

echo "Waiting for PostgreSQL at ${DB_HOST}:${DB_PORT}..."
until nc -z "$DB_HOST" "$DB_PORT"; do
  sleep 1
done

echo "Running database migrations..."
alembic upgrade head

echo "Initializing application data..."
python -m app.seed

exec "$@"
