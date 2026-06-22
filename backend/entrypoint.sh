#!/bin/sh
set -e

HOST="${POSTGRES_HOST:-db}"
PORT="${POSTGRES_PORT:-5432}"
USER="${POSTGRES_USER:-dental_user}"

echo "Esperando a PostgreSQL en ${HOST}:${PORT}..."
until pg_isready -h "$HOST" -p "$PORT" -U "$USER" > /dev/null 2>&1; do
  sleep 1
done
echo "PostgreSQL listo."

echo "Aplicando migraciones..."
# Migrations need DDL/ownership privileges; runtime traffic (flask run below)
# uses a restricted, non-superuser role instead so Row Level Security
# actually applies to it. Falls back to DATABASE_URL if unset, so this is
# safe to deploy before the migrations role exists elsewhere.
DATABASE_URL="${MIGRATIONS_DATABASE_URL:-$DATABASE_URL}" flask db upgrade

echo "Iniciando servidor con gunicorn..."
# gthread workers: each worker keeps its own SQLAlchemy connection pool, and
# threads within a worker share it, so total Postgres connections used here
# is roughly WEB_CONCURRENCY * (pool_size + max_overflow) from app/__init__.py
# — tune both together against the DB's actual max_connections.
#
# Defaults below (2 workers x 2 threads) are deliberately conservative —
# sized for a small/free-tier instance (e.g. Render free, 512MB RAM) so an
# unset env var can't accidentally over-commit memory. Set WEB_CONCURRENCY/
# WEB_THREADS explicitly once on a bigger plan; see backend/.env.example for
# suggested values per tier.
exec gunicorn \
  --workers "${WEB_CONCURRENCY:-2}" \
  --threads "${WEB_THREADS:-2}" \
  --worker-class gthread \
  --timeout "${WEB_TIMEOUT:-60}" \
  --bind 0.0.0.0:5000 \
  run:app
