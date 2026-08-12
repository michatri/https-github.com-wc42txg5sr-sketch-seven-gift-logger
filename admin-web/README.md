# School Check-in Admin Web

เว็บแอดมินดูรายชื่อนักเรียนและเวลาเข้า จากฐานข้อมูล `school.db`

## รันบน Raspberry Pi

```bash
cd /home/master/fingerprint-test
python3 -m venv .venv
source .venv/bin/activate
pip install flask

# คัดลอกโฟลเดอร์ admin-web มาไว้ข้างๆ school.db แล้ว:
cd /home/master/admin-web
export SCHOOL_DB=/home/master/fingerprint-test/school.db
python app.py
```

เปิดจากคอมใน LAN เดียวกัน: `http://192.168.10.55:5000/`
