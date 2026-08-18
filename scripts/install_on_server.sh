#!/usr/bin/env bash
# ติดตั้ง chatriACC บนเซิร์ฟเวอร์ LAN 192.168.10.65
# ssh aaa@192.168.10.65  แล้ว  sudo ./scripts/install_on_server.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERVICE_NAME="chatriacc"
UNIT_DST="/etc/systemd/system/${SERVICE_NAME}.service"
BIND_HOST="0.0.0.0"
SERVER_IP="${CHATRIACC_SERVER_IP:-192.168.10.65}"
APP_USER="${SUDO_USER:-${USER}}"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "รันด้วย sudo: sudo $0"
  exit 1
fi

if ! id "$APP_USER" >/dev/null 2>&1; then
  echo "==> ไม่มี user ${APP_USER} จะรันด้วย root"
  APP_USER="root"
fi
APP_GROUP="$(id -gn "$APP_USER" 2>/dev/null || echo "$APP_USER")"

echo "==> โฟลเดอร์แอป: $ROOT"
echo "==> รันบริการด้วย user: $APP_USER"

export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq python3 python3-venv python3-pip curl iproute2 >/dev/null

chmod +x "$ROOT/scripts/"*.sh

if [[ ! -x "$ROOT/.venv/bin/python" ]]; then
  echo "==> สร้าง virtualenv"
  python3 -m venv "$ROOT/.venv"
fi
# shellcheck disable=SC1091
source "$ROOT/.venv/bin/activate"
pip install -q --upgrade pip
pip install -q -r "$ROOT/requirements.txt"

if [[ ! -x "$ROOT/.venv/bin/gunicorn" ]]; then
  echo "ERROR: ติดตั้ง gunicorn ไม่สำเร็จ"
  exit 1
fi

mkdir -p "$ROOT/data" "$ROOT/data/uploads"
chown -R "$APP_USER:$APP_GROUP" "$ROOT"

port_busy() {
  local p="$1"
  ss -lnt 2>/dev/null | awk '{print $4}' | grep -qE ":${p}$"
}

BIND_PORT="${CHATRIACC_PORT:-8090}"
if port_busy "$BIND_PORT"; then
  echo "==> พอร์ต ${BIND_PORT} ถูกใช้แล้ว จะใช้ 8100 แทน"
  BIND_PORT="8100"
fi
if port_busy "$BIND_PORT"; then
  echo "ERROR: พอร์ต ${BIND_PORT} ก็ถูกใช้แล้วเช่นกัน"
  ss -lntp | grep -E ':8090|:8100|:80[[:space:]]' || true
  exit 1
fi

echo "==> ตรวจ import ก่อนสตาร์ท systemd"
if ! sudo -u "$APP_USER" env PYTHONPATH="$ROOT" "$ROOT/.venv/bin/python" -c "from chatriacc.wsgi import app; print(app.name)"; then
  echo "ERROR: import chatriacc ไม่ผ่าน — ดูข้อความด้านบน"
  exit 1
fi

ENV_FILE=/etc/chatriacc.env
SECRET="$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
if [[ -f "$ENV_FILE" ]]; then
  grep -q '^CHATRIACC_SECRET=' "$ENV_FILE" && SECRET="$(sed -n 's/^CHATRIACC_SECRET=//p' "$ENV_FILE" | head -n1)"
fi
cat > "$ENV_FILE" <<EOF
CHATRIACC_SECRET=${SECRET}
CHATRIACC_HOST=${BIND_HOST}
CHATRIACC_PORT=${BIND_PORT}
CHATRIACC_DB=${ROOT}/data/chatriacc.db
CHATRIACC_SERVER_IP=${SERVER_IP}
EOF
chmod 600 "$ENV_FILE"

echo "==> เขียน systemd unit ที่ path จริง: $ROOT"
cat > "$UNIT_DST" <<EOF
[Unit]
Description=chatriACC church accounting
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${APP_USER}
Group=${APP_GROUP}
WorkingDirectory=${ROOT}
Environment=PYTHONPATH=${ROOT}
Environment=PYTHONUNBUFFERED=1
Environment=CHATRIACC_DB=${ROOT}/data/chatriacc.db
Environment=CHATRIACC_PORT=${BIND_PORT}
EnvironmentFile=-/etc/chatriacc.env
ExecStart=${ROOT}/scripts/chatriacc-run.sh
Restart=on-failure
RestartSec=3
TimeoutStopSec=20
SyslogIdentifier=chatriacc

[Install]
WantedBy=multi-user.target
EOF

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
if command -v ufw >/dev/null 2>&1; then
  ufw reload >/dev/null 2>&1 || true
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
ss -lntp | grep -E ":${BIND_PORT}" || true
if curl -fsS --max-time 5 "http://127.0.0.1:${BIND_PORT}/health"; then
  echo
  echo "chatriACC บนพอร์ต ${BIND_PORT} ทำงานแล้ว"
  echo "เปิดจากเครื่องใน LAN: http://${SERVER_IP}:${BIND_PORT}/"
else
  echo
  echo "ERROR: ยังเรียก http://127.0.0.1:${BIND_PORT}/health ไม่ได้"
  journalctl -u "$SERVICE_NAME" -n 80 --no-pager || true
  echo
  echo "รันเพิ่ม: $ROOT/scripts/diagnose_server.sh"
  exit 1
fi
