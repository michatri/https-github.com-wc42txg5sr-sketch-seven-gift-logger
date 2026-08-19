#!/usr/bin/env bash
# ติดตั้ง chatriACC บน cameraserver ใน LAN
# เครื่องที่เปิดเว็บลงเวลา/บัญชีสลิปได้จริงคือ 192.168.10.56 ไม่ใช่ .65
# รันจาก user aaa:  ssh aaa@192.168.10.56  แล้ว  sudo ./scripts/install_on_server.sh
# ถ้า clone ไว้ที่ /root/chatriacc สคริปต์จะย้ายไป /home/aaa/chatriacc ให้เอง
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERVICE_NAME="chatriacc"
UNIT_DST="/etc/systemd/system/${SERVICE_NAME}.service"
BIND_HOST="0.0.0.0"
REAL_IPS="$(hostname -I 2>/dev/null || true)"
REAL_IP="$(echo "$REAL_IPS" | awk '{print $1}')"
SERVER_IP="${CHATRIACC_SERVER_IP:-${REAL_IP:-192.168.10.56}}"
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
    [[ -r "$dir/chatriacc/wsgi.py" ]] || return 1
    return 0
  fi
  sudo -u "$APP_USER" test -r "$dir/chatriacc/wsgi.py" 2>/dev/null || return 1
  return 0
}

