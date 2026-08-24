/*
 * ESP32 + LCD 16x2 (I2C 0x27) + Keypad 3x4 (PCF8574 0x20)
 *
 * Arduino Library Manager:
 *   - LiquidCrystal I2C  (Frank de Brabander)
 *   - Keypad             (Mark Stanley, Alexander Brevig)
 *
 * Keypad_I2C.h / Keypad_I2C.cpp อยู่ในโฟลเดอร์สเก็ตช์นี้แล้ว
 * (Joe Young, https://github.com/joeyoung/arduino_keypads)
 *
 * I2C: SDA = GPIO 21, SCL = GPIO 22
 */

#include <Wire.h>
#include <LiquidCrystal_I2C.h>
#include <Keypad.h>      // ต้อง include ก่อน Keypad_I2C (makeKeymap + class Keypad)
#include <Keypad_I2C.h>

#define LCD_ADDR     0x27
#define KEYPAD_ADDR  0x20

LiquidCrystal_I2C lcd(LCD_ADDR, 16, 2);

const byte ROWS = 4;
const byte COLS = 3;

char keys[ROWS][COLS] = {
  {'1', '2', '3'},
  {'4', '5', '6'},
  {'7', '8', '9'},
  {'*', '0', '#'}
};

// PCF8574 คีย์แพด: แถว P0–P3, คอลัมน์ P4–P6
byte rowPins[ROWS] = {0, 1, 2, 3};
byte colPins[COLS] = {4, 5, 6};

Keypad_I2C customKeypad(makeKeymap(keys), rowPins, colPins, ROWS, COLS, KEYPAD_ADDR);

void setup() {
  Serial.begin(115200);
  Wire.begin(21, 22);

  lcd.init();
  // lcd.init() ของบางเวอร์ชันเรียก Wire.begin() เองโดยไม่ระบุพิน
  // ล็อกกลับไป GPIO 21/22 ของ ESP32 หลังจอพร้อม
  Wire.begin(21, 22);

  lcd.backlight();
  lcd.setCursor(0, 0);
  lcd.print("ESP32 Keypad Test");

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
    lcd.print(" ");
  }
}
