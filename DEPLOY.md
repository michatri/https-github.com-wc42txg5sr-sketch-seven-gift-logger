# ติดตั้งบน Ubuntu server 192.168.10.56

เป้าหมายคือเครื่อง **cameraserver** ที่ IP `192.168.10.56`  
ระบบบัญชีจะเปิดที่พอร์ต **8090** เพื่อไม่ชนกับของที่มีอยู่แล้ว:

| ระบบ | URL |
|---|---|
| บัญชีรายรับ-รายจ่าย (ใหม่) | http://192.168.10.56:8090/ |
| ลงเวลาด้วยใบหน้า | http://192.168.10.56:8080/ |
| Jakarta Tomcat | http://192.168.10.56:8888/ |

รันคำสั่งด้านล่างบนเซิร์ฟเวอร์ในฐานะ `root` (เช่น `root@cameraserver`)  
อย่าไป `git checkout` ทับโฟลเดอร์ระบบลงเวลาเดิมที่ `/root/https-github.com-wc42txg5sr-sketch-seven-gift-logger`

## ติดตั้งครั้งแรก

```bash
cd /root
git clone -b cursor/accounting-payslip-cd50 \
  https://github.com/michatri/https-github.com-wc42txg5sr-sketch-seven-gift-logger.git accounting
cd /root/accounting
chmod +x scripts/install_on_server.sh
./scripts/install_on_server.sh
```

จากเครื่องอื่นใน LAN เปิด:

```text
http://192.168.10.56:8090/
```

systemd จะเปิดเว็บให้อัตโนมัติตอนบูต ไม่ต้องรันเองทุกครั้ง

## อัปเดตภายหลัง

```bash
cd /root/accounting
git pull origin cursor/accounting-payslip-cd50
./scripts/install_on_server.sh
```

## คำสั่งใช้ประจำ

```bash
systemctl status accounting
systemctl restart accounting
journalctl -u accounting -f
```

ฐานข้อมูล SQLite อยู่ที่ `/root/accounting/data/accounting.db`
