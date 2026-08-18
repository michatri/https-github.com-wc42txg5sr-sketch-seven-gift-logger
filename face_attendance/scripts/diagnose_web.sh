#!/usr/bin/env bash
# ไล่เช็กว่าทำไมเปิด http://SERVER:8080 ไม่ได้
set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "=== path ==="
pwd
ls -la scripts/run_web.sh .venv/bin/python 2>&1 | sed -n '1,5p'

echo
echo "=== IP ของเครื่องนี้ ==="
hostname -I || true

echo
echo "=== โปรเซสพอร์ต 8080 ==="
(ss -lntp 2>/dev/null || netstat -lntp 2>/dev/null || true) | grep 8080 || echo "(ยังไม่มีใครฟังพอร์ต 8080)"

echo
echo "=== firewall ==="
if command -v ufw >/dev/null 2>&1; then
  sudo ufw status || true
else
  echo "ไม่มี ufw"
fi

echo
echo "=== ทดสอบ local ==="
curl -sS -m 3 -o /dev/null -w "HTTP %{http_code}\n" http://127.0.0.1:8080/ || echo "curl 127.0.0.1:8080 ไม่สำเร็จ"

echo
echo "ถ้าพอร์ต 8080 ว่าง ให้รัน:"
echo "  cd $ROOT"
echo "  ./scripts/run_web.sh"
