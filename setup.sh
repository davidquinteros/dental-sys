#!/bin/bash
# ─── DentalSys — Setup Script ───────────────────────────────────────────────
# Run this script to set up both backend and frontend for development
# Usage: bash setup.sh

set -e
echo ""
echo "╔══════════════════════════════════════════╗"
echo "║        DentalSys — Sistema Dental        ║"
echo "╚══════════════════════════════════════════╝"
echo ""

# ─── Backend Setup ───────────────────────────────────────────────────────────
echo "▶ Configurando Backend (Flask)..."
cd backend

if [ ! -d "venv" ]; then
  echo "  Creando entorno virtual Python..."
  python3 -m venv venv
fi

echo "  Instalando dependencias Python..."
source venv/bin/activate
pip install -r requirements.txt --quiet

if [ ! -f ".env" ]; then
  echo "  Creando archivo .env desde .env.example..."
  cp .env.example .env
  echo "  ⚠️  IMPORTANTE: Edite backend/.env con sus credenciales de base de datos"
fi

echo ""
echo "  Para iniciar el backend:"
echo "  cd backend && source venv/bin/activate"
echo "  flask db init && flask db migrate -m 'initial' && flask db upgrade"
echo "  flask seed"
echo "  flask run --port 5000"
echo ""

cd ..

# ─── Frontend Setup ──────────────────────────────────────────────────────────
echo "▶ Configurando Frontend (Angular)..."
cd frontend

if command -v npm &> /dev/null; then
  echo "  Instalando dependencias Node..."
  npm install --silent
  echo ""
  echo "  Para iniciar el frontend:"
  echo "  cd frontend && npm start"
else
  echo "  ⚠️  npm no encontrado. Instale Node.js 18+ y ejecute: cd frontend && npm install"
fi

cd ..

echo ""
echo "╔══════════════════════════════════════════════════════════╗"
echo "║  Setup completado!                                       ║"
echo "║                                                          ║"
echo "║  Backend:   http://localhost:5000                        ║"
echo "║  Frontend:  http://localhost:4200                        ║"
echo "║  API docs:  http://localhost:5000/api/health             ║"
echo "║                                                          ║"
echo "║  Credenciales por defecto (después de flask seed):       ║"
echo "║  Admin:      admin@clinica.com / Admin2025!              ║"
echo "║  Médico:     dr.garcia@clinica.com / Doctor2025!         ║"
echo "║  Recepción:  recepcion@clinica.com / Recep2025!          ║"
echo "║  Asistente:  asistente@clinica.com / Asist2025!          ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""
