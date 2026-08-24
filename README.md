# ESP32 Page Transmitter (I2C LCD + PCF8574 keypad)

Transmitter สำหรับส่งเลขหน้าไปจอ LED ผ่าน ESP-NOW  
ESP32 ต่อ **LCD 16x2** และ **คีย์แพด 3x4** บนบัส I2C เดียวกัน (SDA=21, SCL=22)

- LCD ใช้ backpack PCF8574 ที่อยู่ `0x27`
- คีย์แพด 3x4 ต่อผ่าน PCF8574 ตัวเดียวที่อยู่ `0x20` (ไลบรารี `I2CKeyPad`)

## ไลบรารีที่ต้องติดตั้ง

ใน Arduino IDE:

- [LiquidCrystal I2C](https://github.com/johnrickman/LiquidCrystal_I2C)
- [I2CKeyPad](https://github.com/RobTillaart/I2CKeyPad) โดย Rob Tillaart

ESP32 Arduino Core รองรับทั้ง v2.x และ v3.x (callback ESP-NOW คนละลายเซ็น)

## การต่อสาย

| ESP32 | อุปกรณ์ |
| --- | --- |
| GPIO 21 | SDA (LCD + PCF8574 keypad) |
| GPIO 22 | SCL (LCD + PCF8574 keypad) |
| 3V3 / 5V | VCC ของโมดูล I2C |
| GND | GND |

คีย์แพด 3x4 ต่อเข้า PCF8574 ตามโหมด 4x4 ของ `I2CKeyPad` (คอลัมน์ที่ 4 ไม่ใช้ จึงแมปเป็น `N`):

```
P0–P3 = แถว, P4–P7 = คอลัมน์
keymap = "123N456N789N*0#NNN"
```

ถ้าสแกน I2C แล้วที่อยู่ไม่ใช่ `0x27` / `0x20` ให้แก้ในสเก็ตช์

## ปุ่ม

| ปุ่ม | การทำงาน |
| --- | --- |
| `0`–`9` | ต่อเลข (สูงสุด 5 ตัว) แล้วส่งไปทุกจอทันที |
| `*` | ใส่ช่องว่าง แล้วส่ง |
| `#` | ส่งคำสั่ง `CLEAR` ให้จอ LED ทุกจอดับ |

## จอรับ (ESP-NOW)

แก้ MAC ใน `esp32_transmitter.ino` ให้ตรงกับจอจริง แล้ว uncomment `display3` เมื่อต่อจอที่ 3

ช่องวิทยุล็อกที่ **channel 1** ให้ตรงกับตัวรับ
