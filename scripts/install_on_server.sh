#!/usr/bin/env bash
# ติดตั้งระบบบัญชีบน Ubuntu server 192.168.10.56 (cameraserver)
# ไม่ยุ่งกับระบบลงเวลาใบหน้าที่พอร์ต 8080 และ Tomcat ที่พอร์ต 8888
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERVICE_NAME="accounting"
UNIT_SRC="$ROOT/accounting/deploy/accounting.service"
UNIT_DST="/etc/systemd/system/${SERVICE_NAME}.service"
BIND_HOST="0.0.0.0"
BIND_PORT="${ACCOUNTING_PORT:-8090}"
SERVER_IP="${ACCOUNTING_SERVER_IP:-192.168.10.56}"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "รันด้วย root: sudo $0"
  exit 1
fi

echo "==> ติดตั้งแพ็กเกจระบบ"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq python3 python3-venv python3-pip >/dev/null

if [[ ! -x "$ROOT/.venv/bin/python" ]]; then
  echo "==> สร้าง virtualenv"
  python3 -m venv "$ROOT/.venv"
fi

echo "==> ติดตั้ง Python packages"
# shellcheck disable=SC1091
source "$ROOT/.venv/bin/activate"
pip install -q --upgrade pip
pip install -q -r "$ROOT/requirements.txt"

mkdir -p "$ROOT/data"

if [[ ! -f /etc/accounting.env ]]; then
  echo "==> สร้าง /etc/accounting.env"
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

echo "==> ติดตั้ง systemd: $UNIT_DST"
TMP_UNIT="$(mktemp)"
sed \
  -e "s|/root/accounting|${ROOT}|g" \
  -e "s|0.0.0.0:8090|${BIND_HOST}:${BIND_PORT}|g" \
  "$UNIT_SRC" > "$TMP_UNIT"
cp "$TMP_UNIT" "$UNIT_DST"
rm -f "$TMP_UNIT"

if command -v ufw >/dev/null 2>&1; then
  echo "==> เปิดไฟร์วอลล์พอร์ต ${BIND_PORT}"
  ufw allow "${BIND_PORT}/tcp" >/dev/null 2>&1 || true
fi

# อย่าไปหยุด face-attendance (8080) หรือ tomcat (8888)
if command -v fuser >/dev/null 2>&1; then
  fuser -k "${BIND_PORT}/tcp" 2>/dev/null || true
fi

systemctl daemon-reload
systemctl enable "$SERVICE_NAME"
systemctl restart "$SERVICE_NAME"
sleep 1
systemctl --no-pager --full status "$SERVICE_NAME" || true

echo
echo "เสร็จแล้ว — ระบบบัญชีเปิดอัตโนมัติตอนบูต"
echo "  เปิดเว็บ  : http://${SERVER_IP}:${BIND_PORT}/"
echo "  ตรวจสุขภาพ: http://${SERVER_IP}:${BIND_PORT}/health"
echo "  สถานะ    : systemctl status ${SERVICE_NAME}"
echo "  ดู log    : journalctl -u ${SERVICE_NAME} -f"
echo "  เริ่มใหม่ : systemctl restart ${SERVICE_NAME}"
echo
echo "พอร์ตอื่นบนเครื่องนี้ยังใช้ตามเดิม:"
echo "  ลงเวลาใบหน้า : http://${SERVER_IP}:8080/"
echo "  Tomcat        : http://${SERVER_IP}:8888/"
