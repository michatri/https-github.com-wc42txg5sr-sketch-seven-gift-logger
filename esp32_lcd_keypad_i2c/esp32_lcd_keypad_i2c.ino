/*
 * ESP32 + LCD 16x2 (I2C) + Keypad 3x4 (PCF8574)
 *
 * ไลบรารีที่ต้องติดตั้งจาก Arduino Library Manager:
 *   - LiquidCrystal I2C  (Frank de Brabander)
 *   - Keypad             (Mark Stanley, Alexander Brevig)
 *
 * Keypad_I2C.h / Keypad_I2C.cpp อยู่ในโฟลเดอร์นี้แล้ว
 * (Joe Young, https://github.com/joeyoung/arduino_keypads)
 *
 * บัส I2C ร่วมกัน:
 *   SDA = GPIO 21
 *   SCL = GPIO 22
 *
 * Address:
 *   LCD backpack  = 0x27  (ถ้าไม่ติดลอง 0x3F)
 *   Keypad PCF8574 = 0x20  (A0=A1=A2 = GND)
 */

#include <Wire.h>
#include <Keypad.h>
#include <LiquidCrystal_I2C.h>
#include "Keypad_I2C.h"

// 1. ตั้งค่า LCD 16x2
LiquidCrystal_I2C lcd(0x27, 16, 2);  // Address 0x27 (หากไม่ติดให้ลอง 0x3F)

// 2. ตั้งค่า Keypad 3x4
const byte ROWS = 4;
const byte COLS = 3;

// ตารางปุ่มกด 3x4 ที่ถูกต้อง
char keys[ROWS][COLS] = {
    {'1', '2', '3'},
    {'4', '5', '6'},
    {'7', '8', '9'},
    {'*', '0', '#'}};

// แมปพิน Row และ Col เข้ากับพิน P0-P6 ของ PCF8574
// Row 1-4  -> P0, P1, P2, P3
// Col 1-3  -> P4, P5, P6
byte rowPins[ROWS] = {0, 1, 2, 3};
byte colPins[COLS] = {4, 5, 6};

// Address ของ PCF8574 ที่ต่อกับ Keypad (กำหนดให้เป็น 0x20 เพื่อไม่ให้ชนกับ LCD)
#define KEYPAD_I2C_ADDR 0x20

Keypad_I2C customKeypad(makeKeymap(keys), rowPins, colPins, ROWS, COLS,
                        KEYPAD_I2C_ADDR, PCF8574);

static bool i2cPresent(uint8_t addr) {
  Wire.beginTransmission(addr);
  return Wire.endTransmission() == 0;
}

static void scanI2C() {
  Serial.println("I2C scan:");
  uint8_t found = 0;
  for (uint8_t addr = 1; addr < 127; addr++) {
    if (i2cPresent(addr)) {
      Serial.print("  found 0x");
      if (addr < 16) {
        Serial.print('0');
      }
      Serial.println(addr, HEX);
      found++;
    }
  }
  if (found == 0) {
    Serial.println("  (none)  ตรวจ SDA/SCL, GND ร่วม, และไฟเลี้ยง");
  }
}

void setup() {
  Serial.begin(115200);
  delay(200);

  // ESP32 I2C Pins (SDA=21, SCL=22)
  Wire.begin(21, 22);
  Wire.setClock(100000);
  scanI2C();

  if (!i2cPresent(0x27) && i2cPresent(0x3F)) {
    Serial.println("LCD ไม่ตอบที่ 0x27 แต่เจอ 0x3F — แก้ constructor เป็น LiquidCrystal_I2C lcd(0x3F, 16, 2);");
  }
  if (!i2cPresent(KEYPAD_I2C_ADDR)) {
    Serial.println("ไม่พบ keypad ที่ 0x20 — ตรวจจัมเปอร์ A0-A2 หรือชิป PCF8574A (0x38)");
  }

  // เริ่มต้นทำงาน LCD
  lcd.init();
  // lcd.init() ของบางเวอร์ชันเรียก Wire.begin() แบบไม่ระบุพิน — ล็อกกลับไป GPIO 21/22
  Wire.begin(21, 22);

  lcd.backlight();
  lcd.setCursor(0, 0);
  lcd.print("ESP32 Keypad I2C");
  lcd.setCursor(0, 1);
  lcd.print("Ready...");

  // เริ่มต้นทำงาน Keypad (ต้องเรียกหลัง Wire.begin)
  customKeypad.begin();
}

void loop() {
  char key = customKeypad.getKey();

  if (key) {
    Serial.print("Pressed: ");
    Serial.println(key);

    // แสดงผลบนหน้าจอ LCD (16 ตัวอักษร: "Key Pressed: X ")
    lcd.setCursor(0, 1);
    lcd.print("Key Pressed: ");
    lcd.print(key);
    lcd.print(' ');  // ลบตัวอักษรตกค้าง
  }
}
