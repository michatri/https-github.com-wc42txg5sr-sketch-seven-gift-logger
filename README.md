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
| งบดุล / ฐานะการเงิน | เงินสด เงินฝาก ลูกหนี้ หนี้สิน ทุน |
| ครุภัณฑ์ | ลงครุภัณฑ์ใหม่และจำหน่าย |
| ประมาณการ | งบประมาณรายรหัส + งาน/โครงการ |
| DATA | นำเข้าไฟล์ `.xlsb` เดิมได้ |

ผังบัญชีใช้รหัสชุดเดียวกับโปรแกรมวัด เช่น 4101 รับถุงทาน, 4121 รับขอมิสซา, 5201 จ่ายค่าไฟฟ้า

จำนวนเงินเก็บเป็นสตางค์ใน SQLite เพื่อไม่ให้ทศนิยมคลาดเคลื่อน

## ติดตั้งบนเซิร์ฟเวอร์ 192.168.10.65

ดูขั้นตอนเต็มใน [`DEPLOY.md`](DEPLOY.md)

จากเครื่องใน LAN:

```bash
ssh aaa@192.168.10.65
cd ~
git clone -b cursor/chatriacc-web-ebbb \
  https://github.com/michatri/https-github.com-wc42txg5sr-sketch-seven-gift-logger.git chatriacc
cd ~/chatriacc
chmod +x scripts/install_on_server.sh
sudo ./scripts/install_on_server.sh
```

เปิดจากเครื่องใน LAN: <http://192.168.10.65:8090/>

หลังติดตั้งครั้งแรก ให้เข้า **นำเข้า AC25** แล้วเลือกใช้ไฟล์ `AC25-209` ที่มากับระบบ เพื่อดึงใบสำคัญปี 2025 ของวัดนักบุญมาร์โกเข้าฐานข้อมูล

## วิธีรันบนเครื่องพัฒนา

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m chatriacc
```

เปิดเบราว์เซอร์ที่ <http://127.0.0.1:8090>

ฐานข้อมูลจะถูกสร้างที่ `data/chatriacc.db`

ตัวแปรสภาพแวดล้อม:

- `CHATRIACC_DB` — ตำแหน่งไฟล์ SQLite
- `CHATRIACC_SECRET` — secret key ของ Flask
- `CHATRIACC_HOST` / `CHATRIACC_PORT` — ที่อยู่และพอร์ตที่เปิดเว็บ

## ทดสอบ

```bash
python -m pytest -q
```

## โครงสร้างหลัก

- `chatriacc/app.py` — หน้าเว็บและเส้นทาง
- `chatriacc/db.py` — ใบสำคัญ ผังบัญชี งบ และครุภัณฑ์
- `chatriacc/importer.py` — อ่านไฟล์ AC25 `.xlsb`
- `chatriacc/chart.py` — รหัสบัญชีรับ-จ่ายมาตรฐานของวัด
- `scripts/install_on_server.sh` — ติดตั้ง systemd บน 192.168.10.65
