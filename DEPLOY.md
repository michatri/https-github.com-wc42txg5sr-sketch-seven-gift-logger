# ติดตั้ง chatriACC บน cameraserver หรือ VPS

chatriACC ใช้พอร์ต **8100** (สำรอง 8110 / 8120) และรันด้วย gunicorn ฟังที่ `0.0.0.0` จึงย้ายขึ้น VPS ที่มี IP จริงได้โดยติดตั้งชุดเดิม

- ใน LAN เครื่องที่เปิดเว็บได้จริงคือ **192.168.10.56** ไม่ใช่ `.65`
- บน VPS ให้เปิดตาม **IP สาธารณะ** ที่แผงควบคุมคลาวด์แสดง

## ย้ายขึ้น VPS ที่เป็น IP จริง

โปรแกรมไม่ผูกกับ 192.168.x.x ในตัวรัน ย้ายได้ 3 ขั้น: ติดตั้งบน VPS → คัดลอกฐานข้อมูล (ถ้ามีของเดิม) → เปิดพอร์ตที่ไฟร์วอลล์คลาวด์

ระบบนี้**ยังไม่มีหน้า login** ถ้าเปิด IP จริงทั้งโลกจะเข้าดู/แก้บัญชีวัดได้ ควรจำกัด IP ที่ไฟร์วอลล์ หรือใช้ VPN จนกว่าจะใส่รหัสผ่าน

### 1) สร้างเครื่อง VPS

ใช้ Ubuntu 22.04/24.04 แล้วดู **Public IP** จากแผง (เช่น 203.0.113.10) SSH:

```bash
ssh root@IP_จริง_ของ_VPS
```

สร้าง user ธรรมดา อย่าทำงานใน `/root`:

```bash
adduser aaa
usermod -aG sudo aaa
su - aaa
```

### 2) ติดตั้งบน VPS

```bash
sudo apt-get update
sudo apt-get install -y git python3 python3-venv python3-pip curl
cd ~
git clone -b cursor/chatriacc-web-ebbb \
  https://github.com/michatri/https-github.com-wc42txg5sr-sketch-seven-gift-logger.git chatriacc
cd ~/chatriacc
chmod +x scripts/*.sh
sudo CHATRIACC_PUBLIC=1 ./scripts/install_on_server.sh
```

`CHATRIACC_PUBLIC=1` ให้ไฟร์วอลล์ในเครื่องเปิดพอร์ต 8100 จากอินเทอร์เน็ต ไม่จำกัดแค่ 192.168.10.0/24

ตรวจบน VPS:

```bash
curl -fsS http://127.0.0.1:8100/health
```

ต้องได้ `{"ok": true, ...}`

### 3) เปิดพอร์ตที่แผงควบคุม VPS ด้วย

`ufw` ในเครื่องยังไม่พอ คลาวด์มักมีไฟร์วอลล์อีกชั้น (Security Group, Networking, Firewall)

เปิด **TCP 8100** เข้าเครื่องนี้ (และ 22 สำหรับ SSH)

จากคอมที่บ้านเปิด:

**http://IP_จริง:8100/**

ต้องมี `http://` และ `:8100` อย่าใช้ `https://` จนกว่าจะติดตั้งใบรับรอง

### 4) ย้ายข้อมูลจากเครื่อง LAN (ถ้าใช้มาแล้ว)

บน cameraserver:

```bash
sudo systemctl stop chatriacc
sudo tar -C /home/aaa/chatriacc -czf /tmp/chatriacc-data.tgz data/chatriacc.db data/chatriacc.db-wal data/chatriacc.db-shm data/years 2>/dev/null || \
sudo tar -C /home/aaa/chatriacc -czf /tmp/chatriacc-data.tgz data/chatriacc.db
```

จากคอม:

```bash
scp aaa@192.168.10.56:/tmp/chatriacc-data.tgz .
scp chatriacc-data.tgz aaa@IP_จริง:~/
```

บน VPS:

```bash
sudo systemctl stop chatriacc
cd /home/aaa/chatriacc
sudo tar -xzf ~/chatriacc-data.tgz
sudo chown -R aaa:aaa data
sudo systemctl start chatriacc
```

อย่าคัดลอกโฟลเดอร์ `.venv` จากเครื่องเก่า

### 5) (ไม่บังคับ) เปิดด้วยพอร์ต 80 หรือโดเมน + https

ถ้าต้องการ `http://IP_จริง/` โดยไม่ใส่ `:8100`:

```bash
sudo apt-get install -y nginx
sudo cp /home/aaa/chatriacc/chatriacc/deploy/nginx-chatriacc.conf /etc/nginx/sites-available/chatriacc
sudo ln -sf /etc/nginx/sites-available/chatriacc /etc/nginx/sites-enabled/chatriacc
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx
sudo ufw allow 80/tcp
```

เปิด TCP **80** ที่ไฟร์วอลล์คลาวด์ด้วย

ถ้ามีโดเมนชี้มาที่ IP นี้ แล้วต้องการ https:

```bash
sudo apt-get install -y certbot python3-certbot-nginx
sudo certbot --nginx -d ชื่อโดเมน.com
```

จากนั้นเปิด **https://ชื่อโดเมน.com/**

### เช็คเมื่อ VPS เข้าไม่ได้

| อาการ | สาเหตุที่พบบ่อย |
|---|---|
| `curl` บน VPS ได้ แต่คอม timeout | ยังไม่เปิดพอร์ตที่ **แผง VPS** |
| Connection refused | `systemctl status chatriacc` ยังไม่ขึ้น |
| Timeout ทั้งพอร์ต 80 และ 8100 | เปิด `https://` หรือ IP ผิด |
| หน้าเว็บว่าง ไม่มีใบสำคัญ | ยังไม่ได้คัดลอก `data/chatriacc.db` |

---

## ติดตั้งใน LAN (cameraserver 192.168.10.56)

`192.168.10.65` ที่เคยพิมพ์มัก timeout เพราะเครื่องที่เปิดเว็บได้จริงคือ **192.168.10.56**

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

สคริปต์ติดตั้งจะนำเข้า `chatriacc/seed/AC25-209.xlsb` เข้า `data/chatriacc.db` ให้อัตโนมัติถ้าฐานยังไม่มีใบสำคัญ

ถ้าฐานว่างอยู่แล้วหลังอัปเดตโค้ด ให้รัน:

```bash
cd /home/aaa/chatriacc
sudo -u aaa env PYTHONPATH=/home/aaa/chatriacc CHATRIACC_DB=/home/aaa/chatriacc/data/chatriacc.db \
  /home/aaa/chatriacc/.venv/bin/python -m chatriacc.importer
```

หรือใช้ `--force` ถ้าต้องการให้ไฟล์ทับใบสำคัญปีเดียวกันในฐาน

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
