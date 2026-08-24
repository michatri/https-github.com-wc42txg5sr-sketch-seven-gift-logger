# ESP32 + LCD 16×2 + Keypad 3×4 ผ่าน I2C

สเก็ตช์ตามโค้ดที่ส่งมา: จอ LCD I2C ที่ `0x27` และคีย์แพด 3×4 ผ่าน PCF8574 ที่ `0x20` บนบัสเดียวกัน

ไฟล์อัปโหลด: [`esp32_lcd_keypad_i2c/esp32_lcd_keypad_i2c.ino`](esp32_lcd_keypad_i2c/esp32_lcd_keypad_i2c.ino)

## ไลบรารี

ติดตั้งจาก Arduino Library Manager:

| ไลบรารี | ใช้ทำอะไร |
|---|---|
| **LiquidCrystal I2C** (Frank de Brabander) | ขับจอ 16×2 |
| **Keypad** (Mark Stanley, Alexander Brevig) | สแกนเมทริกซ์ + debounce |

`Keypad_I2C` ของ Joe Young **อยู่ในโฟลเดอร์สเก็ตช์แล้ว** ไม่ต้องติดตั้งเพิ่ม

จุดสำคัญ: ต้องมี `#include <Keypad.h>` ก่อน `Keypad_I2C.h` ไม่งั้นจะ error `makeKeymap was not declared` / `Keypad does not name a type`

```cpp
#include <Wire.h>
#include <LiquidCrystal_I2C.h>
#include <Keypad.h>      // ต้องมีบรรทัดนี้
#include <Keypad_I2C.h>
```

## Address และพิน I2C

| อุปกรณ์ | Address | หมายเหตุ |
|---|---|---|
| LCD backpack (PCF8574) | `0x27` | ถ้าไม่ติดลอง `0x3F` |
| Keypad (PCF8574) | `0x20` | A0=A1=A2 ต่อ GND |
| SDA | GPIO 21 | |
| SCL | GPIO 22 | |

จ่าย PCF8574 คีย์แพดที่ **3.3V** — GPIO ESP32 ไม่ทน 5V ต้องมี GND ร่วมกันทั้งบอร์ด

### แมปคีย์แพดเข้า PCF8574

```
P0 P1 P2 P3  = แถว 1 2 3 4     →  123 / 456 / 789 / *0#
P4 P5 P6     = คอลัมน์ 1 2 3   →  147* / 2580 / 369#
P7           ไม่ใช้
```

## พฤติกรรม

- ตอนบูตพิมพ์ `ESP32 Keypad Test` ที่บรรทัดบนจอ
- กดปุ่มแล้วแสดง `Key Pressed: X` ที่บรรทัดล่าง และพิมพ์ `Pressed: X` ใน Serial (115200)
- `getKey()` คืนค่าครั้งเดียวตอนกดลง (มี debounce ในไลบรารี)

`lcd.init()` ของบางเวอร์ชันเรียก `Wire.begin()` เองโดยไม่ระบุพิน สเก็ตช์จึงล็อกกลับไป GPIO 21/22 หลัง init

## อัปโหลด

Arduino IDE: เลือกบอร์ด ESP32 Dev Module แล้วเปิดโฟลเดอร์ `esp32_lcd_keypad_i2c/`

หรือ PlatformIO:

```bash
pio run -t upload
pio device monitor
```
