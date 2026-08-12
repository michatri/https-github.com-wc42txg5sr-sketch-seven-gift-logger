#!/usr/bin/env bash
# ติดตั้งบน Ubuntu server สำหรับทดสอบ face attendance + Hikvision RTSP
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

echo "==> ติดตั้งแพ็กเกจระบบ"
sudo apt-get update
sudo apt-get install -y \
  python3 \
  python3-venv \
  python3-pip \
  ffmpeg \
  libgl1 \
  libglib2.0-0 \
  curl \
  ca-certificates

echo "==> สร้าง virtualenv"
python3 -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

if [[ ! -f config/camera.env ]]; then
  cp config/camera.example.env config/camera.env
  echo "==> สร้าง config/camera.env แล้ว — แก้ IP/user/password ก่อนรัน"
else
  echo "==> พบ config/camera.env อยู่แล้ว ข้ามการคัดลอก"
fi

echo "==> รัน self-test ออฟไลน์"
python scripts/selftest_offline.py

echo
echo "พร้อมแล้ว"
echo "  source $ROOT/.venv/bin/activate"
echo "  แก้ $ROOT/config/camera.env"
echo "  python scripts/check_camera.py"
