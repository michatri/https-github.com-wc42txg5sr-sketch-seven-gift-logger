/*
 * ESP32 + LCD 16x2 + Keypad 4x3
 * กดตัวเลขได้สูงสุด 6 หลัก
 *
 * ไฟล์เดียว วางใน Arduino IDE ได้เลย ไม่ต้องมีไฟล์อื่น
 * ไม่ต้องติดตั้งไลบรารีเพิ่ม ใช้ได้เลยหลังติดตั้งบอร์ด ESP32
 *
 * ปุ่ม: 0-9 พิมพ์, * ลบ, # ยืนยัน
 *
 * ถ้าจอว่าง:
 *   1) ต้องกด Upload ก่อน ต่อสายอย่างเดียวจอจะไม่ขึ้น
 *   2) ดูไฟ LED บนบอร์ด (GPIO 2) ว่ากระพริบหรือไม่
 *   3) เปิด Serial Monitor 115200 แล้วกดปุ่ม EN บนบอร์ด
 *   4) หมุนสกรูสีน้ำเงินหลังจอ (contrast)
 */

#include <Wire.h>

#define USE_I2C_LCD 1
#define LED_PIN 2
#define SERIAL_BAUD 115200
#define CONFIRM_HOLD_MS 2000
#define DIGIT_INPUT_MAX 6

enum DigitInputResult {
  DIGIT_INPUT_OK = 0,
  DIGIT_INPUT_IGNORED_FULL,
  DIGIT_INPUT_IGNORED_EMPTY,
  DIGIT_INPUT_CONFIRMED
};

struct DigitInput {
  char value[DIGIT_INPUT_MAX + 1];
  size_t length;
};

void digitInputClear(DigitInput *input) {
  input->length = 0;
  input->value[0] = '\0';
}

void digitInputInit(DigitInput *input) {
  digitInputClear(input);
}

DigitInputResult digitInputAppend(DigitInput *input, char digit) {
  if (digit < '0' || digit > '9') {
    return DIGIT_INPUT_IGNORED_EMPTY;
  }
  if (input->length >= DIGIT_INPUT_MAX) {
    return DIGIT_INPUT_IGNORED_FULL;
  }
  input->value[input->length++] = digit;
  input->value[input->length] = '\0';
  return DIGIT_INPUT_OK;
}

DigitInputResult digitInputBackspace(DigitInput *input) {
  if (input->length == 0) {
    return DIGIT_INPUT_IGNORED_EMPTY;
  }
  input->value[--input->length] = '\0';
  return DIGIT_INPUT_OK;
}

DigitInputResult digitInputConfirm(const DigitInput *input) {
  if (input->length == 0) {
    return DIGIT_INPUT_IGNORED_EMPTY;
  }
  return DIGIT_INPUT_CONFIRMED;
}

static const int LCD_SDA_PIN = 21;
static const int LCD_SCL_PIN = 22;

const byte ROWS = 4;
const byte COLS = 3;
char keys[ROWS][COLS] = {
  {'1', '2', '3'},
  {'4', '5', '6'},
  {'7', '8', '9'},
  {'*', '0', '#'}
};

// ขาคีย์แพดซ้ายไปขวา: R1 R2 R3 R4 C1 C2 C3
byte rowPins[ROWS] = {13, 12, 14, 27};
byte colPins[COLS] = {26, 25, 33};

DigitInput input;
bool showingResult = false;
uint32_t resultShownAt = 0;
bool lcdReady = false;
uint8_t lcdAddr = 0;
uint8_t lcdBacklight = 0x08;
uint32_t lastHeartbeatMs = 0;
uint32_t lastStatusMs = 0;
bool ledOn = false;

#if !USE_I2C_LCD
#include <LiquidCrystal.h>
LiquidCrystal parallelLcd(4, 16, 17, 18, 19, 23);
#endif

bool i2cWriteRaw(uint8_t addr, uint8_t data) {
  Wire.beginTransmission(addr);
  Wire.write(data);
  return Wire.endTransmission() == 0;
}

