# ระบบบัญชีจากสลิปโอนเงิน

เว็บแอปบัญชีสำหรับบันทึกรายรับ-รายจ่ายจากสลิปโอนเงิน แล้วดูสรุปเป็นรายวัน รายเดือน และรายปี

## สิ่งที่ระบบทำได้

- บันทึกสลิปโอนเงิน: วันที่จ่าย, รอบเดือน/ปี, ชื่อพนักงาน, บริษัท
- ลงรายรับจากสลิป (เงินเดือน, OT, โบนัส, เบี้ยเลี้ยง ฯลฯ)
- ลงรายจ่ายจากสลิป (ภาษี, ประกันสังคม, กองทุนสำรองเลี้ยงชีพ ฯลฯ)
- บันทึกรายรับ-รายจ่ายเพิ่มเอง นอกเหนือจากสลิป
- ถ่ายรูปหรืออัปโหลดสลิปโอนเงิน แล้วแปลงเป็นรายรับ-รายจ่าย
- แดชบอร์ดยอดวันนี้ / เดือนนี้ / ปีนี้
- สรุปรายวัน รายเดือน รายปี พร้อมกราฟ

จำนวนเงินเก็บเป็นสตางค์ใน SQLite เพื่อไม่ให้ทศนิยมคลาดเคลื่อน

## ติดตั้งบนเซิร์ฟเวอร์ 192.168.10.56

ดูขั้นตอนเต็มใน [`DEPLOY.md`](DEPLOY.md)

SSH จากคอมใน LAN แล้วติดตั้งด้วย user `aaa`:

```bash
ssh aaa@192.168.10.56
cd ~
git clone -b cursor/accounting-payslip-cd50 \
  https://github.com/michatri/https-github.com-wc42txg5sr-sketch-seven-gift-logger.git accounting
cd ~/accounting
chmod +x scripts/install_on_server.sh
sudo ./scripts/install_on_server.sh
```

เปิดจากเครื่องใน LAN: <http://192.168.10.56:8090/>

ถ้ายังเข้าไม่ได้ รัน `./scripts/diagnose_server.sh` บนเซิร์ฟเวอร์

ระบบลงเวลาใบหน้ายังอยู่ที่ <http://192.168.10.56:8080/> และ Tomcat ที่ <http://192.168.10.56:8888/> ตามเดิม

## วิธีรันบนเครื่องพัฒนา

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m accounting
```

เปิดเบราว์เซอร์ที่ <http://127.0.0.1:8090>

ฐานข้อมูลจะถูกสร้างที่ `data/accounting.db`

ตั้งค่าเพิ่มได้ด้วยตัวแปรสภาพแวดล้อม:

- `ACCOUNTING_DB` — ตำแหน่งไฟล์ SQLite
- `ACCOUNTING_SECRET` — secret key ของ Flask
- `ACCOUNTING_HOST` / `ACCOUNTING_PORT` — ที่อยู่และพอร์ตที่เปิดเว็บ

## ทดสอบ

```bash
python -m pytest -q
```

## โครงสร้างหลัก

- `accounting/app.py` — หน้าเว็บและเส้นทาง
- `accounting/db.py` — สลิป รายการบัญชี และสรุป
- `accounting/money.py` — แปลงบาท ↔ สตางค์
- `accounting/templates/` — หน้าภาษาไทย
- `scripts/install_on_server.sh` — ติดตั้ง systemd บน 192.168.10.56
