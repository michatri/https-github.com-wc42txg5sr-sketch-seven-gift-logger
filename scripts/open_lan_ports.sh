#!/usr/bin/env bash
# เปิดไฟร์วอลล์ให้เครื่องใน LAN เข้า chatriACC ที่พอร์ต 8100 (สำรอง 8110)
# Usage: sudo ./scripts/open_lan_ports.sh [port]
set -euo pipefail

if [[ "$(id -u)" -ne 0 ]]; then
  echo "รันด้วย sudo: sudo $0"
  exit 1
fi

LAN="${CHATRIACC_LAN:-192.168.10.0/24}"
MAIN_PORT="${1:-8100}"
PORTS=("${MAIN_PORT}" 8110)

open_port() {
  local port="$1"
  if command -v ufw >/dev/null 2>&1; then
    ufw allow "${port}/tcp" >/dev/null 2>&1 || true
    ufw allow from "$LAN" to any port "$port" proto tcp >/dev/null 2>&1 || true
  fi
  if command -v iptables >/dev/null 2>&1; then
    iptables -C INPUT -p tcp --dport "$port" -j ACCEPT 2>/dev/null \
      || iptables -I INPUT -p tcp --dport "$port" -j ACCEPT || true
    iptables -C INPUT -p tcp -s "$LAN" --dport "$port" -j ACCEPT 2>/dev/null \
      || iptables -I INPUT -p tcp -s "$LAN" --dport "$port" -j ACCEPT || true
  fi
}

echo "==> เปิดพอร์ต ${PORTS[*]} สำหรับ ${LAN}"
for p in "${PORTS[@]}"; do
  open_port "$p"
  echo "    tcp/${p}"
done

if command -v ufw >/dev/null 2>&1; then
  ufw reload >/dev/null 2>&1 || true
  ufw status verbose || true
fi

echo
echo "จากเครื่องอื่นใน LAN ให้เปิด:"
echo "  http://$(hostname -I 2>/dev/null | awk '{print $1}'):${MAIN_PORT}/"
echo "ใช้ http เท่านั้น อย่าพิมพ์ https และต้องใส่ :${MAIN_PORT}"
