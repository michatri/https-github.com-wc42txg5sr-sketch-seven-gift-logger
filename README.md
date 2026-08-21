# Catholic ID Web

ระบบทะเบียนสัตบุรุษบนเว็บ แปลงจากโปรแกรมเดสก์ท็อป **CatholicIDv4.5.exe** และฐานข้อมูล **Catholic.mdb**

## สิ่งที่พบในไฟล์เดิม

`CatholicIDv4.5.exe` เป็นโปรแกรม Delphi (เวอร์ชัน 4.5.0.0) ใช้ Microsoft Access ผ่าน ADO (`Catholic.mdb`) และพิมพ์เอกสารด้วย FastReport

`Catholic.mdb` (JET4) มี 5 ตาราง:

| ตาราง | ความหมาย |
| --- | --- |
| Cattolici | ทะเบียนสัตบุรุษ (ศีลล้างบาป มหาสนิท กำลัง สมรส ย้าย มรณกรรม) |
| Church | รายชื่อวัดคาทอลิกในประเทศไทย (~450 วัด) |
| MarriageNotify | ใบแจ้งการสมรส |
| Move | การย้ายเข้า/ออกวัด |
| Print | หัวกระดาษบัตร ID และจดหมายของวัด |

ข้อมูลตัวอย่างเป็นของ **วัดนักบุญยอแซฟ บ้านโป่ง** (รหัส `070104`) สังฆมณฑลราชบุรี

## รันบนเครื่องนี้

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
# ถ้ามี Catholic.mdb และ mdbtools:
#   .venv/bin/python scripts/import_mdb.py
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8222
```

เปิด http://127.0.0.1:8222 เข้าสู่ระบบด้วย `admin` / `password`

เมนู **รายงาน PDF** ดาวน์โหลดบัตรประจำตัว ใบรับรองศีล รายชื่อสัตบุรุษ ใบแจ้งสมรส เอกสารย้าย และรายชื่อวัด เป็นไฟล์ PDF

เมนู **ออกแบบหน้ารายงาน** ให้ตั้งชื่อรายงานเอง เลือกตารางจากฐานข้อมูล วางฟิลด์บนหน้ากระดาษ แล้วสร้าง PDF

## Docker

```bash
docker compose up -d --build
```

## ติดตั้งบน cameraserver (192.168.10.56)

`scripts/deploy.sh` ใช้จากเครื่องอื่นเพื่อ **ส่งโค้ดไป** เซิร์ฟเวอร์ ถ้าล็อกอินอยู่บน cameraserver อยู่แล้ว ให้ clone แล้วติดตั้งบนเครื่องนั้นโดยตรง:

```bash
cd /home/aaa
apt-get update
apt-get install -y git python3-venv python3-pip
git clone -b cursor/catholic-id-web-9576 https://github.com/michatri/https-github.com-wc42txg5sr-sketch-seven-gift-logger.git catholic-id
cd catholic-id
bash scripts/setup-server.sh
```

จากนั้นเปิด http://192.168.10.56:8222 เข้าสู่ระบบด้วย `admin` / `password`

ถ้าต้องการส่งจากเครื่องพัฒนาที่มี repo นี้อยู่แล้ว:

```bash
bash scripts/deploy.sh
```

## ฟังก์ชันหลัก

- ค้นหาสัตบุรุษตามชื่อ นามสกุล รหัส กลุ่ม ครอบครัว ทูนหัว วัดที่ล้างบาป ฯลฯ
- กรองโสด/สมรส ชาย/หญิง ยังไม่รับศีล ย้ายออก มรณะ
- บัตรประจำตัว ใบรับรองศีล ใบแจ้งสมรส เอกสารย้าย จ่าหน้าซอง รายชื่อตามกลุ่ม/ครอบครัว
- รายชื่อวัดทั้งประเทศ แก้ไขข้อมูลวัดและหัวกระดาษพิมพ์
