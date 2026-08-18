#!/usr/bin/env bash
# เปิด MariaDB/MySQL ให้ Navicat (หรือ client อื่น) ต่อจากเครื่องใน LAN ได้
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ ! -f config/database.env ]]; then
  echo "ไม่พบ config/database.env — สร้างจากตัวอย่างก่อน"
  cp config/database.example.env config/database.env
  echo "แก้ MYSQL_PASSWORD ใน config/database.env แล้วรันสคริปต์นี้อีกครั้ง"
  exit 1
fi

# shellcheck disable=SC1091
set -a
source config/database.env
set +a

DB_NAME="${MYSQL_DATABASE:-face_attendance}"
DB_USER="${MYSQL_USER:-faceapp}"
DB_PASS="${MYSQL_PASSWORD:-}"
SERVER_IP="$(hostname -I 2>/dev/null | awk '{print $1}')"

if [[ -z "$DB_PASS" || "$DB_PASS" == "ChangeThisPassword" ]]; then
  echo "ตั้ง MYSQL_PASSWORD ใน config/database.env ให้แข็งแรงก่อน"
  exit 1
fi

echo "==> ตั้ง bind-address = 0.0.0.0"
CONF_DIR="/etc/mysql/mariadb.conf.d"
CONF_FILE="${CONF_DIR}/99-face-attendance-remote.cnf"
if [[ ! -d "$CONF_DIR" ]]; then
  # fallback MySQL
  CONF_DIR="/etc/mysql/mysql.conf.d"
  CONF_FILE="${CONF_DIR}/99-face-attendance-remote.cnf"
fi
if [[ ! -d "$CONF_DIR" ]]; then
  CONF_DIR="/etc/mysql"
  CONF_FILE="${CONF_DIR}/face-attendance-remote.cnf"
fi

sudo tee "$CONF_FILE" >/dev/null <<EOF
[mysqld]
bind-address = 0.0.0.0
skip-networking = 0
EOF

echo "==> สร้าง/อัปเดต user ให้ต่อจาก remote ได้"
sudo mysql <<SQL
CREATE DATABASE IF NOT EXISTS \`${DB_NAME}\`
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS '${DB_USER}'@'%' IDENTIFIED BY '${DB_PASS}';
ALTER USER '${DB_USER}'@'%' IDENTIFIED BY '${DB_PASS}';
CREATE USER IF NOT EXISTS '${DB_USER}'@'localhost' IDENTIFIED BY '${DB_PASS}';
ALTER USER '${DB_USER}'@'localhost' IDENTIFIED BY '${DB_PASS}';
GRANT ALL PRIVILEGES ON \`${DB_NAME}\`.* TO '${DB_USER}'@'%';
GRANT ALL PRIVILEGES ON \`${DB_NAME}\`.* TO '${DB_USER}'@'localhost';
FLUSH PRIVILEGES;
SQL

echo "==> รีสตาร์ท MariaDB/MySQL"
if systemctl list-unit-files | grep -q '^mariadb\.service'; then
  sudo systemctl restart mariadb
elif systemctl list-unit-files | grep -q '^mysql\.service'; then
  sudo systemctl restart mysql
else
  sudo systemctl restart mariadb || sudo systemctl restart mysql
fi

echo "==> เปิด firewall พอร์ต 3306"
if command -v ufw >/dev/null 2>&1; then
  sudo ufw allow 3306/tcp || true
  sudo ufw reload || true
fi

sleep 1
echo "==> ตรวจพอร์ต"
(ss -lntp 2>/dev/null || true) | grep 3306 || echo "(ยังไม่เห็น 3306 — เช็ก service)"

echo
echo "ตั้งค่าใน Navicat Premium"
echo "  Host     : ${SERVER_IP:-192.168.10.56}"
echo "  Port     : 3306"
echo "  User     : ${DB_USER}"
echo "  Password : (ตาม config/database.env)"
echo "  Database : ${DB_NAME}"
echo
echo "หมายเหตุ: เปิดเฉพาะใน LAN โรงเรียน และใช้รหัสผ่านที่แข็งแรง"
echo "ถ้ายังเข้าไม่ได้จาก Navicat ลองปิด VPN บนเครื่องที่เปิด Navicat"
