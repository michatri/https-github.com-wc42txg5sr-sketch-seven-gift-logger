#!/usr/bin/env bash
# ตรวจว่าทำไม http://192.168.10.56:8090/ เข้าไม่ได้ — รันบนเซิร์ฟเวอร์
set -u

PORT="${ACCOUNTING_PORT:-8090}"
echo "=== hostname / user ==="
hostname; whoami; id
echo
echo "=== ที่อยู่ IP ==="
hostname -I 2>/dev/null || true
ip -4 addr show 2>/dev/null | sed -n 's/.*inet //p' || true
echo
echo "=== systemd accounting ==="
systemctl is-enabled accounting 2>&1 || true
systemctl --no-pager --full status accounting 2>&1 | head -40 || true
echo
echo "=== พอร์ตที่เปิดอยู่ ==="
ss -lntp 2>/dev/null || netstat -lntp 2>/dev/null || true
echo
echo "=== curl localhost:${PORT} ==="
curl -sv --max-time 5 "http://127.0.0.1:${PORT}/health" 2>&1 | tail -30 || true
echo
echo "=== curl localhost:80 ==="
curl -sv --max-time 5 "http://127.0.0.1/health" 2>&1 | tail -20 || true
echo
echo "=== ufw ==="
sudo ufw status verbose 2>&1 || true
echo
echo "=== log ล่าสุด ==="
sudo journalctl -u accounting -n 50 --no-pager 2>&1 || true
