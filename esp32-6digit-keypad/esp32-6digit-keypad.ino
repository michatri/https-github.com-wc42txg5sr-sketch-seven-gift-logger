/*
 * ESP32 + LCD 16x2 + Keypad 4x3
 * รับตัวเลขได้สูงสุด 6 หลัก แล้วแสดงบนจอ
 *
 * ปุ่ม:
 *   0-9  = พิมพ์ตัวเลข (สูงสุด 6 หลัก)
 *   *    = ลบตัวสุดท้าย
 *   #    = ยืนยันค่าที่พิมพ์
 *
 * ไลบรารีใน Arduino IDE:
 *   - Keypad by Mark Stanley, Alexander Brevig
 *   - LiquidCrystal I2C by Frank de Brabander  (เมื่อใช้จอ I2C)
 */

#include <Keypad.h>
#include "DigitInput.h"

#define USE_I2C_LCD 1

#if USE_I2C_LCD
#include <Wire.h>
#include <LiquidCrystal_I2C.h>
#else
#include <LiquidCrystal.h>
#endif

static const uint32_t SERIAL_BAUD = 115200;
static const uint32_t CONFIRM_HOLD_MS = 2000;

#if USE_I2C_LCD
static const int LCD_SDA_PIN = 21;
static const int LCD_SCL_PIN = 22;
static const uint8_t LCD_ADDR_PRIMARY = 0x27;
static const uint8_t LCD_ADDR_FALLBACK = 0x3F;
LiquidCrystal_I2C *lcd = nullptr;
#else
// RS, E, D4, D5, D6, D7
LiquidCrystal lcd(4, 16, 17, 18, 19, 23);
#endif

const byte ROWS = 4;
const byte COLS = 3;
char keys[ROWS][COLS] = {
  {'1', '2', '3'},
  {'4', '5', '6'},
  {'7', '8', '9'},
  {'*', '0', '#'}
};

// คีย์แพด 4x3 ขาจากซ้ายไปขวา: R1 R2 R3 R4 C1 C2 C3
byte rowPins[ROWS] = {13, 12, 14, 27};
byte colPins[COLS] = {26, 25, 33};

Keypad keypad = Keypad(makeKeymap(keys), rowPins, colPins, ROWS, COLS);

DigitInput input;
bool showingResult = false;
uint32_t resultShownAt = 0;

#if USE_I2C_LCD
void scanI2C() {
  Serial.println(F("Scanning I2C..."));
  uint8_t found = 0;
  for (uint8_t addr = 1; addr < 127; addr++) {
    Wire.beginTransmission(addr);
    if (Wire.endTransmission() == 0) {
      Serial.printf("  found device at 0x%02X\n", addr);
      found++;
    }
  }
  if (found == 0) {
    Serial.println(F("  no I2C device found (check SDA/SCL/VCC/GND)"));
  }
}

bool probeI2CAddress(uint8_t addr) {
  Wire.beginTransmission(addr);
  return Wire.endTransmission() == 0;
}

void initLcd() {
  uint8_t addr = LCD_ADDR_PRIMARY;
  if (!probeI2CAddress(addr) && probeI2CAddress(LCD_ADDR_FALLBACK)) {
    addr = LCD_ADDR_FALLBACK;
  }

  lcd = new LiquidCrystal_I2C(addr, 16, 2);
  lcd->init();
  lcd->backlight();
  lcd->clear();
  Serial.printf("LCD I2C address: 0x%02X\n", addr);
}

#define LCD_CLEAR() lcd->clear()
#define LCD_SET_CURSOR(col, row) lcd->setCursor((col), (row))
#define LCD_PRINT(msg) lcd->print(msg)
#else
void initLcd() {
  lcd.begin(16, 2);
  lcd.clear();
}

#define LCD_CLEAR() lcd.clear()
#define LCD_SET_CURSOR(col, row) lcd.setCursor((col), (row))
#define LCD_PRINT(msg) lcd.print(msg)
#endif

void renderPrompt() {
  LCD_CLEAR();
  LCD_SET_CURSOR(0, 0);
  LCD_PRINT(F("Enter number"));
  LCD_SET_CURSOR(0, 1);
  if (input.length == 0) {
    LCD_PRINT(F("______"));
    return;
  }

  LCD_PRINT(input.value);
  for (size_t i = input.length; i < DIGIT_INPUT_MAX; i++) {
    LCD_PRINT('_');
  }
}

void renderFullWarning() {
  LCD_SET_CURSOR(0, 1);
  LCD_PRINT(F("Full (6 digits)"));
}

void renderNeedDigits() {
  LCD_SET_CURSOR(0, 1);
  LCD_PRINT(F("Need 1-6 digits "));
}

void renderConfirmed() {
  LCD_CLEAR();
  LCD_SET_CURSOR(0, 0);
  LCD_PRINT(F("Confirmed"));
  LCD_SET_CURSOR(0, 1);
  LCD_PRINT(input.value);
}

void appendDigit(char digit) {
  const DigitInputResult result = digitInputAppend(&input, digit);
  if (result == DIGIT_INPUT_IGNORED_FULL) {
    Serial.println(F("IGNORED: already 6 digits"));
    renderFullWarning();
    delay(400);
    renderPrompt();
    return;
  }

  Serial.printf("DIGIT: %c  VALUE: %s\n", digit, input.value);
  renderPrompt();
}

void deleteLastDigit() {
  const DigitInputResult result = digitInputBackspace(&input);
  if (result == DIGIT_INPUT_IGNORED_EMPTY) {
    Serial.println(F("CLEAR"));
  } else {
    Serial.printf("BACKSPACE  VALUE: %s\n", input.value);
  }
  renderPrompt();
}

void confirmInput() {
  if (digitInputConfirm(&input) != DIGIT_INPUT_CONFIRMED) {
    Serial.println(F("CONFIRM ignored: empty"));
    renderNeedDigits();
    delay(700);
    renderPrompt();
    return;
  }

  Serial.printf("CONFIRM: %s\n", input.value);
  renderConfirmed();
  showingResult = true;
  resultShownAt = millis();
}

void resetEntry() {
  showingResult = false;
  digitInputClear(&input);
  renderPrompt();
}

void handleKey(char key) {
  if (showingResult) {
    resetEntry();
  }

  if (key >= '0' && key <= '9') {
    appendDigit(key);
    return;
  }
  if (key == '*') {
    deleteLastDigit();
    return;
  }
  if (key == '#') {
    confirmInput();
  }
}

void setup() {
  Serial.begin(SERIAL_BAUD);
  delay(200);
  Serial.println();
  Serial.println(F("ESP32 6-digit keypad ready"));
  Serial.println(F("Keys: 0-9 enter, * delete, # confirm"));

#if USE_I2C_LCD
  Wire.begin(LCD_SDA_PIN, LCD_SCL_PIN);
  scanI2C();
#endif
  initLcd();

  digitInputInit(&input);
  renderPrompt();
}

void loop() {
  if (showingResult && (millis() - resultShownAt >= CONFIRM_HOLD_MS)) {
    resetEntry();
  }

  const char key = keypad.getKey();
  if (key) {
    Serial.printf("KEY: %c\n", key);
    handleKey(key);
  }
}
