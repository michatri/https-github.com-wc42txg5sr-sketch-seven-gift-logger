# Report Designer — Analysis (Catholic ID Web)

เอกสารนี้จัดทำ**ก่อน**ลงมือเขียนโมดูลออกแบบรายงานตามข้อกำหนด
(เลือกข้อมูล → เลือกฟิลด์ → ลากวาง → ออกแบบ → ตัวอย่าง → บันทึก → พิมพ์ → PDF)
โดยไม่เขียนทับตรรกะทะเบียนเดิม และไม่ให้เบราว์เซอร์เชื่อมต่อไฟล์ MDB โดยตรง

---

## 1. Existing architecture

| ชั้น | ของเดิมในโปรเจกต์นี้ | คงไว้ / ไม่ทำ |
| --- | --- | --- |
| Frontend | Jinja2 + HTML/CSS/vanilla JS (Sarabun, โทน burgundy/gold) | คงไว้ ไม่ย้ายไป React/Vue |
| Backend | FastAPI (`app/main.py`) พอร์ต **8222** | คงไว้ เพิ่ม router ใหม่ |
| Auth | Session cookie `catholicid` + `users` (pbkdf2_sha256) | **ไม่เปลี่ยน** ระบบล็อกอิน |
| PDF สำเร็จรูป | `app/pdfs.py` + fpdf2 + ฟอนต์ Sarabun | คงเมนูเดิม ที่ `/reports/library` |
| ออกแบบแบบง่าย | `app/designer.py` + ตาราง `report_designs` | คง `/designer` ไม่ลบ |
| Routing | หน้า HTML ใน FastAPI, ไม่มี SPA | เพิ่ม `/reports/*` และ `/api/*` |

สถาปัตยกรรมที่ implement:

```
Browser
   |
   v
Jinja2 + vanilla JS  (ไม่คุยกับไฟล์ .mdb)
   |
   v
FastAPI  (Report Service, Query Builder, Permission, PDF)
   |
   v
Database Adapter  (SQLite, read-only เมื่อรันรายงาน)
   |
   v
catholic.db  ← นำเข้าจาก Catholic.mdb (Jet) ผ่าน scripts/import_mdb.py
```

เบราว์เซอร์**ไม่มี** connection string ไปยัง Access/Jet

---

## 2. Database architecture

แหล่งต้นทาง: **Catholic.mdb (JET4)** ตารางจริง 5 ตาราง  
รันไทม์เว็บ: **SQLite** ที่ `app/data/catholic.db` (คัดลอกโครงสร้าง/ข้อมูล ไม่เปลี่ยนชื่อคอลัมน์ธุรกิจ)

| MDB | SQLite | บทบาท |
| --- | --- | --- |
| Cattolici | `members` | ทะเบียนสัตบุรุษ / ศีล |
| Church | `churches` | รายชื่อวัด |
| MarriageNotify | `marriage_notifies` | ใบแจ้งสมรส |
| Move | `moves` | ย้ายเข้า–ออก |
| Print | `parish_settings` | หัวกระดาษ / บัตร |

คอลัมน์ธุรกิจ (เช่น `MarriageID` ใน MDB → `marriage_id` ใน SQLite ตามที่ import ไว้แล้ว, `family_No` → `family_no`, `birth_date`, `btsm_date`, `cnfm_date`, `Priest` → `priest`, `Witness1`/`Witness2`, `address1`/`address2`, `occupation`, `dead_date`) **ห้ามเปลี่ยนในงานนี้**

ตารางที่ระบบรายงานสร้างขึ้นเอง (metadata เท่านั้น — ไม่แก้ตารางทะเบียน):

- `report_data_sources`
- `report_datasets`
- `reports`
- `report_parameters`
- `report_permissions`
- `report_versions`

ตารางเดิม `report_designs` ของ `/designer` **ไม่ลบ**

