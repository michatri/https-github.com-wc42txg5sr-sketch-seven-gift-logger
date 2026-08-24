# ESP32 Keypad → ESP32-S3 LED P4 64×32

ระบบ 2 บอร์ด: พิมพ์ได้สูงสุด 6 ตัวอักษรจากคีย์แพด 3×4 แสดงบน LCD 16×2 แล้วส่งไปแสดงบนจอ LED P4 64×32

- `*` = ช่องว่าง (space)
- `#` = เคลียร์หน้าจอทั้ง LCD และ LED
- ช่องทางหลักระหว่างบอร์ด: **WiFi UDP** (ESP32-S3 เป็น Access Point)
- ช่องทางเสริม: **Bluetooth LE** (ESP32-S3 ชื่อ `ESP32S3-LED`) เพราะ ESP32-S3 ไม่มี Bluetooth Classic

```
[Keypad 3x4] + [LCD 16x2 I2C]
        ESP32 (บอร์ด 1)
              |  WiFi UDP  และ  BLE
              v
        ESP32-S3 (บอร์ด 2)
              |
        LED P4 64x32 HUB75
```

อัปโหลดบอร์ด 2 ก่อน แล้วค่อยบอร์ด 1 เพื่อให้มี WiFi AP / BLE ให้ต่อ

## สิ่งที่ต้องใช้

| ชิ้น | จำนวน | หมายเหตุ |
| --- | --- | --- |
| ESP32 DevKit (WROOM-32) | 1 | บอร์ดคีย์แพด |
| ESP32-S3 DevKitC-1 | 1 | บอร์ดจอ LED |
| Keypad matrix 3×4 | 1 | 7 ขา |
| LCD 16×2 + I2C backpack (PCF8574) | 1 | ที่อยู่ I2C มักเป็น `0x27` หรือ `0x3F` |
| LED matrix P4 64×32 HUB75 | 1 | ต้องใช้ไฟ 5V ภายนอก อย่างน้อย 3A |
| สายจั๊มเปอร์, ไฟ 5V, กราวน์ร่วม | | อย่าป้อนไฟแผง LED จากขา 5V ของบอร์ด |

## ไลบรารี Arduino IDE

ติดตั้ง **Arduino-ESP32** โดย Espressif แล้วติดตั้งไลบรารีเหล่านี้จาก Library Manager:

บอร์ด 1

- `Keypad` โดย Mark Stanley, Alexander Brevig
- `LiquidCrystal I2C` โดย Frank de Brabander หรือ Marcos Schwartz

บอร์ด 2