# user aaa เข้า /root ไม่ได้ (drwx------) จึงห้ามรันบริการจาก /root/chatriacc
if [[ "$APP_USER" != "root" ]]; then
  TARGET="${APP_HOME}/chatriacc"
  if [[ "$ROOT" == /root/* ]] || ! user_can_read_app "$ROOT"; then
    echo "==> โค้ดอยู่ที่ $ROOT ซึ่ง user ${APP_USER} เข้าไม่ได้"
    echo "==> ย้ายไป ${TARGET} เพื่อไม่ให้เจอ Permission denied ที่ .venv/bin/python"
    mkdir -p "$TARGET"
    if command -v rsync >/dev/null 2>&1; then
      rsync -a --exclude '.venv' --exclude '__pycache__' --exclude '.pytest_cache' \
        "$ROOT/" "$TARGET/"
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
  echo "==> นี่คือ cameraserver (.56) — เปิดเว็บที่ http://192.168.10.56:8100/"
fi
if echo " ${REAL_IPS} " | grep -q " 192.168.10.65 "; then
  echo "==> เครื่องนี้มี IP .65 ตามที่ขอไว้"
elif echo " ${REAL_IPS} " | grep -q " 192.168.10."; then
  echo "==> คำเตือน: ไม่มี 192.168.10.65 บนเครื่องนี้ — อย่าเปิด URL ที่ลงท้าย .65"
fi

chmod +x "$ROOT/scripts/"*.sh
mkdir -p "$ROOT/data" "$ROOT/data/uploads"
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
for candidate in "${CHATRIACC_PORT:-8100}" 8100 8110 8120; do
  case "$candidate" in
    22|80|443|3306|8080|8090|8888) continue ;;
  esac
  if port_busy "$candidate"; then
    echo "==> พอร์ต ${candidate} ถูกใช้แล้ว"
    continue
  fi
  BIND_PORT="$candidate"
  break
done
if [[ -z "$BIND_PORT" ]]; then
  echo "ERROR: พอร์ต 8100/8110/8120 ถูกใช้หมดแล้ว"
  ss -lntp | grep -E ':8100|:8110|:8120|:8090|:8080|:8888|:80[[:space:]]' || true
  exit 1
fi
echo "==> จะเปิด chatriACC ที่พอร์ต ${BIND_PORT}"

echo "==> ตรวจ import ก่อนสตาร์ท systemd"
if ! sudo -u "$APP_USER" env PYTHONPATH="$ROOT" CHATRIACC_AUTO_SEED=0 "$ROOT/.venv/bin/python" -c "from chatriacc.wsgi import app; print(app.name)"; then
  echo "ERROR: import chatriacc ไม่ผ่าน"
  echo "user=${APP_USER} root=${ROOT}"
  ls -ld /root "$ROOT" "$ROOT/.venv/bin/python" 2>&1 || true
  exit 1
fi

echo "==> นำเข้าข้อมูลจาก chatriacc/seed/AC25-209.xlsb เข้าฐานข้อมูล"
sudo -u "$APP_USER" env PYTHONPATH="$ROOT" CHATRIACC_DB="${ROOT}/data/chatriacc.db" \
  "$ROOT/.venv/bin/python" -m chatriacc.importer || true
sudo -u "$APP_USER" env PYTHONPATH="$ROOT" CHATRIACC_DB="${ROOT}/data/chatriacc.db" \
  "$ROOT/.venv/bin/python" -c "from chatriacc.db import Store; s=Store('${ROOT}/data/chatriacc.db'); print('ใบสำคัญในฐาน:', s.voucher_count())" || true

ENV_FILE=/etc/chatriacc.env
SECRET="$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
if [[ -f "$ENV_FILE" ]]; then
  grep -q '^CHATRIACC_SECRET=' "$ENV_FILE" && SECRET="$(sed -n 's/^CHATRIACC_SECRET=//p' "$ENV_FILE" | head -n1)"
fi
cat > "$ENV_FILE" <<EOF
CHATRIACC_SECRET=${SECRET}
CHATRIACC_HOST=${BIND_HOST}
CHATRIACC_PORT=${BIND_PORT}
CHATRIACC_BIND_80=0
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
Environment=CHATRIACC_BIND_80=0
EnvironmentFile=-/etc/chatriacc.env
ExecStart=${ROOT}/scripts/chatriacc-run.sh
Restart=on-failure
RestartSec=3
TimeoutStopSec=20
SyslogIdentifier=chatriacc

[Install]
WantedBy=multi-user.target
EOF

echo "==> เปิดไฟร์วอลล์พอร์ต ${BIND_PORT}"
chmod +x "$ROOT/scripts/open_lan_ports.sh"
if [[ "${CHATRIACC_PUBLIC:-0}" == "1" ]]; then
  CHATRIACC_PUBLIC=1 CHATRIACC_LAN=0.0.0.0/0 "$ROOT/scripts/open_lan_ports.sh" "${BIND_PORT}" || true
else
  CHATRIACC_LAN="${CHATRIACC_LAN:-192.168.10.0/24}" "$ROOT/scripts/open_lan_ports.sh" "${BIND_PORT}" || true
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
LOCAL_IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
if curl -fsS --max-time 5 "http://127.0.0.1:${BIND_PORT}/health"; then
  echo
  echo "chatriACC บนพอร์ต ${BIND_PORT} ทำงานแล้ว"
  echo "โฟลเดอร์ที่ใช้จริง: $ROOT"
  echo "ครั้งถัดไปให้อัปเดตที่นี่ ไม่ใช่ /root/chatriacc:"
  echo "  cd $ROOT && git pull origin cursor/chatriacc-web-ebbb && sudo ./scripts/install_on_server.sh"
  echo "เปิดด้วย http และต้องใส่ :${BIND_PORT}"
  echo "  http://${LOCAL_IP}:${BIND_PORT}/"
  echo "  http://${SERVER_IP}:${BIND_PORT}/"
  if [[ "${CHATRIACC_PUBLIC:-0}" == "1" ]]; then
    echo "โหมด VPS: เปิดพอร์ต ${BIND_PORT} ที่ไฟร์วอลล์ของคลาวด์ด้วย (Security Group / Networking)"
  fi
else
  echo
  echo "ERROR: ยังเรียก http://127.0.0.1:${BIND_PORT}/health ไม่ได้"
  journalctl -u "$SERVICE_NAME" -n 80 --no-pager || true
  echo
  echo "รันเพิ่ม: $ROOT/scripts/diagnose_server.sh"
  exit 1
fi
