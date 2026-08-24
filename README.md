# ESP32 Keypad → ESP32-S3 LED P4 64×32

ระบบ 2 บอร์ด: พิมพ์ได้สูงสุด 6 ตัวอักษรจากคีย์แพด 3×4 แสดงบน LCD 16×2 แล้วส่งไปแสดงบนจอ LED P4 64×32

- `*` = ช่องว่าง (space)
- `#` = เคลียร์หน้าจอทั้ง LCD และ LED
- เชื่อมต่อบอร์ดต่อบอร์ดด้วย **ESP-NOW ผ่าน WiFi MAC** ไม่ต้องใช้เราเตอร์และไม่ต้องมี Access Point

```
[Keypad 3x4] + [LCD 16x2 I2C]
        ESP32 (บอร์ด 1)
              |  ESP-NOW  (ส่งไปที่ MAC ของบอร์ด 2)
              v
        ESP32-S3 (บอร์ด 2)
              |
        LED P4 64x32 HUB75
```

## จับคู่ด้วย MAC

1. อัปโหลดบอร์ด 2 (`esp32s3-led-p4`) ก่อน
2. เปิด Serial Monitor 115200 หรือดูจอ LED ตอนบูต จะขึ้น WiFi MAC เช่น `24:6F:28:AA:BB:CC`
3. ใส่ MAC นั้นใน `esp32-keypad-lcd/protocol.h`

```c
#define LED_BOARD_MAC 0x24, 0x6F, 0x28, 0xAA, 0xBB, 0xCC
```

4. อัปโหลดบอร์ด 1 (`esp32-keypad-lcd`)

ถ้ายังไม่ใส่ MAC จริง ค่าเริ่มต้น `FF:FF:FF:FF:FF:FF` คือ broadcast ส่งถึงทุกบอร์ด ESP-NOW ที่ช่องเดียวกัน (ช่อง `1`)

ทั้งสองบอร์ดต้องใช้ `ESPNOW_WIFI_CHANNEL` ค่าเดียวกันใน `protocol.h`

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

ตอนบูต LCD จะโชว์ MAC ของตัวเอง แล้วโชว์ MAC ปลายทางที่ตั้งใน `LED_BOARD_MAC`

### การใช้งานคีย์แพด

- กด 0–9 เพื่อพิมพ์ จำกัด 6 ตัว
- กด `*` เพื่อใส่ช่องว่าง
- กด `#` เพื่อล้าง LCD + ส่งคำสั่งเคลียร์ไปจอ LED
- ทุกครั้งที่พิมพ์ บอร์ดจะส่ง ESP-NOW ไปจอ LED ทันที
- พิมพ์ผ่าน Serial Monitor ได้เช่นกัน (115200 baud)

บรรทัดบนของ LCD: `>1234__`

## บอร์ด 2 — ESP32-S3 + LED P4 64×32

จอ P4 64×32 ใช้หัว **HUB75** ไม่ใช่สาย WS2812

### ไฟเลี้ยง (สำคัญ)

- แผง P4 64×32 กินไฟสูง ใช้ **5V 3A ขึ้นไป** เข้าหัวไฟของแผงโดยตรง
- ต่อ **GND ของเพาเวอร์ซัพพลายร่วมกับ GND ของ ESP32-S3**
- อย่าจ่ายไฟแผงจากขา 5V ของ DevKit

### สาย HUB75 → ESP32-S3

ค่าเริ่มต้นใน `esp32s3-led-p4/config.h`

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

## โปรโตคอล ESP-NOW

```
SET:123456
CLR
```

ข้อความเปล่าหรือ `CLR` = เคลียร์จอ

## ลำดับเปิดเครื่องที่แนะนำ

1. จ่ายไฟแผง LED 5V แล้วค่อยเสียบ USB / ไฟ ESP32-S3
2. จอจะขึ้น WiFi MAC ประมาณ 8 วินาที
3. เปิด ESP32 บอร์ดคีย์แพด
4. LCD บรรทัดล่างควรเป็น `ESP-NOW ready`
5. พิมพ์ตัวเลข ดู LCD และจอ P4 พร้อมกัน
6. กด `#` ทั้งสองจอต้องว่าง

## แก้ปัญหาเบื้องต้น

| อาการ | สิ่งที่ตรวจ |
| --- | --- |
| LCD ดำ / มีกล่อง | ปรับคอนทราสต์บน backpack, ตรวจ SDA/SCL, ดู Serial ว่าเจอที่อยู่ I2C หรือไม่ |
| คีย์ไม่ขึ้น | สลับแถว/คอลัมน์ตามสายจริงของคีย์แพด, ตรวจ GPIO |
| อัปโหลด ESP32 ไม่ติด | ถอดคีย์แพดออกจาก GPIO 12 / กด BOOT |
| จอไม่ขึ้นตามคีย์ | ใส่ MAC ของบอร์ด 2 ใน `LED_BOARD_MAC`, ช่อง WiFi ต้องตรงกัน (`ESPNOW_WIFI_CHANNEL`) |
| ESP-NOW fail | เปิดบอร์ด 2 ก่อน, วางใกล้กัน, ตรวจ Serial ทั้งสองฝั่ง |
| จอ LED ไม่ติด | ไฟ 5V ของแผง, GND ร่วม, สาย OE/CLK/LAT, ลดความสว่าง |
| จอ LED สีผิด / เส้นแตก | ลอง `PANEL_FM6126A 1`, ตรวจ R1/G1/B1 สลับกันหรือไม่ |

## โครงสร้างไฟล์

```
esp32-keypad-lcd/      สเก็ตช์บอร์ด 1 (ส่ง ESP-NOW ตาม MAC)
esp32s3-led-p4/        สเก็ตช์บอร์ด 2 (รับ ESP-NOW)
shared/protocol.h      MAC + ช่อง WiFi (สำเนาอยู่ในแต่ละสเก็ตช์)
```
