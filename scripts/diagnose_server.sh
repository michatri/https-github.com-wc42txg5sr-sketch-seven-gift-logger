#!/usr/bin/env bash
# ตรวจ chatriACC บนเครื่องเซิร์ฟเวอร์ เมื่อเข้าเว็บไม่ได้
set -euo pipefail
PORT="${CHATRIACC_PORT:-8100}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
echo "== hostname / IP จริง =="
hostname
echo "hostname -I: $(hostname -I 2>/dev/null || true)"
echo "ถ้าไม่มี 192.168.10.56 ในบรรทัดบน แสดงว่าไม่ได้ติดตั้งบน cameraserver"
echo "อย่าเปิด 192.168.10.65 ถ้า IP จริงเป็น .56 (ตัวเลขสลับกัน)"
uname -a
python3 --version || true
echo "== unit =="; systemctl cat chatriacc || true
echo "== status =="; systemctl --no-pager --full status chatriacc || true
echo "== journal =="; journalctl -u chatriacc -n 80 --no-pager || true
echo "== listening =="; ss -lntp | grep -E ':8100|:8110|:8120|:8090|:8080|:8888|:80[[:space:]]' || true
echo "== files ==";
ls -ld "$ROOT" "$ROOT/scripts/chatriacc-run.sh" "$ROOT/.venv/bin/gunicorn" "$ROOT/.venv/bin/python" 2>&1 || true
echo "== import ==";
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PYTHONPATH="$ROOT" "$ROOT/.venv/bin/python" -c "from chatriacc.wsgi import app; print('ok', app.name)" || true
else
  echo "ไม่มี $ROOT/.venv/bin/python"
fi
for p in "$PORT" 8100 8110 8120; do
  echo "== health :${p} =="; curl -sS --max-time 3 "http://127.0.0.1:${p}/health" && echo || echo "(no listener)"
done
echo "== env file =="; if [[ -f /etc/chatriacc.env ]]; then grep -v SECRET /etc/chatriacc.env; else echo "ไม่มี /etc/chatriacc.env"; fi
echo "== ufw =="; ufw status verbose || true
echo "== firewalld =="; firewall-cmd --list-ports 2>/dev/null || true
