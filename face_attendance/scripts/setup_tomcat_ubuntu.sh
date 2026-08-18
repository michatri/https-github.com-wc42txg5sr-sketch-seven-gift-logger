#!/usr/bin/env bash
# ติดตั้ง Apache Tomcat 10 (Jakarta EE) บน Ubuntu
# ค่าเริ่มต้นใช้พอร์ต 8090 เพื่อไม่ชนกับ Face Attendance ที่ 8080
set -euo pipefail

TOMCAT_HTTP_PORT="${TOMCAT_HTTP_PORT:-8090}"
TOMCAT_SHUTDOWN_PORT="${TOMCAT_SHUTDOWN_PORT:-8005}"
TOMCAT_AJP_PORT="${TOMCAT_AJP_PORT:-8009}"

echo "==> ติดตั้ง Java + Tomcat 10 (Jakarta)"
sudo apt-get update
sudo apt-get install -y openjdk-17-jre-headless tomcat10 tomcat10-admin tomcat10-common

echo "==> ตั้งพอร์ต HTTP = ${TOMCAT_HTTP_PORT} (กันชนกับ face-attendance:8080)"
SERVER_XML="/etc/tomcat10/server.xml"
if [[ -f "$SERVER_XML" ]]; then
  sudo cp -a "$SERVER_XML" "${SERVER_XML}.bak.$(date +%Y%m%d%H%M%S)"
  # shutdown port
  sudo sed -i -E "s/Server port=\"[0-9]+\" shutdown=/Server port=\"${TOMCAT_SHUTDOWN_PORT}\" shutdown=/" "$SERVER_XML"
  # HTTP connector port
  sudo sed -i -E "s/(Connector port=\")[0-9]+(\" protocol=\"HTTP\\/1\\.1\")/\1${TOMCAT_HTTP_PORT}\2/" "$SERVER_XML"
  # AJP connector if present
  sudo sed -i -E "s/(Connector protocol=\"AJP\\/1\\.3\"[^>]*port=\")[0-9]+/\1${TOMCAT_AJP_PORT}/" "$SERVER_XML" || true
fi

echo "==> สร้างหน้าทดสอบ"
sudo mkdir -p /var/lib/tomcat10/webapps/ROOT
sudo tee /var/lib/tomcat10/webapps/ROOT/index.html >/dev/null <<EOF
<!DOCTYPE html>
<html lang="th">
<head>
  <meta charset="utf-8" />
  <title>Jakarta Tomcat</title>
  <style>
    body { font-family: sans-serif; max-width: 720px; margin: 48px auto; line-height: 1.5; }
    code { background: #f2f2f2; padding: 2px 6px; border-radius: 4px; }
  </style>
</head>
<body>
  <h1>Apache Tomcat 10 (Jakarta) พร้อมแล้ว</h1>
  <p>นี่คือ web server Tomcat แยกจากระบบ Face Attendance (Python) ที่พอร์ต 8080</p>
  <ul>
    <li>Tomcat: พอร์ต <code>${TOMCAT_HTTP_PORT}</code></li>
    <li>Face Attendance: พอร์ต <code>8080</code></li>
  </ul>
</body>
</html>
EOF

echo "==> เปิด firewall พอร์ต ${TOMCAT_HTTP_PORT}"
if command -v ufw >/dev/null 2>&1; then
  sudo ufw allow "${TOMCAT_HTTP_PORT}/tcp" || true
  sudo ufw reload || true
fi

echo "==> เปิดบริการ Tomcat"
sudo systemctl enable --now tomcat10
sudo systemctl restart tomcat10
sleep 2
sudo systemctl --no-pager --full status tomcat10 || true

IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
echo
echo "เสร็จแล้ว"
echo "  ตรวจสถานะ : sudo systemctl status tomcat10"
echo "  ดู log     : sudo journalctl -u tomcat10 -f"
echo "  เปิดเว็บ   : http://${IP:-SERVER_IP}:${TOMCAT_HTTP_PORT}/"
echo
echo "หมายเหตุ:"
echo "  - Face Attendance ยังอยู่ที่ http://${IP:-SERVER_IP}:8080/ (systemd: face-attendance)"
echo "  - วางไฟล์ WAR ของแอป Java ที่ /var/lib/tomcat10/webapps/"
echo "  - เปลี่ยนพอร์ตได้ด้วย: TOMCAT_HTTP_PORT=8090 ./scripts/setup_tomcat_ubuntu.sh"
