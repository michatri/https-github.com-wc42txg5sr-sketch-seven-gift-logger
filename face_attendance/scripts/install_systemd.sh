#!/usr/bin/env bash
# ติดตั้ง systemd ให้เว็บเปิดอัตโนมัติตอนบูต ไม่ต้องรัน run_web.sh เอง
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd "$ROOT/.." && pwd)"
SERVICE_NAME="face-attendance"
UNIT_SRC="$ROOT/deploy/face-attendance.service"
UNIT_DST="/etc/systemd/system/${SERVICE_NAME}.service"

if [[ ! -x "$ROOT/.venv/bin/python" ]]; then
  echo "ยังไม่มี .venv — กำลังสร้างและติดตั้ง dependencies"
  python3 -m venv "$ROOT/.venv"
  # shellcheck disable=SC1091
  source "$ROOT/.venv/bin/activate"
  pip install --upgrade pip
  pip install -r "$ROOT/requirements.txt"
fi

# หยุดการรันมือที่จับพอร์ต 8080 อยู่ (ถ้ามี)
sudo fuser -k 8080/tcp 2>/dev/null || true

TMP_UNIT="$(mktemp)"
sed \
  -e "s|/root/https-github.com-wc42txg5sr-sketch-seven-gift-logger/face_attendance|${ROOT}|g" \
  -e "s|/root/https-github.com-wc42txg5sr-sketch-seven-gift-logger|${REPO_ROOT}|g" \
  "$UNIT_SRC" > "$TMP_UNIT"

echo "==> ติดตั้ง unit: $UNIT_DST"
sudo cp "$TMP_UNIT" "$UNIT_DST"
rm -f "$TMP_UNIT"

sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE_NAME"
sudo systemctl restart "$SERVICE_NAME"
sleep 1
sudo systemctl --no-pager --full status "$SERVICE_NAME" || true

echo
echo "เสร็จแล้ว — เว็บจะเปิดเองตอนบูตเครื่อง"
echo "  ตรวจสถานะ: sudo systemctl status $SERVICE_NAME"
echo "  ดู log    : sudo journalctl -u $SERVICE_NAME -f"
echo "  เปิดเว็บ  : http://$(hostname -I | awk '{print $1}'):8080/"
echo "  หยุดชั่วคราว: sudo systemctl stop $SERVICE_NAME"
echo "  เริ่มใหม่ : sudo systemctl restart $SERVICE_NAME"