void lcdPulse(uint8_t data) {
  i2cWriteRaw(lcdAddr, data | 0x04 | lcdBacklight);
  delayMicroseconds(2);
  i2cWriteRaw(lcdAddr, (data & ~0x04) | lcdBacklight);
  delayMicroseconds(50);
}

void lcdWrite4(uint8_t nibble, bool rs) {
  uint8_t data = (nibble & 0x0F) << 4;
  if (rs) {
    data |= 0x01;
  }
  data |= lcdBacklight;
  lcdPulse(data);
}

void lcdCommand(uint8_t value) {
  lcdWrite4(value >> 4, false);
  lcdWrite4(value & 0x0F, false);
}

void lcdWriteChar(char value) {
  lcdWrite4((uint8_t)value >> 4, true);
  lcdWrite4((uint8_t)value & 0x0F, true);
}

void lcdClearScreen() {
  if (!lcdReady) {
    return;
  }
#if USE_I2C_LCD
  lcdCommand(0x01);
  delay(3);
#else
  parallelLcd.clear();
#endif
}

void lcdAt(uint8_t col, uint8_t row) {
  if (!lcdReady) {
    return;
  }
#if USE_I2C_LCD
  lcdCommand(0x80 | (row == 0 ? col : (0x40 + col)));
#else
  parallelLcd.setCursor(col, row);
#endif
}

void lcdText(const char *text) {
  if (!lcdReady) {
    return;
  }
#if USE_I2C_LCD
  while (*text) {
    lcdWriteChar(*text++);
  }
#else
  parallelLcd.print(text);
#endif
}

uint8_t findLcdAddress() {
  static const uint8_t candidates[] = {
    0x27, 0x3F, 0x26, 0x25, 0x24, 0x23, 0x22, 0x21, 0x20,
    0x3E, 0x3D, 0x3C, 0x3B, 0x3A, 0x39, 0x38
  };
  for (uint8_t i = 0; i < sizeof(candidates); i++) {
    Wire.beginTransmission(candidates[i]);
    if (Wire.endTransmission() == 0) {
      return candidates[i];
    }
  }
  return 0;
}

void scanAllI2C() {
  Serial.println("Scanning I2C on SDA=21 SCL=22 ...");
  uint8_t found = 0;
  for (uint8_t addr = 1; addr < 127; addr++) {
    Wire.beginTransmission(addr);
    if (Wire.endTransmission() == 0) {
      Serial.printf("  found 0x%02X\n", addr);
      found++;
    }
  }
  if (found == 0) {
    Serial.println("  NO I2C DEVICE. Check VCC GND SDA SCL.");
  }
}

bool initI2CLcd() {
  delay(100);
  lcdAddr = findLcdAddress();
  if (lcdAddr == 0) {
    Serial.println("LCD I2C not found");
    return false;
  }

  Serial.printf("LCD I2C address 0x%02X\n", lcdAddr);
  i2cWriteRaw(lcdAddr, lcdBacklight);
  delay(50);

  lcdWrite4(0x03, false);
  delay(5);
  lcdWrite4(0x03, false);
  delayMicroseconds(150);
  lcdWrite4(0x03, false);
  delayMicroseconds(150);
  lcdWrite4(0x02, false);

  lcdCommand(0x28);
  lcdCommand(0x08);
  lcdCommand(0x01);
  delay(3);
  lcdCommand(0x06);
  lcdCommand(0x0C);
  return true;
}

void initKeypad() {
  for (byte r = 0; r < ROWS; r++) {
    pinMode(rowPins[r], OUTPUT);
    digitalWrite(rowPins[r], HIGH);
  }
  for (byte c = 0; c < COLS; c++) {
    pinMode(colPins[c], INPUT_PULLUP);
  }
}

char readKeypad() {
  static char held = 0;
  char found = 0;

  for (byte r = 0; r < ROWS; r++) {
    digitalWrite(rowPins[r], LOW);
    delayMicroseconds(20);
    for (byte c = 0; c < COLS; c++) {
      if (digitalRead(colPins[c]) == LOW) {
        found = keys[r][c];
      }
    }
    digitalWrite(rowPins[r], HIGH);
  }

  if (found == 0) {
    held = 0;
    return 0;
  }
  if (found == held) {
    return 0;
  }
  delay(25);
  held = found;
  return found;
}