- `Adafruit GFX Library`
- `Adafruit BusIO`
- `ESP32 HUB75 LED MATRIX PANEL DMA Display` โดย mrfaptastic  
  (หรือ Clone จาก https://github.com/mrfaptastic/ESP32-HUB75-MatrixPanel-I2S-DMA )

ตั้งค่าตอนอัปโหลด

- บอร์ด 1: `ESP32 Dev Module`, upload speed 115200
- บอร์ด 2: `ESP32S3 Dev Module`, **USB CDC On Boot = Enabled**, PSRAM ตามโมดูลที่ใช้

เปิดสเก็ตช์

- `esp32-keypad-lcd/esp32-keypad-lcd.ino`
- `esp32s3-led-p4/esp32s3-led-p4.ino`

หรือใช้ PlatformIO ในโฟลเดอร์ของแต่ละบอร์ด

## บอร์ด 1 — ESP32 คีย์แพด + LCD

### คีย์แพด 3×4

```
byte rowPins[ROWS] = {4, 12, 14, 5};
byte colPins[COLS] = {26, 25, 33};
```

| Keypad | ESP32 GPIO |
| --- | --- |
| R1 | 4 |
| R2 | 12 |
| R3 | 14 |
| R4 | 5 |
| C1 | 26 |
| C2 | 25 |
| C3 | 33 |

แป้น

```
1  2  3
4  5  6
7  8  9
*  0  #
```

GPIO 12 เป็นขา strapping ของ ESP32 หากอัปโหลดไม่ติด ให้ถอดคีย์แพดออกก่อนแฟลช

### LCD 16×2 I2C

| LCD I2C | ESP32 |
| --- | --- |
| VCC | 5V (หรือ 3.3V ตามโมดูล) |
| GND | GND |
| SDA | 21 |
| SCL | 22 |

สเก็ตช์จะสแกนหาที่อยู่ I2C ให้เอง (`0x27`, `0x3F`, แล้วช่วง `0x20–0x3F`)

### การใช้งานคีย์แพด

- กด 0–9 เพื่อพิมพ์ จำกัด 6 ตัว
- กด `*` เพื่อใส่ช่องว่าง
- กด `#` เพื่อล้าง LCD + ส่งคำสั่งเคลียร์ไปจอ LED
- ทุกครั้งที่พิมพ์ บอร์ดจะส่งข้อความไปจอ LED ทันที
- พิมพ์ผ่าน Serial Monitor ได้เช่นกัน (115200 baud)

บรรทัดบนของ LCD: `>1234__`  
บรรทัดล่าง: สถานะ WiFi / BLE

## บอร์ด 2 — ESP32-S3 + LED P4 64×32

จอ P4 64×32 ใช้หัว **HUB75** ไม่ใช่สาย WS2812

### ไฟเลี้ยง (สำคัญ)

- แผง P4 64×32 กินไฟสูง ใช้ **5V 3A ขึ้นไป** เข้าหัวไฟของแผงโดยตรง
- ต่อ **GND ของเพาเวอร์ซัพพลายร่วมกับ GND ของ ESP32-S3**
- อย่าจ่ายไฟแผงจากขา 5V ของ DevKit

### สาย HUB75 → ESP32-S3

ค่าเริ่มต้นใน `esp32s3-led-p4/config.h` หลีกเลี่ยงขา USB (19, 20) UART0 (43, 44) และขา octal PSRAM (35–37)

| HUB75 | สัญญาณ | ESP32-S3 GPIO |
| --- | --- | --- |
| R1 | Red 1 | 4 |
| G1 | Green 1 | 5 |
| B1 | Blue 1 | 6 |
| R2 | Red 2 | 7 |
| G2 | Green 2 | 15 |
| B2 | Blue 2 | 16 |
| A | Row A | 18 |
| B | Row B | 8 |
| C | Row C | 9 |
| D | Row D | 10 |
| E | Row E (แผง 32 แถวไม่ใช้) | ไม่ต่อ |
| LAT / STB | Latch | 11 |
| OE | Output Enable | 12 |
| CLK | Clock | 13 |
| GND | Ground | GND |

หัว IDC 16 พินโดยทั่วไป:

```
 1 R1    2 G1
 3 B1    4 GND
 5 R2    6 G2
 7 B2    8 GND
 9 A    10 B
11 C    12 D
13 CLK  14 LAT
15 OE   16 GND
```

ถ้าสีเพี้ยน / ภาพเบลอ / แถวเลื่อน ให้ลองใน `config.h`

- `#define PANEL_FM6126A 1`
- ลด `PANEL_BRIGHTNESS` เช่น 40
- สลับ `mxconfig.clkphase` ในสเก็ตช์ถ้าภาพแตกเป็นเงา

## การเชื่อมต่อไร้สาย

บอร์ด 2 เปิด WiFi AP

| รายการ | ค่า |
| --- | --- |
| SSID | `ESP32-LED-P4` |
| รหัสผ่าน | `12345678` |
| IP บอร์ดจอ | `192.168.4.1` |
| UDP port | `4210` |
| หน้าเว็บ | http://192.168.4.1/ |
| BLE ชื่อ | `ESP32S3-LED` |

แก้ SSID / รหัสผ่านใน `protocol.h` ของ **ทั้งสองโฟลเดอร์ให้ตรงกัน**

โปรโตคอลข้อความ (UDP และ BLE):

```
SET:123456
CLR
```

ข้อความเปล่าหรือ `CLR` = เคลียร์จอ  
ส่งตัวอักษร 1–6 ตัวโดยไม่มี `SET:` ก็ได้

มือถือต่อ WiFi `ESP32-LED-P4` แล้วเปิดเบราว์เซอร์ที่ `http://192.168.4.1/` เพื่อพิมพ์ทดสอบโดยไม่ใช้คีย์แพด

แอป BLE เช่น nRF Connect / Serial Bluetooth Terminal (โหมด BLE) เขียนไปที่ Nordic UART RX ก็แสดงบนจอได้เช่นกัน

## ลำดับเปิดเครื่องที่แนะนำ

1. จ่ายไฟแผง LED 5V แล้วค่อยเสียบ USB / ไฟ ESP32-S3
2. รอจนจอขึ้น `P4 64x32` และเคอร์เซอร์กระพริบ
3. เปิด ESP32 บอร์ดคีย์แพด
4. LCD บรรทัดล่างควรเป็น `WiFi OK` หรือ `BLE+WiFi ready`
5. พิมพ์ตัวเลข ดู LCD และจอ P4 พร้อมกัน
6. กด `#` ทั้งสองจอต้องว่าง

## แก้ปัญหาเบื้องต้น

| อาการ | สิ่งที่ตรวจ |
| --- | --- |
| LCD ดำ / มีกล่อง | ปรับคอนทราสต์บน backpack, ตรวจ SDA/SCL, ดู Serial ว่าเจอที่อยู่ I2C หรือไม่ |
| คีย์ไม่ขึ้น | สลับแถว/คอลัมน์ตามสายจริงของคีย์แพด, ตรวจ GPIO |
| อัปโหลด ESP32 ไม่ติด | ถอดคีย์แพดออกจาก GPIO 12 / กด BOOT |
| บอร์ด 1 ไม่มี WiFi | เปิดบอร์ด 2 ก่อน, ยืนยัน SSID `ESP32-LED-P4` |
| จอ LED ไม่ติด | ไฟ 5V ของแผง, GND ร่วม, สาย OE/CLK/LAT, ลดความสว่าง |
| จอ LED สีผิด / เส้นแตก | ลอง `PANEL_FM6126A 1`, ตรวจ R1/G1/B1 สลับกันหรือไม่ |
| BLE ต่อไม่ติด | ใช้ WiFi เป็นช่องหลักได้เลย (ESP32 ใช้ WiFi+BLE พร้อมกันอาจช้า) |

## โครงสร้างไฟล์

```
esp32-keypad-lcd/      สเก็ตช์บอร์ด 1
esp32s3-led-p4/        สเก็ตช์บอร์ด 2
shared/protocol.h      ค่า WiFi/BLE ต้นฉบับ (สำเนาอยู่ในแต่ละสเก็ตช์)
```
