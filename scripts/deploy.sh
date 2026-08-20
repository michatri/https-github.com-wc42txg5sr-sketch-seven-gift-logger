#!/usr/bin/env bash
# Deploy Catholic ID Web to a LAN host (default 192.168.10.56).
# Run this from a machine that can SSH to the parish server.
set -euo pipefail

HOST="${CATHOLIC_HOST:-192.168.10.56}"
USER="${CATHOLIC_USER:-aaa}"
DEST="${CATHOLIC_DEST:-/home/aaa/catholic-id}"
PORT="${CATHOLIC_PORT:-8080}"

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "Deploying to ${USER}@${HOST}:${DEST}"
ssh "${USER}@${HOST}" "mkdir -p '${DEST}'"
rsync -av --exclude '.git' --exclude '.venv' --exclude '__pycache__' \
  --exclude '.pytest_cache' --exclude '*.exe' \
  "$ROOT/" "${USER}@${HOST}:${DEST}/"

ssh "${USER}@${HOST}" bash -s <<EOF
set -e
cd '${DEST}'
if command -v docker >/dev/null 2>&1; then
  docker compose up -d --build
  echo "Started with Docker on port 8080"
else
  python3 -m venv .venv
  .venv/bin/pip install -r requirements.txt
  mkdir -p app/data app/uploads/photos
  if [ ! -f app/data/catholic.db ]; then
    echo "Missing app/data/catholic.db"
    exit 1
  fi
  nohup .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port ${PORT} >/tmp/catholic-id.log 2>&1 &
  echo "Started uvicorn on port ${PORT} (log: /tmp/catholic-id.log)"
fi
EOF

echo "Open http://${HOST}:${PORT}  (admin / password)"
