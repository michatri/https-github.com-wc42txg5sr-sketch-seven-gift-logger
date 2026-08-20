#!/usr/bin/env bash
# Install and start Catholic ID Web on THIS machine (the parish/camera server).
# Usage, after cloning the repo:
#   cd /home/aaa/catholic-id
#   sudo bash scripts/setup-server.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
PORT="${CATHOLIC_PORT:-8222}"
APP_USER="${CATHOLIC_APP_USER:-aaa}"

echo "==> Catholic ID Web setup in $ROOT"

if [[ ! -f app/main.py ]] || [[ ! -f app/data/catholic.db ]]; then
  echo "This folder is not the Catholic ID project."
  echo "Clone it first:"
  echo "  git clone -b cursor/catholic-id-web-9576 https://github.com/michatri/https-github.com-wc42txg5sr-sketch-seven-gift-logger.git /home/aaa/catholic-id"
  exit 1
fi

if command -v docker >/dev/null 2>&1 && { command -v docker-compose >/dev/null 2>&1 || docker compose version >/dev/null 2>&1; }; then
  echo "==> Starting with Docker on port ${PORT}"
  if docker compose version >/dev/null 2>&1; then
    docker compose up -d --build
  else
    docker-compose up -d --build
  fi
else
  echo "==> Docker not found, using Python venv"
  if ! python3 -c "import venv" 2>/dev/null; then
    if command -v apt-get >/dev/null 2>&1; then
      export DEBIAN_FRONTEND=noninteractive
      apt-get update -qq
      apt-get install -y -qq python3-venv python3-pip
    else
      echo "Need python3-venv. Install it, then re-run this script."
      exit 1
    fi
  fi
  python3 -m venv .venv
  .venv/bin/pip install -q --upgrade pip
  .venv/bin/pip install -q -r requirements.txt
  mkdir -p app/uploads/photos app/data

  if command -v fuser >/dev/null 2>&1; then
    fuser -k "${PORT}/tcp" 2>/dev/null || true
    fuser -k "8080/tcp" 2>/dev/null || true
  fi
  pkill -f "uvicorn app.main:app" 2>/dev/null || true
  sleep 1

  nohup env PYTHONPATH="$ROOT" .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port "${PORT}" \
    >/tmp/catholic-id.log 2>&1 &
  echo $! >/tmp/catholic-id.pid
  echo "==> uvicorn pid $(cat /tmp/catholic-id.pid)  log: /tmp/catholic-id.log"
fi

if [[ -f scripts/catholic-id.service ]] && command -v systemctl >/dev/null 2>&1 && [[ "$(id -u)" -eq 0 ]]; then
  sed "s|/home/aaa/catholic-id|${ROOT}|g" scripts/catholic-id.service >/etc/systemd/system/catholic-id.service
  if id "$APP_USER" >/dev/null 2>&1; then
    chown -R "${APP_USER}:${APP_USER}" "$ROOT" || true
  fi
  systemctl daemon-reload
  # Keep nohup/docker running for now; enable unit for reboot if venv exists
  if [[ -x "${ROOT}/.venv/bin/uvicorn" ]]; then
    systemctl enable catholic-id.service >/dev/null 2>&1 || true
  fi
fi

sleep 2
if command -v curl >/dev/null 2>&1; then
  curl -fsS "http://127.0.0.1:${PORT}/health" || echo "Server starting... check /tmp/catholic-id.log"
fi

IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
echo
echo "Open  http://${IP:-192.168.10.56}:${PORT}"
echo "Login admin / password"
