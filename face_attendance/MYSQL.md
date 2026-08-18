# เตรียมใช้งาน MySQL / MariaDB

ระบบรองรับทั้งโหมดไฟล์ (ค่าเริ่มต้น) และโหมด MySQL  
เปิดใช้ MySQL ด้วย `MYSQL_ENABLED=1` หลังติดตั้งและย้ายข้อมูลแล้ว

## 1) ติดตั้งบน Ubuntu

```bash
cd ~/https-github.com-wc42txg5sr-sketch-seven-gift-logger
git pull origin cursor/hikvision-face-attendance-starter-74a8
cd face_attendance

cp config/database.example.env config/database.env
nano config/database.env   # ตั้ง MYSQL_PASSWORD ให้แข็งแรง
```

ตัวอย่าง `database.env`:
```env
MYSQL_ENABLED=0
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_USER=faceapp
MYSQL_PASSWORD=รหัสผ่านของคุณ
MYSQL_DATABASE=face_attendance
```

รันติดตั้ง MariaDB + สร้าง DB:
```bash
chmod +x scripts/setup_mysql_ubuntu.sh
./scripts/setup_mysql_ubuntu.sh
```

## 2) ทดสอบการเชื่อมต่อ

```bash
source .venv/bin/activate
pip install -r requirements.txt
python scripts/test_mysql.py
```

## 3) ย้ายข้อมูลจากไฟล์เดิมเข้า MySQL

```bash
python scripts/migrate_files_to_mysql.py
```

จะย้าย:
- นักเรียน + embedding ใบหน้า
- ประวัติเข้า-ออก
- ปีการศึกษา / ห้อง ที่เคยเพิ่มไว้

## 4) เปิดใช้ MySQL กับเว็บ

```bash
nano config/database.env
# เปลี่ยนเป็น
MYSQL_ENABLED=1
```

รีสตาร์ทเว็บ:
```bash
sudo fuser -k 8080/tcp
./scripts/run_web.sh
```

ตรวจ health:
```bash
curl http://127.0.0.1:8080/api/health
```

## 5) เปิดให้ Navicat Premium ต่อได้

บน server:
```bash
cd face_attendance
chmod +x scripts/enable_mysql_remote.sh
./scripts/enable_mysql_remote.sh
```

ใน Navicat สร้าง connection ใหม่:

| ช่อง | ค่า |
|---|---|
| Connection Type | MySQL / MariaDB |
| Host | `192.168.10.56` (IP server) |
| Port | `3306` |
| User Name | `faceapp` |
| Password | ตาม `config/database.env` |
| Database | `face_attendance` |

กด **Test Connection** แล้ว Save

ถ้าติด:
- `sudo ufw allow 3306/tcp`
- ตรวจว่า MariaDB ฟังพอร์ต: `ss -lntp | grep 3306`
- ปิด VPN บนเครื่องที่เปิด Navicat
- ยืนยันว่าเครื่อง Navicat อยู่ subnet เดียว เช่น `192.168.10.x`

| ตาราง | ใช้เก็บ |
|---|---|
| `students` | ข้อมูลนักเรียน + embedding + รูป preview |
| `attendance` | ลงเวลาเข้า/ออก |
| `school_option_years` | ปีการศึกษาที่เพิ่มเอง |
| `school_option_rooms` | ห้องที่เพิ่มเอง |
| `app_meta` | เวอร์ชัน schema |

ไฟล์ schema อยู่ที่ `sql/schema.sql`
