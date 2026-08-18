#!/usr/bin/env bash
# เปลี่ยนพอร์ต Tomcat เป็น 8888 (หรือค่าที่ส่งเข้ามา)
set -euo pipefail

NEW_PORT="${1:-8888}"
SERVER_XML="/etc/tomcat10/server.xml"

if [[ ! -f "$SERVER_XML" ]]; then
  echo "ไม่พบ $SERVER_XML — ติดตั้ง Tomcat ก่อน: ./scripts/setup_tomcat_ubuntu.sh"
  exit 1
fi

echo "==> เปลี่ยน HTTP port เป็น ${NEW_PORT}"
sudo cp -a "$SERVER_XML" "${SERVER_XML}.bak.$(date +%Y%m%d%H%M%S)"
sudo sed -i -E "s/(Connector port=\")[0-9]+(\" protocol=\"HTTP\\/1\\.1\")/\1${NEW_PORT}\2/" "$SERVER_XML"

# อัปเดตข้อความในหน้า index ถ้ามี
if [[ -f /var/lib/tomcat10/webapps/ROOT/index.html ]]; then
  sudo sed -i -E "s|พอร์ต <code>[0-9]+</code>|พอร์ต <code>${NEW_PORT}</code>|" /var/lib/tomcat10/webapps/ROOT/index.html || true
fi

if command -v ufw >/dev/null 2>&1; then
  sudo ufw allow "${NEW_PORT}/tcp" || true
  sudo ufw reload || true
fi

sudo systemctl restart tomcat10
sleep 1
(ss -lntp 2>/dev/null || true) | grep "${NEW_PORT}" || true

IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
echo
echo "เสร็จแล้ว เปิด: http://${IP:-192.168.10.56}:${NEW_PORT}/"
