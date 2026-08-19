# ติดตั้ง chatriACC บน cameraserver

`192.168.10.65` ที่เคยพิมพ์มัก timeout เพราะเครื่องที่เปิดเว็บได้จริงคือ **192.168.10.56** (cameraserver — ระบบลงเวลาที่ `:8080` และบัญชีสลิปที่ `:8090` อยู่ที่นี่)

chatriACC ใช้พอร์ต **8100** และต้องเป็น **http** ไม่ใช่ https

เปิดแบบนี้:

- http://192.168.10.56:8100/

Cloud agent SSH เข้าเครื่องนี้ไม่ได้ ต้องรันคำสั่งด้านล่างบนเครื่องใน LAN เอง

บัญชีที่ใช้: **aaa**

## ติดตั้ง (คัดลอกทั้งก้อน รันบนเซิร์ฟเวอร์)

จากคอมใน LAN:

```bash
ssh aaa@192.168.10.56
```

**อย่าใช้ `sudo git clone` และอย่าทำงานใน `/root`** เพราะ user `aaa` เข้า `/root` ไม่ได้ จะขึ้น `Permission denied` ที่ `.venv/bin/python`

แล้ววางคำสั่งนี้:

```bash
sudo apt-get update
sudo apt-get install -y git python3 python3-venv python3-pip curl
cd ~
git clone -b cursor/chatriacc-web-ebbb \
  https://github.com/michatri/https-github.com-wc42txg5sr-sketch-seven-gift-logger.git chatriacc
cd ~/chatriacc
git pull origin cursor/chatriacc-web-ebbb || true
chmod +x scripts/*.sh
sudo ./scripts/install_on_server.sh
```

ถ้า clone ไว้ที่ `/root/chatriacc` แล้ว ให้รันชุดนี้แทน (สคริปต์จะย้ายไป `/home/aaa/chatriacc`):

```bash
sudo git -C /root/chatriacc pull origin cursor/chatriacc-web-ebbb
sudo chmod +x /root/chatriacc/scripts/*.sh
sudo /root/chatriacc/scripts/install_on_server.sh
```

ถ้าติดตั้งสำเร็จ บนเซิร์ฟเวอร์ต้องขึ้นว่าเรียก `/health` ได้ และจะพิมพ์ **IP จริง** จาก `hostname -I` จากนั้นเปิดจากคอมใน LAN:

- http://192.168.10.56:8100/
- http://192.168.10.56:8110/  (ถ้าพอร์ต 8100 ถูกบริการอื่นใช้แล้ว)

ห้ามใช้ `https://` — ระบบยังไม่มีใบรับรอง SSL จะค้างจนหมดเวลา

รัน `hostname -I` บนเซิร์ฟเวอร์ เปิด URL ตามเลขที่ขึ้น ไม่ใช่เลขที่จำไว้

อย่าไป `git checkout` ทับโฟลเดอร์ระบบลงเวลาหรือ Tomcat ที่มีอยู่แล้ว
อย่า `cp` ไฟล์ `chatriacc.service` เข้า `/etc/systemd` เอง ให้ใช้สคริปต์ติดตั้ง เพราะมันจะใส่ path จริงของโฟลเดอร์บนเครื่อง

หลังขึ้นเว็บแล้ว ให้เข้าเมนู **นำเข้า AC25** เพื่อดึงข้อมูลจากไฟล์โปรแกรมบัญชีวัดเดิม

## ถ้ายังเข้าไม่ได้

รันบนเซิร์ฟเวอร์แล้วส่งผลมา:

```bash
cd ~/chatriacc
./scripts/diagnose_server.sh
```

ตรวจเร็วๆ:

```bash
hostname -I
systemctl status chatriacc
journalctl -u chatriacc -n 80 --no-pager
curl -v http://127.0.0.1:8100/health
sudo ./scripts/open_lan_ports.sh
```

ข้อความ `Failed with result 'exit-code'` แปลว่าโปรเซส gunicorn ดับทันที สาเหตุที่พบบ่อย:

- คัดลอก `chatriacc.service` ไป `/etc/systemd/system/` เอง ทำให้ชี้ `/root/chatriacc` ทั้งที่โค้ดอยู่ที่ `/home/aaa/chatriacc`
- clone ด้วย root จนได้ `/root/chatriacc` แล้วรันบริการด้วย user `aaa` → `Permission denied` ที่ `.venv/bin/python` (aaa เข้า `/root` ไม่ได้) ชุดนี้จะย้ายไป `/home/aaa/chatriacc` ให้
- ติดตั้งบนเครื่องผิด IP (เปิด `.65` ทั้งที่บริการอยู่ที่ `.56`)
- พอร์ต 8100 ถูกบริการอื่นใช้แล้ว — สคริปต์จะย้ายไป 8110 หรือ 8120 ให้เอง

แก้โดย `git pull` แล้วรัน `sudo ./scripts/install_on_server.sh` อีกครั้ง อย่าคัดลอกไฟล์ `.service` เอง

- `curl` บนเซิร์ฟเวอร์ไม่ได้ = บริการยังไม่ขึ้น ดู `journalctl -u chatriacc -n 80`
- `curl` บนเซิร์ฟเวอร์ได้ แต่คอมเข้าไม่ได้ = ไฟร์วอลล์บล็อกพอร์ต 8100 หรือเปิด URL คนละ IP

## อัปเดตภายหลัง

```bash
cd ~/chatriacc
git pull origin cursor/chatriacc-web-ebbb
chmod +x scripts/*.sh
sudo ./scripts/install_on_server.sh
sudo ./scripts/open_lan_ports.sh
```

## พอร์ตบน cameraserver (192.168.10.56)

| ระบบ | URL |
|---|---|
| chatriACC บัญชีวัด | http://192.168.10.56:8100/ |
| accounting.service บัญชีสลิป | http://192.168.10.56:8090/ |
| ลงเวลาด้วยใบหน้า | http://192.168.10.56:8080/ |
| Jakarta Tomcat | http://192.168.10.56:8888/ |
