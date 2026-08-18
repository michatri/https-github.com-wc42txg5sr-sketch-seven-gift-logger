#!/usr/bin/env bash
# ติดตั้งระบบบัญชีบน cameraserver (192.168.10.56)
# ใช้ได้กับ user aaa:  ssh aaa@192.168.10.56  แล้ว  sudo ./scripts/install_on_server.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERVICE_NAME="accounting"
UNIT_SRC="$ROOT/accounting/deploy/accounting.service"
UNIT_DST="/etc/systemd/system/${SERVICE_NAME}.service"
BIND_HOST="0.0.0.0"
BIND_PORT="${ACCOUNTING_PORT:-8090}"
SERVER_IP="${ACCOUNTING_SERVER_IP:-192.168.10.56}"
APP_USER="${SUDO_USER:-${USER}}"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "รันด้วย sudo: sudo $0"
  exit 1
fi

if [[ "$APP_USER" == "root" && -d /home/aaa ]]; then
  APP_USER="aaa"
fi

echo "==> โฟลเดอร์แอป: $ROOT"
echo "==> รันบริการด้วย user: $APP_USER"

export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq python3 python3-venv python3-pip curl iproute2 tesseract-ocr tesseract-ocr-tha >/dev/null

if [[ ! -x "$ROOT/.venv/bin/gunicorn" ]]; then
  echo "==> สร้าง virtualenv และติดตั้งแพ็กเกจ"
  python3 -m venv "$ROOT/.venv"
fi
# shellcheck disable=SC1091
source "$ROOT/.venv/bin/activate"
pip install -q --upgrade pip
pip install -q -r "$ROOT/requirements.txt"

mkdir -p "$ROOT/data"
chown -R "$APP_USER:$APP_USER" "$ROOT"

if [[ ! -f /etc/accounting.env ]]; then
  SECRET="$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
  cat > /etc/accounting.env <<EOF
ACCOUNTING_SECRET=${SECRET}
ACCOUNTING_HOST=${BIND_HOST}
ACCOUNTING_PORT=${BIND_PORT}
ACCOUNTING_DB=${ROOT}/data/accounting.db
ACCOUNTING_SERVER_IP=${SERVER_IP}
EOF
  chmod 600 /etc/accounting.env
fi

BINDS="--bind ${BIND_HOST}:${BIND_PORT}"
if command -v ss >/dev/null 2>&1 && ! ss -lnt | grep -qE ':80\\s'; then
  echo "==> พอร์ต 80 ว่าง จะเปิด http://${SERVER_IP}/ ด้วย"
  BINDS="${BINDS} --bind ${BIND_HOST}:80"
  OPEN_HTTP80=1
else
  OPEN_HTTP80=0
fi

echo "==> ติดตั้ง systemd: $UNIT_DST"
TMP_UNIT="$(mktemp)"
sed \
  -e "s|/root/accounting|${ROOT}|g" \
  -e "s|User=root|User=${APP_USER}|g" \
  -e "s|--bind 0.0.0.0:8090|${BINDS}|g" \
  "$UNIT_SRC" > "$TMP_UNIT"

if [[ "$OPEN_HTTP80" == "1" && "$APP_USER" != "root" ]]; then
  # พอร์ต 80 ต้องใช้สิทธิ์ root หรือ capability
  sed -i "s|User=${APP_USER}|User=root|" "$TMP_UNIT"
fi

cp "$TMP_UNIT" "$UNIT_DST"
rm -f "$TMP_UNIT"

open_port() {
  local port="$1"
  if command -v ufw >/dev/null 2>&1; then
    ufw allow "${port}/tcp" >/dev/null 2>&1 || true
  fi
  if command -v iptables >/dev/null 2>&1; then
    iptables -C INPUT -p tcp --dport "$port" -j ACCEPT 2>/dev/null \
      || iptables -I INPUT -p tcp --dport "$port" -j ACCEPT || true
  fi
}

echo "==> เปิดไฟร์วอลล์พอร์ต ${BIND_PORT}"
open_port "$BIND_PORT"
if [[ "$OPEN_HTTP80" == "1" ]]; then
  open_port 80
fi
if command -v ufw >/dev/null 2>&1; then
  ufw reload >/dev/null 2>&1 || true
  ufw status || true
fi

if command -v fuser >/dev/null 2>&1; then
  fuser -k "${BIND_PORT}/tcp" 2>/dev/null || true
fi

systemctl daemon-reload
systemctl enable "$SERVICE_NAME"
systemctl restart "$SERVICE_NAME"
sleep 2
systemctl --no-pager --full status "$SERVICE_NAME" || true

echo
echo "==> ตรวจจากเครื่องเซิร์ฟเวอร์เอง"
ss -lntp | grep -E ":${BIND_PORT}|:80\\s" || true
if curl -fsS --max-time 5 "http://127.0.0.1:${BIND_PORT}/health"; then
  echo
  echo "บริการบนพอร์ต ${BIND_PORT} ทำงานแล้ว"
else
  echo
  echo "ERROR: ยังเรียก http://127.0.0.1:${BIND_PORT}/health ไม่ได้"
  journalctl -u "$SERVICE_NAME" -n 80 --no-pager || true
  exit 1
fi

echo
echo "เปิดจากเครื่องใน LAN:"
echo "  http://${SERVER_IP}:${BIND_PORT}/"
if [[ "$OPEN_HTTP80" == "1" ]]; then
  echo "  http://${SERVER_IP}/"
fi
echo
echo "ถ้าเครื่องอื่นยังเข้าไม่ได้ แต่ curl บนเซิร์ฟเวอร์ได้ = ไฟร์วอลล์/สวิตช์บล็อกพอร์ต"
echo "  systemctl status ${SERVICE_NAME}"
echo "  journalctl -u ${SERVICE_NAME} -f"
echo "  sudo ufw allow ${BIND_PORT}/tcp && sudo ufw reload"
