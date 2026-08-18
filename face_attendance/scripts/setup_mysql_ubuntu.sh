#!/usr/bin/env bash
# ติดตั้ง MariaDB/MySQL บน Ubuntu และสร้าง database สำหรับ Face Attendance
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ ! -f config/database.env ]]; then
  cp config/database.example.env config/database.env
  echo "สร้าง config/database.env แล้ว — แก้รหัสผ่านก่อน"
fi

# shellcheck disable=SC1091
set -a
source config/database.env
set +a

DB_NAME="${MYSQL_DATABASE:-face_attendance}"
DB_USER="${MYSQL_USER:-faceapp}"
DB_PASS="${MYSQL_PASSWORD:-ChangeThisPassword}"
DB_HOST="${MYSQL_HOST:-127.0.0.1}"

if [[ "$DB_PASS" == "ChangeThisPassword" ]]; then
  echo "กรุณาแก้ MYSQL_PASSWORD ใน config/database.env ก่อน แล้วรันสคริปต์นี้อีกครั้ง"
  exit 1
fi

echo "==> ติดตั้ง MariaDB Server + client"
sudo apt-get update
sudo apt-get install -y mariadb-server mariadb-client

echo "==> เริ่มบริการ MariaDB"
sudo systemctl enable --now mariadb

echo "==> สร้าง database/user"
sudo mysql <<SQL
CREATE DATABASE IF NOT EXISTS \`${DB_NAME}\`
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS '${DB_USER}'@'localhost' IDENTIFIED BY '${DB_PASS}';
CREATE USER IF NOT EXISTS '${DB_USER}'@'%' IDENTIFIED BY '${DB_PASS}';
GRANT ALL PRIVILEGES ON \`${DB_NAME}\`.* TO '${DB_USER}'@'localhost';
GRANT ALL PRIVILEGES ON \`${DB_NAME}\`.* TO '${DB_USER}'@'%';
FLUSH PRIVILEGES;
SQL

echo "==> ใส่ schema"
mysql -h "$DB_HOST" -u "$DB_USER" -p"$DB_PASS" "$DB_NAME" < sql/schema.sql

echo "==> ติดตั้ง pymysql ใน venv (ถ้ามี)"
if [[ -f .venv/bin/activate ]]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
  pip install -q pymysql cryptography
fi

echo
echo "พร้อมแล้ว"
echo "  1) ตรวจ: python scripts/test_mysql.py"
echo "  2) ย้ายข้อมูลไฟล์เดิม: python scripts/migrate_files_to_mysql.py"
echo "  3) เปิดใช้: ตั้ง MYSQL_ENABLED=1 ใน config/database.env แล้วรีสตาร์ทเว็บ"
