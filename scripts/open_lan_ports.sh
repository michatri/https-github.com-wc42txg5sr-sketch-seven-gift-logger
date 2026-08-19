#!/usr/bin/env bash
# เปิดไฟร์วอลล์ให้เครื่องใน LAN เข้า chatriACC ที่พอร์ต 8100 (สำรอง 8110, 8120)
# Usage: sudo ./scripts/open_lan_ports.sh [port]
set -euo pipefail

if [[ "$(id -u)" -ne 0 ]]; then
  echo "รันด้วย sudo: sudo $0"
  exit 1
fi

LAN="${CHATRIACC_LAN:-192.168.10.0/24}"
if [[ "${CHATRIACC_PUBLIC:-0}" == "1" ]]; then
  LAN="0.0.0.0/0"
fi
MAIN_PORT="${1:-8100}"
PORTS=("${MAIN_PORT}" 8110 8120)

open_port() {
  local port="$1"
  if command -v ufw >/dev/null 2>&1; then
    ufw allow "${port}/tcp" comment "chatriACC" >/dev/null 2>&1 || true
    ufw allow from "$LAN" to any port "$port" proto tcp >/dev/null 2>&1 || true
  fi
  if command -v firewall-cmd >/dev/null 2>&1 && firewall-cmd --state >/dev/null 2>&1; then
    firewall-cmd --permanent --add-port="${port}/tcp" >/dev/null 2>&1 || true
  fi
  if command -v iptables >/dev/null 2>&1; then
    iptables -C INPUT -p tcp --dport "$port" -j ACCEPT 2>/dev/null \
      || iptables -I INPUT -p tcp --dport "$port" -j ACCEPT || true
    iptables -C INPUT -p tcp -s "$LAN" --dport "$port" -j ACCEPT 2>/dev/null \
      || iptables -I INPUT -p tcp -s "$LAN" --dport "$port" -j ACCEPT || true
  fi
  if command -v iptables-legacy >/dev/null 2>&1; then
    iptables-legacy -C INPUT -p tcp --dport "$port" -j ACCEPT 2>/dev/null \
      || iptables-legacy -I INPUT -p tcp --dport "$port" -j ACCEPT || true
  fi
}

echo "==> เปิดพอร์ต ${PORTS[*]} สำหรับ ${LAN}"
for p in "${PORTS[@]}"; do
  open_port "$p"
  echo "    tcp/${p}"
done

if command -v firewall-cmd >/dev/null 2>&1 && firewall-cmd --state >/dev/null 2>&1; then
  firewall-cmd --reload >/dev/null 2>&1 || true
fi
if command -v ufw >/dev/null 2>&1; then
  ufw reload >/dev/null 2>&1 || true
  ufw status verbose || true
fi
if command -v netfilter-persistent >/dev/null 2>&1; then
  netfilter-persistent save >/dev/null 2>&1 || true
fi

REAL_IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
echo
echo "IP จริงของเครื่องนี้: $(hostname -I 2>/dev/null || true)"
echo "จากเครื่องอื่นให้เปิด:"
echo "  http://${REAL_IP}:${MAIN_PORT}/"
if [[ "${CHATRIACC_PUBLIC:-0}" == "1" ]]; then
  echo "โหมด VPS: เปิดพอร์ตให้เข้าจากอินเทอร์เน็ต ตรวจไฟร์วอลล์ที่แผงควบคุม VPS ด้วย"
else
  echo "งานลงเวลา/บัญชีสลิปที่เข้าได้มาก่อนอยู่ที่ 192.168.10.56 ไม่ใช่ .65"
fi
echo "ใช้ http เท่านั้นถ้ายังไม่มี SSL และต้องใส่ :${MAIN_PORT}"
