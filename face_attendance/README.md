# ต้นแบบทดสอบลงเวลาด้วยใบหน้า — Hikvision DS-2CD2146G2-I (4mm)

โปรเจกต์นี้เป็น **ขั้นเริ่มต้นสำหรับทดสอบจริง** ด้วยกล้องที่มีอยู่แล้ว  
โฟกัส 4 อย่าง: เชื่อม RTSP → ตรวจหลายใบหน้า → ลงทะเบียน → ลงเวลา

> กล้องรุ่นนี้มีแค่ **Face Capture** ไม่ได้รู้ว่าเป็นใคร  
> การจดจำ/ลงเวลาทำงานบนเครื่องที่รันสคริปต์นี้

---

## สิ่งที่ต้องมีก่อนรัน

1. กล้องต่อ LAN / PoE แล้ว และรู้ IP (เช่น `192.168.1.64`)
2. เปิดเว็บกล้องได้ (`http://IP`) ด้วย user/password
3. คอม/โน้ตบุ๊กเครื่องเดียวกับ LAN กล้อง (Windows/Linux/Mac)
4. Python 3.10+ และ `ffmpeg`

### ตั้งค่าบนกล้อง (ทำครั้งแรก ~10 นาที)

1. Configuration → Network → Basic: ตั้ง **IP คงที่**
2. Configuration → Network → Advanced → Integration Protocol: เปิด **RTSP**
3. Configuration → System → System Settings → Time: ตั้ง NTP ให้เวลาตรง
4. (ถ้าต้องการใช้ Face Capture ของกล้องภายหลัง)  
   Configuration → Event → Smart Event → **Face Capture = Enable**  
   หมายเหตุ: เปิด Face Capture แล้ว AcuSense human/vehicle อาจปิดเอง
5. ทดสอบดู live view ในเว็บกล้อง ให้เห็นใบหน้าชัดที่ระยะ 1.5–4 ม.

RTSP ของ Hikvision โดยทั่วไป:

```text
rtsp://USER:PASS@CAMERA_IP:554/Streaming/Channels/101   # main (คม)
rtsp://USER:PASS@CAMERA_IP:554/Streaming/Channels/102   # sub  (เบา)
```

---

## ติดตั้งบนเครื่องทดสอบ

```bash
cd face_attendance
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp config/camera.example.env config/camera.env
# แก้ CAMERA_IP / CAMERA_USER / CAMERA_PASS
```

ทดสอบ pipeline แบบไม่มีกล้องก่อนได้:

```bash
python scripts/selftest_offline.py
```

---

## ลำดับทดสอบกับกล้องจริง

### ขั้น 1 — เชื่อมกล้องได้ไหม

```bash
python scripts/check_camera.py
```

สำเร็จจะได้รูป snapshot ใน `data/captures/camera_ok_*.jpg`

ถ้าไม่ได้:
- ping IP กล้อง
- รหัสผ่านมีอักขระพิเศษ → ใส่ `RTSP_URL=` ใน `camera.env` แบบ URL-encode
- ลอง channel `102`
- ปิด VPN / เช็กว่าคอมกับกล้องอยู่ subnet เดียวกัน

### ขั้น 2 — ตรวจหลายใบหน้าพร้อมกัน

ยืน 2–3 คนหน้ากล้อง แล้วรัน:

```bash
python scripts/detect_faces.py --frames 3
```

ดูผลที่ `data/captures/faces_*.jpg`  
เป้าหมายขั้นนี้: **นับใบหน้าถูก** ยังไม่ต้องรู้ชื่อ

### ขั้น 3 — ลงทะเบียนนักเรียนทดสอบ 2–3 คน

จากรูปถ่ายชัด ๆ:

```bash
python scripts/enroll_face.py --person-id S001_somchai --image /path/to/somchai.jpg
python scripts/enroll_face.py --person-id S002_malee --image /path/to/malee.jpg
```

หรือยืนคนเดียวหน้ากล้อง:

```bash
python scripts/enroll_face.py --person-id S001_somchai --from-camera
```

ข้อมูลจะอยู่ที่ `data/gallery/<person_id>/`

### ขั้น 4 — ทดสอบลงเวลาหลายคน

```bash
python scripts/live_attendance.py --seconds 60
```

- จดจำได้จะพิมพ์ `[ATTEND] ...`
- บันทึก CSV ที่ `data/attendance/attendance_*.csv`
- ภาพล่าสุดที่ `data/attendance/live_preview_*.jpg`

ปรับความเข้มงวดใน `config/camera.env`:

- `MATCH_THRESHOLD=0.42` (สูง = เข้มขึ้น ลดจับผิด / อาจพลาดคนจริง)
- `COOLDOWN_SECONDS=120` (กันลงซ้ำ)

---

## เกณฑ์ผ่านของรอบทดสอบแรก

| รายการ | ผ่านเมื่อ |
|---|---|
| RTSP | ได้ snapshot คม ไม่ดำ/ไม่ค้าง |
| Multi-face | 2–3 คนในเฟรม ถูกกรอบครบ |
| Enroll | สร้าง gallery ได้ |
| Match | คนที่ลงทะเบียนแล้วถูกเรียกชื่อ |
| Unknown | คนแปลกหน้าเป็น `unknown` |
| Anti-duplicate | คนเดิมไม่ลงซ้ำภายใน cooldown |

---

## โครงโฟลเดอร์

```text
face_attendance/
  config/camera.example.env
  models/          # YuNet detect + SFace recognize
  lib/             # RTSP + face pipeline
  scripts/         # ขั้นทดสอบ 1–4
  data/
    gallery/       # คนที่ลงทะเบียน
    captures/      # รูปตรวจจับ
    attendance/    # CSV ลงเวลา
```

---

## ขั้นถัดไปหลังทดสอบผ่าน

1. ลงทะเบียนทั้งห้อง/ทั้งโรงเรียน (รูปตรงหน้า ถอดแว่นดำ/หมวก)
2. ย้ายจากสคริปต์ → API + หน้าเว็บครู
3. เพิ่มกฎสาย/ขาด, ส่งรายงาน
4. ถ้าคนแน่นช่วงเช้ามาก: เพิ่มกล้อง หรือใช้ GPU + โมเดล InsightFace

โมเดลในโปรโตไทป์นี้เป็น OpenCV Zoo (YuNet + SFace) รันบน CPU ได้ เหมาะทดสอบ  
ระบบจริงที่คนเยอะค่อยอัปเกรดโมเดลทีหลังได้โดยไม่ต้องเปลี่ยนกล้อง