ตาราง `users` ไม่ใช่แหล่งรายงานของวัด — ไม่โชว์ `password_hash` และไม่ให้ SELECT คอลัมน์ลับ

### จอยที่ปลอดภัย (ต้องให้ผู้ใช้เลือกเอง ไม่จอยอัตโนมัติ)

- `moves.member_id` → `members.id` (มี FK ใน schema)
- `marriage_notifies.member_id` → `members.id` (คอลัมน์มีอยู่ แต่เดิมไม่มี FK)

**ห้าม**จอยอัตโนมัติ `members.go_church` กับ `churches.name` (ข้อความอิสระ ไม่ใช่รหัสวัด)

---

## 3. Existing report architecture

### 3.1 FastReport ในไฟล์เดสก์ท็อป

`CatholicIDv4.5.exe` เป็น Delphi 4.5 ใช้ FastReport (`TfrxReport`)  
**ไม่พบ**ไฟล์ `.fr3` / `.frf` / prepared report ในรีโปหรือในชุดอัปโหลด  
เทมเพลตฝังใน EXE (~20 รายงาน) — **ห้ามทำลาย** เพราะไม่มีไฟล์แยกให้ทำลาย

รายงานสำเร็จรูปที่พอร์ตแล้วในเว็บ (เทียบเท่า FastReport เดิม):

- บัตรประจำตัว, ใบรับรองศีล, ประวัติสัตบุรุษ, จ่าหน้าซอง
- รายชื่อตามอักษร / นักบุญ / กลุ่ม / รหัส / ครอบครัว / สรุป
- ใบแจ้งสมรส, เอกสารย้าย, รายชื่อวัด

ย้ายฮับนี้จาก `/reports` ไป `/reports/library` เพื่อให้ `/reports` เป็นรายการรายงานที่ผู้ใช้สร้างเองตามสเปกใหม่

### 3.2 ตัวออกแบบเดิม (`/designer`)

เก็บ JSON ใน `report_designs` โหมด `form` / `list` ออกรายงานด้วย `design_pdf()`  
ยังใช้ได้คู่กับตัวออกแบบใหม่ ไม่ย้ายข้อมูลอัตโนมัติ (โครงสร้างคนละแบบ)

### 3.3 กลยุทธ์นำเข้า FastReport

1. คงรายงานสำเร็จรูปใน `/reports/library`
2. ไม่เขียนตัวแปลง `.fr3` จนกว่าจะมีไฟล์เทมเพลตจริงจากลูกค้า
3. ถ้ามี `.fr3` ในอนาคต: แมป DataSet → `report_datasets.query_config_json`, แถบ Header/Detail/Footer → `layout_json.sections`, Memo/Picture → components
4. รายงานที่ผู้ใช้สร้างใหม่เก็บเป็น JSON ตามสเปก ไม่เก็บ HTML ดิบ

---

## 4. Recommended architecture

ชั้นบริการในแบ็กเอนด์:

| บริการ | หน้าที่ |
| --- | --- |
| Data Source browser | อ่าน `sqlite_master` / `PRAGMA table_info` / `PRAGMA foreign_key_list` |
| Query Builder | คอมไพล์ JSON → SELECT เท่านั้น ผูกพารามิเตอร์แบบ bound |
| Report Service | CRUD รายงาน, สำเนา, รายการ, autosave |
| Permission Service | can_view / can_edit / can_print / can_export_pdf |
| PDF Service | fpdf2 + Sarabun ให้ตัวอย่างกับ PDF ใช้พิกัดเดียวกัน |

ข้อจำกัดความปลอดภัย:

- ผู้ใช้ทั่วไปสร้างคิวรีด้วย UI เท่านั้น ไม่พิมพ์ SQL
- Admin อาจวาง SELECT ขั้นสูงได้ แต่ต้องผ่านตัวตรวจ (ห้าม INSERT/UPDATE/DELETE/DROP/ALTER/CREATE/TRUNCATE/EXEC/EXECUTE/ATTACH)
- รันข้อมูลด้วย `PRAGMA query_only=ON`
- LIMIT / หน้า / timeout / ไม่โหลดทั้งตารางเข้าเบราว์เซอร์
- ข้อผิดพลาดฐานข้อมูลไม่โชว์ดิบ — ข้อความไทย + log ฝั่งเซิร์ฟเวอร์

