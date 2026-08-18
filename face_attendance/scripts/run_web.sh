#!/usr/bin/env bash
# รันเว็บ Face Attendance ที่พอร์ต 8080
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ ! -d .venv ]]; then
  echo "==> ยังไม่มี .venv — สร้างและติดตั้ง dependencies"
  python3 -m venv .venv
  # shellcheck disable=SC1091
  source .venv/bin/activate
  pip install --upgrade pip
  pip install -r requirements.txt
else
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

# เผื่อเครื่องยังไม่มีแพ็กเกจเว็บหลัง git pull
python - <<'PY' || pip install -r requirements.txt
import fastapi, uvicorn, jinja2  # noqa: F401
PY

if [[ ! -f config/camera.env ]]; then
  cp config/camera.example.env config/camera.env
  echo "==> สร้าง config/camera.env แล้ว — ควรใส่ IP/รหัสกล้อง"
fi

export PYTHONPATH="$(cd "$ROOT/.." && pwd)${PYTHONPATH:+:$PYTHONPATH}"

IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
echo "==> เริ่มเว็บที่ http://0.0.0.0:8080/"
if [[ -n "${IP}" ]]; then
  echo "==> เปิดจากเครื่องอื่นใน LAN: http://${IP}:8080/"
fi
echo "==> กด Ctrl+C เพื่อหยุด"
echo

exec python -m uvicorn face_attendance.web.app:app --host 0.0.0.0 --port 8080
