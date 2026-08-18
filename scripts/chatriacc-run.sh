#!/usr/bin/env bash
# ตัวรันจริงของ systemd — หาโฟลเดอร์แอปจากตำแหน่งสคริปต์เอง
# ไม่ผูกพอร์ต 80 เพื่อไม่ชน nginx/apache
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT"
export PYTHONUNBUFFERED=1

HOST="${CHATRIACC_HOST:-0.0.0.0}"
PORT="${CHATRIACC_PORT:-8090}"
export CHATRIACC_DB="${CHATRIACC_DB:-$ROOT/data/chatriacc.db}"

mkdir -p "$ROOT/data" "$ROOT/data/uploads"

log() { echo "chatriACC: $*" >&2; }

port_busy() {
  local p="$1"
  if command -v ss >/dev/null 2>&1; then
    ss -lnt 2>/dev/null | awk '{print $4}' | grep -qE ":${p}$" && return 0
  fi
  if command -v fuser >/dev/null 2>&1; then
    fuser "${p}/tcp" >/dev/null 2>&1 && return 0
  fi
  return 1
}

if port_busy "$PORT"; then
  log "พอร์ต ${PORT} ถูกใช้แล้ว"
  ss -lntp 2>/dev/null | grep -E ":${PORT}([[:space:]]|$)" || true
  log "ถ้า accounting.service ใช้ 8090 อยู่ ให้ใส่ CHATRIACC_PORT=8100 ใน /etc/chatriacc.env"
  exit 1
fi

VENV="$ROOT/.venv"
PY="$VENV/bin/python"
GUNI="$VENV/bin/gunicorn"

if [[ ! -x "$PY" ]]; then
  log "สร้าง virtualenv ที่ $VENV"
  python3 -m venv "$VENV"
fi
if [[ ! -x "$GUNI" ]]; then
  log "ติดตั้ง gunicorn และแพ็กเกจ"
  "$VENV/bin/pip" install -q --upgrade pip
  "$VENV/bin/pip" install -q -r "$ROOT/requirements.txt"
fi

if [[ ! -x "$GUNI" ]]; then
  log "ERROR: ไม่พบ $GUNI — รัน sudo ./scripts/install_on_server.sh อีกครั้ง"
  exit 1
fi

log "ตรวจ import จาก $ROOT"
if ! "$PY" -c "from chatriacc.wsgi import app; print('import-ok', app.name)"; then
  log "ERROR: import chatriacc.wsgi ไม่ผ่าน"
  exit 1
fi

log "gunicorn bind ${HOST}:${PORT} db=${CHATRIACC_DB}"
exec "$GUNI" \
  --chdir "$ROOT" \
  --workers 2 \
  --bind "${HOST}:${PORT}" \
  --access-logfile - \
  --error-logfile - \
  chatriacc.wsgi:app
