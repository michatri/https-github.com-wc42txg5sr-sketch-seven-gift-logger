# School Check-in Admin Web

เว็บแอดมินสำหรับ:
- ลงทะเบียนนักเรียน (รหัส / ชื่อ / นามสกุล + สแกนลายนิ้วมือ)
- ดูรายชื่อนักเรียน
- ดูเวลาเข้า

## รันบน Raspberry Pi

```bash
cd /home/master/school-app/admin-web
source .venv/bin/activate
pip install -r requirements.txt
export SCHOOL_DB=/home/master/fingerprint-test/school.db
pkill -f "python app.py" || true
nohup python app.py > /tmp/admin-web.log 2>&1 &
```

เปิดจากคอมใน LAN เดียวกัน:
- เวลาเข้า: `http://192.168.10.55:5000/`
- ลงทะเบียน: `http://192.168.10.55:5000/register`
