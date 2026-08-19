# ระบบรับของบริจาคจาก 7-11

สำเนาของระบบที่ [saintmarkpathum.com](https://saintmarkpathum.com/) สำหรับมูลนิธิเซนต์มาร์ติน / เซนต์มาร์ค ปทุม — ใช้บันทึกรับของบริจาคจากสาขา 7-Eleven แล้วสรุปเป็นรายงาน / แจ้งกลุ่ม LINE

รันบนเครื่อง LAN **cameraserver `192.168.10.56` พอร์ต 8110** (ไม่ชนกับลงเวลา `:8080` บัญชีสลิป `:8090` chatriACC `:8100`)

## เปิดใช้บน 192.168.10.56

จากเครื่องใน LAN:

```bash
ssh aaa@192.168.10.56
# รหัสผ่าน: password

cd ~
git clone -b cursor/seven-gift-logger-c670 \
  https://github.com/michatri/https-github.com-wc42txg5sr-sketch-seven-gift-logger.git \
  seven-gift-logger
cd seven-gift-logger
chmod +x scripts/*.sh
sudo ./scripts/install_on_server.sh
```

จากนั้นเปิด:

- เข้าสู่ระบบ: http://192.168.10.56:8110/
- ฟอร์มสาขา: http://192.168.10.56:8110/donate
- สุขภาพระบบ: http://192.168.10.56:8110/health

บัญชีเริ่มต้น: **`admin@saintmarkpathum.com` / `admin123`** (เปลี่ยนทันทีหลังติดตั้ง)

อัปเดตภายหลัง:

```bash
cd /home/aaa/seven-gift-logger
git pull
sudo ./scripts/install_on_server.sh
```

ตรวจเครื่อง: `./scripts/diagnose_server.sh`

## หน้าที่ของระบบ (เทียบกับเว็บต้นทาง)

| หน้า | ความสามารถ |
|---|---|
| เข้าสู่ระบบ | อีเมล + รหัสผ่าน, ลืมรหัสผ่าน, ตั้งรหัสใหม่ |
| `/donate` | ฟอร์มสาธารณะ ให้สาขายืนยันรหัสร้าน แล้วบันทึกเองได้ |
| บันทึกข้อมูล | วันที่, ค้นหาสาขา, จำนวนชิ้น/ตะกร้า, ผู้ติดต่อ, น้ำหนัก, รูปถ่าย + สรุปประจำเดือน |
| รายการของที่รับบริจาค | กรองรายวัน / ช่วงวัน / เดือน, ลบรายการ, ส่งออก Excel |
| สรุปตามสาขา | รวมครั้ง/ชิ้น/น้ำหนัก รายเดือน |
| กลุ่มรับของ | สร้างกลุ่มสายรถ ผูกสาขา |
| รายงานตามกลุ่ม | คัดลอกข้อความสรุป + Excel แยกชีต |
| ข้อมูลสาขา | 38 สาขาตั้งต้นจากระบบเดิม, เพิ่มสาขา, แก้ผู้ติดต่อ |
| LINE | กลุ่มแจ้งเตือนแบบข้อความเต็ม+รูป หรือข้อความย่อ «รับของ» |

สาขาตั้งต้นครบชุดเดียวกับเว็บออนไลน์ เช่น หมู่บ้านเมืองเอก-รังสิต (`15005`), สี่แยกปทุมธานี (`11583`), เทศบาล 10 สามโคก ฯลฯ

## รันบนเครื่องพัฒนา

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest -q
GIFT_PORT=8110 .venv/bin/python app.py
```

## LINE (ถ้าต้องการแจ้งกลุ่ม)

ใส่ใน `/etc/seven-gift-logger.env` แล้ว `sudo systemctl restart seven-gift-logger`:

```
LINE_CHANNEL_ACCESS_TOKEN=...
LINE_CHANNEL_SECRET=...
PUBLIC_BASE_URL=http://192.168.10.56:8110
```

Webhook ของบอท: `http://192.168.10.56:8110/api/line/webhook` — เมื่อเพิ่มบอทเข้ากลุ่ม ระบบจะเก็บ Group ID ให้อัตโนมัติ

## หมายเหตุ

- ข้อมูลเก็บใน SQLite ที่ `data/gift_logger.db` บนเครื่อง `.56` ไม่ได้ดึงฐาน Supabase ของเว็บออนไลน์มาด้วย จึงเริ่มต้นว่าง (ยกเว้นรายชื่อสาขา)
- รูปเก็บที่ `data/photos/`
- อย่า `git checkout` ทับโฟลเดอร์ระบบลงเวลาใบหน้า
