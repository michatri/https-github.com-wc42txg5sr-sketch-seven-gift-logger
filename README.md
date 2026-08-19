# ระบบรับของบริจาคจาก 7-11

สำเนาของโปรเจกต์ Lovable
[ระบบรับของบริจาค 7-Eleven](https://lovable.dev/projects/15a6aed2-ef54-4c0b-90e6-d418a315bf3b)
(เว็บที่เผยแพร่แล้ว: [saintmarkpathum.com](https://saintmarkpathum.com/))
สำหรับมูลนิธิเซนต์มาร์ติน / เซนต์มาร์ค ปทุม

ย้ายมาทำงานบนเครื่อง LAN **cameraserver `192.168.10.56` พอร์ต 8110**
(ไม่ชนกับลงเวลา `:8080` บัญชีสลิป `:8090` chatriACC `:8100`)

หน้าจอและเมนูเทียบกับต้นฉบับ:

- `/` เข้าสู่ระบบ → บันทึกข้อมูล / รายการของที่รับบริจาค / สรุปตามสาขา / กลุ่มรับของ / รายงานตามกลุ่ม / ข้อมูลสาขา / LINE
- `/donate` ฟอร์มสาธารณะให้สาขายืนยันรหัสร้านแล้วบันทึกเอง
- `/reset-password` ตั้งรหัสผ่านใหม่

## เปิดใช้บน 192.168.10.56

จากเครื่องใน LAN:

```bash
ssh aaa@192.168.10.56
# รหัสผ่าน: password

cd ~
git clone -b cursor/lovable-gift-logger-d906 \
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

## ข้อมูลที่ย้ายมาแล้ว

ติดตั้งแล้วนำเข้าจากระบบออนไลน์อัตโนมัติ:

- **3,129 รายการรับของ** (รวม 53,566 ชิ้น)
- **43 สาขา** + ผู้ติดต่อล่าสุดของแต่ละสาขา
- **กลุ่ม LINE 5 กลุ่ม**
- **รูป 28 ไฟล์** (ดาวน์โหลดตอนติดตั้งถ้าเครื่องออกเน็ตได้)

## รันบนเครื่องพัฒนา

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest -q
.venv/bin/python scripts/import_production.py
GIFT_PORT=8110 GIFT_BIND=0.0.0.0 \
  PUBLIC_BASE_URL=http://192.168.10.56:8110 \
  .venv/bin/python app.py
```

## LINE (ถ้าต้องการแจ้งกลุ่ม)

ใส่ใน `/etc/seven-gift-logger.env` แล้ว `sudo systemctl restart seven-gift-logger`:

```
LINE_CHANNEL_ACCESS_TOKEN=...
LINE_CHANNEL_SECRET=...
PUBLIC_BASE_URL=http://192.168.10.56:8110
```

Webhook ของบอท: `http://192.168.10.56:8110/api/line/webhook`

## หมายเหตุ

- ข้อมูลรายการอยู่ใน `data/import/snapshot.json` และถูกนำเข้า SQLite `data/gift_logger.db` ตอนติดตั้ง
- รูปเก็บที่ `data/photos/`
- อย่า `git checkout` ทับโฟลเดอร์ระบบลงเวลาใบหน้า
