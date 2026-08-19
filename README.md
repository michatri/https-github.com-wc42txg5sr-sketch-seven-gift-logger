# chatriACC

เว็บแอปบัญชีวัด แปลงจากโปรแกรม Excel **AC25-209** (ใบสำคัญรับ / ใบสำคัญจ่าย ของอัครสังฆมณฑลกรุงเทพฯ) ให้ใช้ผ่านเบราว์เซอร์ในชื่อ **chatriACC**

## สิ่งที่ระบบทำได้

เทียบกับชีทในไฟล์ `AC25-209.xlsb`:

| โปรแกรม Excel | chatriACC |
|---|---|
| ใบสำคัญ | บันทึกใบสำคัญรับ (CRV) / จ่าย (CPV) ไม่เกิน 7 รายการต่อใบ |
| พิมพ์_ยกเลิก | พิมพ์ใบสำคัญ และยกเลิกแล้วทำใหม่ (เรียกคืนไม่ได้) |
| บัญชีรับ / บัญชีจ่าย | ดูรายเดือนตามรหัสบัญชีวัด |
| งบบัญชี | งบบัญชีรับจ่ายรายเดือนทั้งปี |
| รายงานรหัสบัญชี | เลือกรหัสบัญชี เรียงตามรหัส และมียอดสรุปรายรหัส/ทั้งรายงาน |
| งบดุล / ฐานะการเงิน | เงินสด เงินฝาก ลูกหนี้ หนี้สิน ทุน |
| ครุภัณฑ์ | ลงครุภัณฑ์ใหม่และจำหน่าย |
| ประมาณการ | งบประมาณรายรหัส + งาน/โครงการ |
| DATA | นำเข้าไฟล์ `.xlsb` รายปี (AC25-209, AC26-209, …) |
| ปีบัญชี | เตรียมปีใหม่โดยไม่ลบปีเก่า แล้วเลือกปีจากเมนูซ้าย |

ผังบัญชีใช้รหัสชุดเดียวกับโปรแกรมวัด เช่น 4101 รับถุงทาน, 4121 รับขอมิสซา, 5201 จ่ายค่าไฟฟ้า

จำนวนเงินเก็บเป็นสตางค์ใน SQLite เพื่อไม่ให้ทศนิยมคลาดเคลื่อน

## ติดตั้งบน cameraserver 192.168.10.56

ดูขั้นตอนเต็มใน [`DEPLOY.md`](DEPLOY.md) รวมวิธีย้ายขึ้น **VPS IP จริง**

เครื่องที่เปิดเว็บลงเวลาได้จริงใน LAN คือ **192.168.10.56** ไม่ใช่ `.65`

จากเครื่องใน LAN:

```bash
ssh aaa@192.168.10.56
cd ~
git clone -b cursor/chatriacc-web-ebbb \
  https://github.com/michatri/https-github.com-wc42txg5sr-sketch-seven-gift-logger.git chatriacc
cd ~/chatriacc
chmod +x scripts/install_on_server.sh
sudo ./scripts/install_on_server.sh
```

เปิดจากเครื่องใน LAN: **http://192.168.10.56:8100/** (ต้องมี `http://` และ `:8100`)

พิมพ์ `.65` หรือใช้ `https://` จะขึ้นว่าใช้เวลาตอบกลับนานเกินไป

ถ้า `chatriacc.service` ขึ้น `Failed with result 'exit-code'` หรือเข้าเว็บไม่ได้ ให้ `git pull` แล้วรัน:

```bash
chmod +x scripts/*.sh
sudo ./scripts/install_on_server.sh
sudo ./scripts/open_lan_ports.sh
```

ตอนติดตั้ง (และตอนสตาร์ทถ้าฐานยังว่าง) ระบบจะนำเข้าไฟล์ `chatriacc/seed/AC25-209.xlsb` เข้า SQLite ให้อัตโนมัติ — ใบสำคัญรับ/จ่าย ปี 2025 ของวัดนักบุญมาร์โกจะอยู่ในฐานทันที ไม่ต้องกดนำเข้าเอง

## วิธีรันบนเครื่องพัฒนา

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m chatriacc
```

เปิดเบราว์เซอร์ที่ <http://127.0.0.1:8100>

ฐานข้อมูลจะถูกสร้างที่ `data/chatriacc.db`

ตัวแปรสภาพแวดล้อม:

- `CHATRIACC_DB` — ตำแหน่งไฟล์ SQLite
- `CHATRIACC_SECRET` — secret key ของ Flask
- `CHATRIACC_HOST` / `CHATRIACC_PORT` — ที่อยู่และพอร์ตที่เปิดเว็บ (ค่าเริ่มต้นพอร์ต **8100**)

## ทดสอบ

```bash
python -m pytest -q
```

## โครงสร้างหลัก

- `chatriacc/app.py` — หน้าเว็บและเส้นทาง
- `chatriacc/db.py` — ใบสำคัญ ผังบัญชี งบ และครุภัณฑ์
- `chatriacc/importer.py` — อ่านไฟล์ AC25 `.xlsb`
- `chatriacc/chart.py` — รหัสบัญชีรับ-จ่ายมาตรฐานของวัด
- `scripts/install_on_server.sh` — ติดตั้ง systemd บน cameraserver 192.168.10.56
