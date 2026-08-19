#!/usr/bin/env bash
# ติดตั้งระบบรับของบริจาค 7-Eleven บน cameraserver 192.168.10.56
# รันจาก user aaa:  ssh aaa@192.168.10.56
# แล้ว:  sudo ./scripts/install_on_server.sh
# อย่าใช้พอร์ต 8080 (ลงเวลา), 8090 (บัญชีสลิป), 8100 (chatriACC)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERVICE_NAME="seven-gift-logger"
UNIT_DST="/etc/systemd/system/${SERVICE_NAME}.service"
BIND_HOST="0.0.0.0"
REAL_IPS="$(hostname -I 2>/dev/null || true)"
REAL_IP="$(echo "$REAL_IPS" | awk '{print $1}')"
SERVER_IP="${GIFT_SERVER_IP:-${REAL_IP:-192.168.10.56}}"
APP_USER="${SUDO_USER:-${USER}}"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "รันด้วย sudo: sudo $0"
  exit 1
fi

if [[ "$APP_USER" == "root" && -d /home/aaa ]]; then
  APP_USER="aaa"
fi
if ! id "$APP_USER" >/dev/null 2>&1; then
  echo "==> ไม่มี user ${APP_USER} จะรันด้วย root"
  APP_USER="root"
fi
APP_GROUP="$(id -gn "$APP_USER" 2>/dev/null || echo "$APP_USER")"
APP_HOME="$(getent passwd "$APP_USER" | cut -d: -f6)"
[[ -n "$APP_HOME" ]] || APP_HOME="/home/${APP_USER}"

export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq python3 python3-venv python3-pip curl iproute2 rsync >/dev/null

user_can_read_app() {
  local dir="$1"
  if [[ "$APP_USER" == "root" ]]; then
    [[ -r "$dir/wsgi.py" ]] || return 1
    return 0
  fi
  sudo -u "$APP_USER" test -r "$dir/wsgi.py" 2>/dev/null || return 1
}

if [[ "$APP_USER" != "root" ]]; then
  TARGET="${APP_HOME}/seven-gift-logger"
  if [[ "$ROOT" == /root/* ]] || ! user_can_read_app "$ROOT"; then
    echo "==> โค้ดอยู่ที่ $ROOT ซึ่ง user ${APP_USER} เข้าไม่ได้"
    echo "==> ย้ายไป ${TARGET}"
    mkdir -p "$TARGET"
    if command -v rsync >/dev/null 2>&1; then
      rsync -a --exclude '.venv' --exclude '__pycache__' --exclude '.pytest_cache' \
        --exclude 'data/*.db' "$ROOT/" "$TARGET/"
    else
      rm -rf "$TARGET"
      mkdir -p "$TARGET"
      cp -a "$ROOT"/. "$TARGET/"
      rm -rf "$TARGET/.venv"
    fi
    ROOT="$TARGET"
  fi
fi

echo "==> โฟลเดอร์แอป: $ROOT"
echo "==> รันบริการด้วย user: $APP_USER"
echo "==> IP จริงของเครื่องนี้: ${REAL_IPS:-unknown}"
if echo " ${REAL_IPS} " | grep -q " 192.168.10.56 "; then
  echo "==> นี่คือ cameraserver (.56)"
fi

chmod +x "$ROOT/scripts/"*.sh
mkdir -p "$ROOT/data" "$ROOT/data/photos"
chown -R "$APP_USER:$APP_GROUP" "$ROOT"

echo "==> สร้าง virtualenv สำหรับ user ${APP_USER}"
rm -rf "$ROOT/.venv"
if [[ "$APP_USER" == "root" ]]; then
  python3 -m venv "$ROOT/.venv"
  "$ROOT/.venv/bin/pip" install -q --upgrade pip
  "$ROOT/.venv/bin/pip" install -q -r "$ROOT/requirements.txt"
else
  sudo -u "$APP_USER" python3 -m venv "$ROOT/.venv"
  sudo -u "$APP_USER" "$ROOT/.venv/bin/pip" install -q --upgrade pip
  sudo -u "$APP_USER" "$ROOT/.venv/bin/pip" install -q -r "$ROOT/requirements.txt"
fi

if ! sudo -u "$APP_USER" test -x "$ROOT/.venv/bin/gunicorn"; then
  echo "ERROR: ติดตั้ง gunicorn ไม่สำเร็จ ที่ $ROOT/.venv"
  ls -l "$ROOT/.venv/bin" || true
  exit 1
fi

port_busy() {
  local p="$1"
  ss -lnt 2>/dev/null | awk '{print $4}' | grep -qE ":${p}$"
}

BIND_PORT=""
for candidate in "${GIFT_PORT:-8110}" 8110 8120 8130; do
  case "$candidate" in
    22|80|443|3306|8080|8090|8100|8888) continue ;;
  esac
  if port_busy "$candidate"; then
    echo "==> พอร์ต ${candidate} ถูกใช้แล้ว"
    continue
  fi
  BIND_PORT="$candidate"
  break
done
if [[ -z "$BIND_PORT" ]]; then
  echo "ERROR: พอร์ต 8110/8120/8130 ถูกใช้หมดแล้ว"
  ss -lntp | grep -E ':8110|:8120|:8130|:8100|:8090|:8080|:8888|:80[[:space:]]' || true
  exit 1
fi

ENV_FILE="/etc/seven-gift-logger.env"
if [[ ! -f "$ENV_FILE" ]]; then
  cat > "$ENV_FILE" <<EOF
GIFT_PORT=${BIND_PORT}
GIFT_BIND=0.0.0.0
GIFT_DB=${ROOT}/data/gift_logger.db
GIFT_DATA_DIR=${ROOT}/data
GIFT_ADMIN_EMAIL=admin@saintmarkpathum.com
GIFT_ADMIN_PASSWORD=admin123
# PUBLIC_BASE_URL=http://192.168.10.56:${BIND_PORT}
# LINE_CHANNEL_ACCESS_TOKEN=
# LINE_CHANNEL_SECRET=
EOF
  chmod 640 "$ENV_FILE"
  chown root:"$APP_GROUP" "$ENV_FILE"
fi

cat > "$UNIT_DST" <<EOF
[Unit]
Description=Seven-Eleven donation logger (Saint Mark Pathum)
After=network.target

[Service]
Type=simple
User=${APP_USER}
Group=${APP_GROUP}
WorkingDirectory=${ROOT}
Environment=GIFT_PORT=${BIND_PORT}
Environment=GIFT_BIND=${BIND_HOST}
Environment=GIFT_DB=${ROOT}/data/gift_logger.db
Environment=GIFT_DATA_DIR=${ROOT}/data
EnvironmentFile=-${ENV_FILE}
ExecStart=${ROOT}/scripts/gift-logger-run.sh
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable "$SERVICE_NAME"
systemctl restart "$SERVICE_NAME"

if command -v ufw >/dev/null 2>&1; then
  ufw allow "${BIND_PORT}/tcp" || true
fi

sleep 1
echo "==> สถานะบริการ:"
systemctl --no-pager --full status "$SERVICE_NAME" || true
echo
echo "เปิดเว็บที่: http://${SERVER_IP}:${BIND_PORT}/"
echo "ฟอร์มสาขา:  http://${SERVER_IP}:${BIND_PORT}/donate"
echo "เข้าสู่ระบบครั้งแรก: admin@saintmarkpathum.com / admin123"
echo "ตรวจสุขภาพ: curl -s http://127.0.0.1:${BIND_PORT}/health"
