# ติดตั้ง Jakarta Tomcat (Apache Tomcat 10)

Tomcat ใช้สำหรับรันเว็บแอป Java (WAR)  
ระบบ Face Attendance ปัจจุบันเป็น Python (FastAPI) ยังรันด้วย systemd ที่พอร์ต **8080**  
จึงตั้ง Tomcat ที่พอร์ต **8888** เพื่อไม่ชนกัน

## ติดตั้งบน Ubuntu

```bash
cd ~/https-github.com-wc42txg5sr-sketch-seven-gift-logger
git pull origin cursor/hikvision-face-attendance-starter-74a8
cd face_attendance

chmod +x scripts/setup_tomcat_ubuntu.sh
./scripts/setup_tomcat_ubuntu.sh
```

เปิดเบราว์เซอร์:
```text
http://192.168.10.56:8888/
```

## พอร์ตที่แยกกัน

| บริการ | พอร์ต | วิธีเปิด |
|---|---|---|
| Face Attendance (Python) | 8080 | `face-attendance.service` |
| Jakarta Tomcat | 8888 | `tomcat10.service` |
| MySQL/MariaDB | 3306 | `mariadb` / `mysql` |

## คำสั่งใช้ประจำ

```bash
sudo systemctl status tomcat10
sudo systemctl restart tomcat10
sudo journalctl -u tomcat10 -f
```

วางแอป Java:
```bash
sudo cp your-app.war /var/lib/tomcat10/webapps/
sudo systemctl restart tomcat10
```

## ถ้าต้องการให้ Tomcat ใช้พอร์ตอื่น

```bash
TOMCAT_HTTP_PORT=9080 ./scripts/setup_tomcat_ubuntu.sh
sudo ufw allow 9080/tcp
```

## สิ่งที่ควรรู้

- Tomcat **ไม่ได้แทน** `./scripts/run_web.sh` / `face-attendance.service`
- ถ้าต้องการ reverse proxy รวมพอร์ตเดียว (เช่น 80) แนะนำใช้ Nginx นำหน้าทั้งสองบริการ