void renderPrompt() {
  lcdClearScreen();
  lcdAt(0, 0);
  lcdText("Enter number");
  lcdAt(0, 1);
  if (input.length == 0) {
    lcdText("______");
    return;
  }
  lcdText(input.value);
  char pad[8];
  size_t remain = DIGIT_INPUT_MAX - input.length;
  for (size_t i = 0; i < remain; i++) {
    pad[i] = '_';
  }
  pad[remain] = '\0';
  lcdText(pad);
}

void renderConfirmed() {
  lcdClearScreen();
  lcdAt(0, 0);
  lcdText("Confirmed");
  lcdAt(0, 1);
  lcdText(input.value);
}

void showSplash() {
  lcdClearScreen();
  lcdAt(0, 0);
  lcdText("HELLO ESP32");
  lcdAt(0, 1);
  lcdText("LCD OK 123456");
}

void appendDigit(char digit) {
  if (digitInputAppend(&input, digit) == DIGIT_INPUT_IGNORED_FULL) {
    Serial.println("IGNORED: already 6 digits");
    lcdAt(0, 1);
    lcdText("Full (6 digits)");
    delay(400);
    renderPrompt();
    return;
  }
  Serial.printf("DIGIT: %c  VALUE: %s\n", digit, input.value);
  renderPrompt();
}

void deleteLastDigit() {
  if (digitInputBackspace(&input) == DIGIT_INPUT_IGNORED_EMPTY) {
    Serial.println("CLEAR");
  } else {
    Serial.printf("BACKSPACE  VALUE: %s\n", input.value);
  }
  renderPrompt();
}

void confirmInput() {
  if (digitInputConfirm(&input) != DIGIT_INPUT_CONFIRMED) {
    Serial.println("CONFIRM ignored: empty");
    lcdAt(0, 1);
    lcdText("Need 1-6 digits");
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

void heartbeat() {
  uint32_t now = millis();
  uint32_t interval = lcdReady ? 500 : 150;
  if (now - lastHeartbeatMs < interval) {
    return;
  }
  lastHeartbeatMs = now;
  ledOn = !ledOn;
  digitalWrite(LED_PIN, ledOn ? HIGH : LOW);

  if (!lcdReady && (now - lastStatusMs >= 2000)) {
    lastStatusMs = now;
    Serial.println("WAITING: LCD not found. Open Serial 115200. Adjust contrast. Check SDA=21 SCL=22 VCC GND.");
  }
}

void setup() {
  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, HIGH);

  Serial.begin(SERIAL_BAUD);
  delay(300);
  Serial.println();
  Serial.println("================================");
  Serial.println("ESP32 6-digit keypad starting");
  Serial.println("LED on GPIO2 should blink");
  Serial.println("================================");

  initKeypad();
  digitInputInit(&input);

#if USE_I2C_LCD
  Wire.begin(LCD_SDA_PIN, LCD_SCL_PIN);
  Wire.setClock(50000);
  delay(200);
  scanAllI2C();
  lcdReady = initI2CLcd();
#else
  parallelLcd.begin(16, 2);
  lcdReady = true;
#endif

  if (lcdReady) {
    Serial.println("LCD ready: you should see HELLO ESP32");
    showSplash();
    delay(2000);
    renderPrompt();
  } else {
    Serial.println("LCD not ready. Keypad still works in Serial Monitor.");
    Serial.println("Type on keypad and watch this window.");
  }

  Serial.println("Keys: 0-9 enter, * delete, # confirm");
}

void loop() {
  heartbeat();

  if (showingResult && (millis() - resultShownAt >= CONFIRM_HOLD_MS)) {
    resetEntry();
  }

  const char key = readKeypad();
  if (key) {
    Serial.printf("KEY: %c\n", key);
    handleKey(key);
  }
}