---

## 5. Migration strategy

1. `ensure_schema()` สร้างตาราง metadata ถ้ายังไม่มี (ฐานที่มีอยู่ไม่ต้อง import MDB ใหม่)
2. Seed แหล่งข้อมูล 1 รายการ: «ทะเบียนสัตบุรุษ (Catholic.mdb)» adapter=`sqlite`
3. ไม่รัน DDL บนตาราง `members` / `churches` / `marriage_notifies` / `moves` / `parish_settings`
4. ย้ายหน้า PDF สำเร็จรูปไป `/reports/library` อัปเดตเมนูและเทส
5. `/designer` คงเดิม

ไม่ใช้ Alembic — โปรเจกต์นี้ใช้ `CREATE TABLE IF NOT EXISTS` อยู่แล้ว

---

## 6. Risks

| ความเสี่ยง | การจัดการ |
| --- | --- |
| จอยผิดทำให้คาร์ทีเซียน | จอยเมื่อผู้ใช้เลือก; แนะนำเฉพาะ FK ที่รู้จัก |
| SELECT * ดึงแสนแถว | MAX_ROWS, หน้า, ไม่ส่งแถวเกินหน้าไป UI |
| SQL injection จากชื่อตาราง/คอลัมน์ | whitelist ident + quote + ตรวจ schema จริง |
| โชว์ password_hash | บล็อกคอลัมน์ลับเสมอ |
| PDF ไม่ตรงตัวอย่าง | renderer ชุดเดียว (mm) สำหรับ HTML/PDF |
| ไม่มีไฟล์ FastReport | ไม่เดาเลย์เอาต์จาก EXE; ใช้ library สำเร็จรูป |
| ชื่อฟิลด์ MDB vs SQLite | แสดงชื่อ SQLite จริง + ป้ายไทย; ไม่เปลี่ยน schema |

---

## 7. Dependencies

ของเดิม: FastAPI, Jinja2, fpdf2, passlib, pytest  
เพิ่ม (ถ้ามีใน requirements): `qrcode` สำหรับคอมโพเนนต์ QR (ไม่มีก็แสดงตัวแทนข้อความ)

ไม่เพิ่ม ORM, ไม่เพิ่ม React

---

## 8. Implementation phases

| เฟส | งาน |
| --- | --- |
| 1 | วิเคราะห์ (เอกสารนี้) |
| 2 | ตาราง metadata + seed data source |
| 3 | Data Source browser (ตาราง/คอลัมน์/ชนิด/PK/ความสัมพันธ์) |
| 4 | Dataset / Query Builder (SELECT/WHERE/JOIN/GROUP/AGG/ORDER/LIMIT/พารามิเตอร์) |
| 5 | รายการรายงาน ค้นหา กรอง เรียง โปรด สำเนา ลบ |
| 6–7 | ตัวออกแบบลากวาง (แถบ, คอมโพเนนต์, คุณสมบัติ) |
| 8 | ตัวอย่าง + หน้า + ไม่มีข้อมูล/โหลด/ผิดพลาด |
| 9 | ส่งออก PDF (A4/A5/Letter, ไทย, หัวตารางซ้ำ) |
| 10 | พิมพ์จากเบราว์เซอร์ |
| 11 | สิทธิ์ดู/แก้/พิมพ์/PDF |
| 12 | เวอร์ชัน + restore |
| 13 | Autosave 20 วินาที + Ctrl+S |

หลังแต่ละเฟสหลัก: `pytest` และตรวจว่าล็อกอิน / สัตบุรุษ / PDF สำเร็จรูป / `/designer` ยังผ่าน

---

