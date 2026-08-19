#!/usr/bin/env bash
# ตัวรันจริงของ systemd — หาโฟลเดอร์แอปจากตำแหน่งสคริปต์เอง
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT"
export PYTHONUNBUFFERED=1

HOST="${CHATRIACC_HOST:-0.0.0.0}"
REQUESTED_PORT="${CHATRIACC_PORT:-8100}"
export CHATRIACC_DB="${CHATRIACC_DB:-$ROOT/data/chatriacc.db}"

mkdir -p "$ROOT/data" "$ROOT/data/uploads"

log() { echo "chatriACC: $*" >&2; }

# พอร์ตของบริการอื่นบน cameraserver — ห้ามแย่ง
never_steal() {
  case "$1" in
    22|80|443|3306|8080|8090|8888) return 0 ;;
    *) return 1 ;;
  esac
}

port_busy() {
  local p="$1"
  if command -v ss >/dev/null 2>&1; then
    ss -lnt 2>/dev/null | awk '{print $4}' | grep -qE ":${p}$" && return 0
  fi
  if timeout 1 bash -c "echo >/dev/tcp/127.0.0.1/${p}" 2>/dev/null; then
    return 0
  fi
  return 1
}

pick_port() {
  local p seen=" "
  for p in "${REQUESTED_PORT}" 8100 8110 8120; do
    [[ "${seen}" == *" ${p} "* ]] && continue
    seen+="${p} "
    if never_steal "$p"; then
      log "ข้ามพอร์ต ${p} เพราะเป็นของบริการอื่น (SSH/เว็บ/บัญชีสลิป/Tomcat)"
      continue
    fi
    if port_busy "$p"; then
      log "พอร์ต ${p} ถูกใช้แล้ว"
      ss -lntp 2>/dev/null | grep -E ":${p}([[:space:]]|$)" >&2 || true
      continue
    fi
    echo "$p"
    return 0
  done
  return 1
}

PORT="$(pick_port || true)"
if [[ -z "${PORT}" ]]; then
  log "ERROR: พอร์ต 8100/8110/8120 ถูกใช้หมดแล้ว"
  ss -lntp 2>/dev/null || true
  exit 1
fi
export CHATRIACC_PORT="$PORT"

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

log "เปิด http://0.0.0.0:${PORT}/  (ใช้ IP จริงจาก hostname -I ไม่ใช่แค่ .65)"
exec "$GUNI" \
  --chdir "$ROOT" \
  --workers 2 \
  --bind "${HOST}:${PORT}" \
  --access-logfile - \
  --error-logfile - \
  chatriacc.wsgi:app
