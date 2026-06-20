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
flask db upgrade

echo "Cargando datos iniciales (seed)..."
flask seed

echo "Iniciando servidor Flask..."
exec flask run --host=0.0.0.0 --port=5000
