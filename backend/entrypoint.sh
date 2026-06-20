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

echo "Cargando datos iniciales (seed)..."
flask seed

echo "Iniciando servidor Flask..."
exec flask run --host=0.0.0.0 --port=5000
