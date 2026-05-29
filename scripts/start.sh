#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ ! -f backend/.venv/bin/activate ]]; then
  echo "請先：cd backend && python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"
  exit 1
fi

# shellcheck source=/dev/null
source backend/.venv/bin/activate

if [[ -f frontend/dist/index.html ]]; then
  (cd backend && python manage.py collectstatic --noinput)
else
  echo "[WARN] 尚未建置前端：cd frontend && npm install && npm run build"
fi

cd backend
exec daphne -b 0.0.0.0 -p 3080 config.asgi:application