## 9. UI language

ป้ายหลักเป็นภาษาไทย: รายงาน, สร้างรายงาน, แก้ไขรายงาน, บันทึกรายงาน, ดูตัวอย่าง, พิมพ์, ส่งออก PDF, ข้อมูล, ฟิลด์, ตัวกรอง, เรียงลำดับ, จัดกลุ่ม, คุณสมบัติ

บทสนทนาก่อนรัน: วันที่เริ่มต้น / สิ้นสุด / โบสถ์ ฯลฯ จาก `report_parameters`

---

## 10. Implementation notes (after coding)

### Files created
- `REPORT_DESIGNER_ANALYSIS.md`
- `app/report_schema.py` — metadata DDL, schema browser
- `app/query_builder.py` — visual query → SELECT
- `app/report_engine.py` — preview HTML + PDF
- `app/reports.py` — pages + `/api/*`
- Templates: `report_list.html`, `report_wizard.html`, `report_designer.html`, `report_preview.html`, `report_print.html`, `report_sources.html`
- JS: `report-list.js`, `report-wizard.js`, `report-designer.js`, `report-preview.js`, `report-sources.js`
- CSS: `app/static/css/reports.css`
- Tests: `tests/test_reports.py`, `tests/conftest.py`

### Files modified
- `app/db.py` — `ensure_schema` สร้างตารางรายงาน
- `scripts/import_mdb.py` — เรียก schema รายงานตอน init
- `app/main.py` — include reports router, ย้ายฮับ PDF ออกจาก `/reports`
- `app/templates/base.html`, `dashboard.html`, `reports.html`
- `tests/test_app.py`, `README.md`

### Database migrations
ไม่มี Alembic — ใช้ `CREATE TABLE IF NOT EXISTS` ใน `ensure_report_schema()`:
`report_data_sources`, `report_datasets`, `reports`, `report_parameters`, `report_permissions`, `report_versions`  
ตารางทะเบียนเดิมไม่ถูก ALTER

### API endpoints
ตามสเปก: `/api/reports`, `/api/datasets`, `/api/data-sources` รวม preview/pdf/print/duplicate/versions/restore-version  
เพิ่ม `POST /api/query/preview` สำหรับวิซาร์ดก่อนบันทึก

### Dependencies
ของเดิมเท่านั้น (FastAPI, Jinja2, fpdf2). QR ใช้แพ็กเกจ `qrcode` ถ้ามี ไม่งั้นแสดงข้อความแทน

### How to run / test
```bash
python3 -m pip install -r requirements.txt
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8222
python3 -m pytest tests -q
```

บน cameraserver: `git pull` แล้ว `bash scripts/setup-server.sh`

### Report Designer usage
สร้างรายงาน → เลือกแหล่งข้อมูล/ตาราง/ฟิลด์ → ความสัมพันธ์ (opt-in) → ตัวกรอง → ออกแบบ → ตัวอย่าง → บันทึก  
จากรายการ: แก้ไข / ดูตัวอย่าง / พิมพ์ / PDF / สำเนา / ลบ / ติดดาว  
Ctrl+S และ autosave 20 วินาที

### Security
SELECT เท่านั้น, `PRAGMA query_only`, บล็อกคำสั่งเขียน, บล็อก `users`/`password_hash`, LIMIT/timeout, ข้อผิดพลาดไทย

### Known limitations
- ไม่มีไฟล์ `.fr3` ให้แปลง — รายงาน FastReport เดิมอยู่ที่ `/reports/library`
- รายงานย่อย/แผนภูมิ/บาร์โค้ดเป็นเวอร์ชันแรก (แสดงได้ แต่ไม่เทียบสแกนเนอร์ระดับอุตสาหกรรม)
- QR ใน PDF สมบูรณ์เมื่อติดตั้ง `qrcode`+Pillow
- จอยต้องเลือกเอง ไม่จอย `go_church` ↔ ชื่อวัดอัตโนมัติ

