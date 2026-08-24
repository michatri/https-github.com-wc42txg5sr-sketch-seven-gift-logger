/*
 * ESP32 + PCF8574 + Keypad 4x3 + LCD 16x2
 *
 * ต่อสาย (บัส I2C เส้นเดียว):
 *
 *   ESP32 GPIO21 (SDA) ──┬── LCD 16x2 I2C   (PCF8574 ใน backpack)  0x27
 *   ESP32 GPIO22 (SCL) ──┤
 *   ESP32 3.3V / GND  ───┤
 *                        └── PCF8574 คีย์แพด 4x3                   0x20
 *                              P0-P3 = แถว, P4-P6 = คอลัมน์
 *
 * จอ 16x2 แบบ I2C มีชิป PCF8574 ติดมาที่แผงด้านหลังอยู่แล้ว
 * คีย์แพดใช้ PCF8574 อีกตัว — รวม 2 ตัว ห้าม address ชนกัน
 *
 * Arduino Library Manager:
 *   - LiquidCrystal I2C  (Frank de Brabander)
 *   - Keypad             (Mark Stanley, Alexander Brevig)
 *
 * Keypad_I2C.h / Keypad_I2C.cpp อยู่ในโฟลเดอร์สเก็ตช์นี้แล้ว
 */

#include <Wire.h>
#include <LiquidCrystal_I2C.h>
#include <Keypad.h>      // ต้อง include ก่อน Keypad_I2C (makeKeymap + class Keypad)
#include <Keypad_I2C.h>

#define LCD_ADDR     0x27   // PCF8574 บนโมดูลจอ (ถ้าไม่ติดลอง 0x3F)
#define KEYPAD_ADDR  0x20   // PCF8574 ที่ต่อคีย์แพด 4x3 (A0=A1=A2 = GND)
#define I2C_SDA      21
#define I2C_SCL      22

LiquidCrystal_I2C lcd(LCD_ADDR, 16, 2);

const byte ROWS = 4;  // คีย์แพด 4 แถว
const byte COLS = 3;  // คีย์แพด 3 คอลัมน์

char keys[ROWS][COLS] = {
  {'1', '2', '3'},
  {'4', '5', '6'},
  {'7', '8', '9'},
  {'*', '0', '#'}
};

// PCF8574 ตัวที่ต่อคีย์แพด: แถว P0–P3, คอลัมน์ P4–P6
byte rowPins[ROWS] = {0, 1, 2, 3};
byte colPins[COLS] = {4, 5, 6};

Keypad_I2C customKeypad(makeKeymap(keys), rowPins, colPins, ROWS, COLS, KEYPAD_ADDR);

static bool i2cPresent(uint8_t addr) {
  Wire.beginTransmission(addr);
  return Wire.endTransmission() == 0;
}

static void scanI2C() {
  Serial.println("I2C scan (ต้องเจอ PCF8574 จอ 0x27 และ PCF8574 คีย์แพด 0x20):");
  uint8_t found = 0;
  for (uint8_t addr = 1; addr < 127; addr++) {
    if (i2cPresent(addr)) {
      Serial.print("  found 0x");
      if (addr < 16) {
        Serial.print('0');
      }
      Serial.print(addr, HEX);
      if (addr == LCD_ADDR) {
        Serial.print("  <- LCD 16x2");
      } else if (addr == KEYPAD_ADDR) {
        Serial.print("  <- Keypad 4x3");
      } else if (addr == 0x3F) {
        Serial.print("  <- LCD แบบ PCF8574A? เปลี่ยน LCD_ADDR เป็น 0x3F");
      } else if (addr == 0x38) {
        Serial.print("  <- Keypad แบบ PCF8574A? เปลี่ยน KEYPAD_ADDR เป็น 0x38");
      }
      Serial.println();
      found++;
    }
  }
  if (found == 0) {
    Serial.println("  (none)  ตรวจ SDA=21 SCL=22, GND ร่วม, และไฟ 3.3V");
  }
}

void setup() {
  Serial.begin(115200);
  delay(200);

  Wire.begin(I2C_SDA, I2C_SCL);
  Wire.setClock(100000);
  scanI2C();

  lcd.init();
  // lcd.init() ของบางเวอร์ชันเรียก Wire.begin() เองโดยไม่ระบุพิน
  Wire.begin(I2C_SDA, I2C_SCL);

  lcd.backlight();
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("ESP32+PCF8574");  // 13 ตัว อันบนจอ 16 คอลัมน์

  if (!i2cPresent(LCD_ADDR) && i2cPresent(0x3F)) {
    lcd.setCursor(0, 1);
    lcd.print("LCD try 0x3F   ");
    Serial.println("LCD ไม่ตอบที่ 0x27 แต่เจอ 0x3F — แก้ LCD_ADDR เป็น 0x3F");
  } else if (!i2cPresent(KEYPAD_ADDR)) {
    lcd.setCursor(0, 1);
    lcd.print("No KP @0x20    ");
    Serial.println("ไม่พบ PCF8574 คีย์แพดที่ 0x20 — ตรวจจัมเปอร์ A0-A2 หรือชิป PCF8574A (0x38)");
  } else {
    lcd.setCursor(0, 1);
    lcd.print("Keypad 4x3 OK  ");
  }

  customKeypad.begin();
}

void loop() {
  char key = customKeypad.getKey();

  if (key) {
    Serial.print("Pressed: ");
    Serial.println(key);

    lcd.setCursor(0, 1);
    lcd.print("Key Pressed: ");
    lcd.print(key);
    lcd.print(' ');
  }
}
