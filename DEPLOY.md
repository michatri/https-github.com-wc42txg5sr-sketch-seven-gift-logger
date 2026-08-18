# ติดตั้งบน Ubuntu server 192.168.10.56

เข้า `http://192.168.10.56:8090/` ไม่ได้จนกว่าจะ **ติดตั้งและสตาร์ทบริการบนเซิร์ฟเวอร์แล้ว**  
Cloud agent SSH เข้าเครื่องนี้ไม่ได้ ต้องรันคำสั่งด้านล่างบน `cameraserver` เอง

บัญชีที่ใช้: **aaa**

## ติดตั้ง (คัดลอกทั้งก้อน รันบนเซิร์ฟเวอร์)

จากคอมใน LAN:

```bash
ssh aaa@192.168.10.56
```

แล้ววางคำสั่งนี้:

```bash
sudo apt-get update
sudo apt-get install -y git python3 python3-venv python3-pip curl
cd ~
git clone -b cursor/accounting-payslip-cd50 \
  https://github.com/michatri/https-github.com-wc42txg5sr-sketch-seven-gift-logger.git accounting
cd ~/accounting
chmod +x scripts/bootstrap.sh scripts/install_on_server.sh scripts/diagnose_server.sh
sudo ./scripts/install_on_server.sh
```

ถ้าติดตั้งสำเร็จ บนเซิร์ฟเวอร์ต้องขึ้นว่าเรียก `/health` ได้ จากนั้นเปิดจากคอม:

- http://192.168.10.56:8090/
- http://192.168.10.56/  (ถ้าพอร์ต 80 ว่าง)

อย่าไป `git checkout` ทับโฟลเดอร์ระบบลงเวลาที่ `/root/https-github.com-wc42txg5sr-sketch-seven-gift-logger`

## ถ้ายังเข้าไม่ได้

รันบนเซิร์ฟเวอร์แล้วส่งผลมา:

```bash
cd ~/accounting
./scripts/diagnose_server.sh
```

ตรวจเร็วๆ:

```bash
systemctl status accounting
curl -v http://127.0.0.1:8090/health
sudo ufw allow 8090/tcp
sudo ufw allow 80/tcp
sudo ufw reload
```

- `curl` บนเซิร์ฟเวอร์ไม่ได้ = บริการยังไม่ขึ้น ดู `journalctl -u accounting -n 80`
- `curl` บนเซิร์ฟเวอร์ได้ แต่คอมเข้าไม่ได้ = ไฟร์วอลล์บล็อกพอร์ต 8090

## อัปเดตภายหลัง

```bash
cd ~/accounting
git pull origin cursor/accounting-payslip-cd50
sudo ./scripts/install_on_server.sh
```

## พอร์ตบนเครื่องนี้

| ระบบ | URL |
|---|---|
| บัญชีรายรับ-รายจ่าย | http://192.168.10.56:8090/ |
| ลงเวลาด้วยใบหน้า | http://192.168.10.56:8080/ |
| Jakarta Tomcat | http://192.168.10.56:8888/ |
