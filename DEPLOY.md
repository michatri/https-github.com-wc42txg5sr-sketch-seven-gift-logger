# ติดตั้ง chatriACC บน Ubuntu server 192.168.10.65

เข้า `http://192.168.10.65:8090/` ไม่ได้จนกว่าจะ **ติดตั้งและสตาร์ทบริการบนเซิร์ฟเวอร์แล้ว**  
Cloud agent SSH เข้าเครื่องนี้ไม่ได้ ต้องรันคำสั่งด้านล่างบนเครื่องใน LAN เอง

บัญชีที่ใช้: **aaa**

## ติดตั้ง (คัดลอกทั้งก้อน รันบนเซิร์ฟเวอร์)

จากคอมใน LAN:

```bash
ssh aaa@192.168.10.65
```

แล้ววางคำสั่งนี้:

```bash
sudo apt-get update
sudo apt-get install -y git python3 python3-venv python3-pip curl
cd ~
git clone -b cursor/chatriacc-web-ebbb \
  https://github.com/michatri/https-github.com-wc42txg5sr-sketch-seven-gift-logger.git chatriacc
cd ~/chatriacc
chmod +x scripts/bootstrap.sh scripts/install_on_server.sh scripts/diagnose_server.sh
sudo ./scripts/install_on_server.sh
```

ถ้าติดตั้งสำเร็จ บนเซิร์ฟเวอร์ต้องขึ้นว่าเรียก `/health` ได้ จากนั้นเปิดจากคอม:

- http://192.168.10.65:8090/
- http://192.168.10.65/  (ถ้าพอร์ต 80 ว่าง)

อย่าไป `git checkout` ทับโฟลเดอร์ระบบลงเวลาหรือ Tomcat ที่มีอยู่แล้ว

หลังขึ้นเว็บแล้ว ให้เข้าเมนู **นำเข้า AC25** เพื่อดึงข้อมูลจากไฟล์โปรแกรมบัญชีวัดเดิม

## ถ้ายังเข้าไม่ได้

รันบนเซิร์ฟเวอร์แล้วส่งผลมา:

```bash
cd ~/chatriacc
./scripts/diagnose_server.sh
```

ตรวจเร็วๆ:

```bash
systemctl status chatriacc
curl -v http://127.0.0.1:8090/health
sudo ufw allow 8090/tcp
sudo ufw allow 80/tcp
sudo ufw reload
```

- `curl` บนเซิร์ฟเวอร์ไม่ได้ = บริการยังไม่ขึ้น ดู `journalctl -u chatriacc -n 80`
- `curl` บนเซิร์ฟเวอร์ได้ แต่คอมเข้าไม่ได้ = ไฟร์วอลล์บล็อกพอร์ต 8090

## อัปเดตภายหลัง

```bash
cd ~/chatriacc
git pull origin cursor/chatriacc-web-ebbb
sudo ./scripts/install_on_server.sh
```

## พอร์ตที่แนะนำบนเครื่องนี้

| ระบบ | URL |
|---|---|
| chatriACC บัญชีวัด | http://192.168.10.65:8090/ |
