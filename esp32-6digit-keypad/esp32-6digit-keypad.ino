#include <Wire.h>

#define LED_PIN 2
#define MAX_DIGITS 6
#define LCD_COLS 16

const int SDA_PIN = 21;
const int SCL_PIN = 22;

const byte ROWS = 4;
const byte COLS = 3;
char keymap[ROWS][COLS] = {
  {'1', '2', '3'},
  {'4', '5', '6'},
  {'7', '8', '9'},
  {'*', '0', '#'}
};
byte rowPins[ROWS] = {13, 32, 14, 27};
byte colPins[COLS] = {26, 25, 33};

char screen[LCD_COLS + 1];
byte screenLen = 0;
byte groupLen = 0;
bool lcdOk = false;
uint8_t lcdAddr = 0;
uint8_t lcdBl = 0x08;
uint32_t lastBlink = 0;
bool ledOn = false;

void clearScreen() {
  screenLen = 0;
  groupLen = 0;
  screen[0] = '\0';
}

void addDigit(char d) {
  if (groupLen >= MAX_DIGITS) {
    Serial.println("FULL");
    return;
  }
  if (screenLen >= LCD_COLS) {
    Serial.println("LINE FULL");
    return;
  }
  screen[screenLen++] = d;
  screen[screenLen] = '\0';
  groupLen++;
  Serial.print("VALUE ");
  Serial.println(screen);
}

void addSpace() {
  if (groupLen == 0) {
    return;
  }
  if (screenLen >= LCD_COLS) {
    Serial.println("LINE FULL");
    return;
  }
  screen[screenLen++] = ' ';
  screen[screenLen] = '\0';
  groupLen = 0;
  Serial.print("SPACE ");
  Serial.println(screen);
}

bool i2cWrite(uint8_t addr, uint8_t data) {
  Wire.beginTransmission(addr);
  Wire.write(data);
  return Wire.endTransmission() == 0;
}

void lcdPulse(uint8_t data) {
  i2cWrite(lcdAddr, data | 0x04 | lcdBl);
  delayMicroseconds(2);
  i2cWrite(lcdAddr, (data & ~0x04) | lcdBl);
  delayMicroseconds(50);
}

void lcdNibble(uint8_t nibble, bool rs) {
  uint8_t data = (nibble & 0x0F) << 4;
  if (rs) {
    data |= 0x01;
  }
  lcdPulse(data | lcdBl);
}

void lcdCmd(uint8_t value) {
  lcdNibble(value >> 4, false);
  lcdNibble(value & 0x0F, false);
}

void lcdChar(char value) {
  lcdNibble((uint8_t)value >> 4, true);
  lcdNibble((uint8_t)value & 0x0F, true);
}

void lcdClear() {
  if (!lcdOk) {
    return;
  }
  lcdCmd(0x01);
  delay(3);
}

void lcdAt(uint8_t col, uint8_t row) {
  if (!lcdOk) {
    return;
  }
  uint8_t pos = (row == 0) ? col : (0x40 + col);
  lcdCmd(0x80 | pos);
}

void lcdPrint(const char *text) {
  if (!lcdOk) {
    return;
  }
  while (*text) {
    lcdChar(*text++);
  }
}

uint8_t findLcd() {
  uint8_t list[] = {
    0x27, 0x3F, 0x26, 0x3E, 0x20, 0x38
  };
  for (uint8_t i = 0; i < 6; i++) {
    Wire.beginTransmission(list[i]);
    if (Wire.endTransmission() == 0) {
      return list[i];
    }
  }
  return 0;
}

void scanI2C() {
  Serial.println("I2C scan");
  uint8_t n = 0;
  for (uint8_t a = 1; a < 127; a++) {
    Wire.beginTransmission(a);
    if (Wire.endTransmission() == 0) {
      Serial.print("found 0x");
      Serial.println(a, HEX);
      n++;
    }
  }
  if (n == 0) {
    Serial.println("no I2C device");
  }
}

bool initLcd() {
  lcdAddr = findLcd();
  if (lcdAddr == 0) {
    Serial.println("LCD not found");
    return false;
  }
  Serial.print("LCD 0x");
  Serial.println(lcdAddr, HEX);
  i2cWrite(lcdAddr, lcdBl);
  delay(50);
  lcdNibble(0x03, false);
  delay(5);
  lcdNibble(0x03, false);
  delayMicroseconds(150);
  lcdNibble(0x03, false);
  lcdNibble(0x02, false);
  lcdCmd(0x28);
  lcdCmd(0x08);
  lcdCmd(0x01);
  delay(3);
  lcdCmd(0x06);
  lcdCmd(0x0C);
  return true;
}

void initKeys() {
  for (byte r = 0; r < ROWS; r++) {
    pinMode(rowPins[r], OUTPUT);
    digitalWrite(rowPins[r], HIGH);
  }
  for (byte c = 0; c < COLS; c++) {
    pinMode(colPins[c], INPUT_PULLUP);
  }
}

char readKey() {
  static char held = 0;
  char found = 0;
  for (byte r = 0; r < ROWS; r++) {
    digitalWrite(rowPins[r], LOW);
    delayMicroseconds(20);
    for (byte c = 0; c < COLS; c++) {
      if (digitalRead(colPins[c]) == LOW) {
        found = keymap[r][c];
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

void showPrompt() {
  lcdClear();
  lcdAt(0, 0);
  lcdPrint("Enter number");
  lcdAt(0, 1);
  if (screenLen > 0) {
    lcdPrint(screen);
  }
}

void showHello() {
  lcdClear();
  lcdAt(0, 0);
  lcdPrint("HELLO ESP32");
  lcdAt(0, 1);
  lcdPrint("* clear  # space");
}

void handleKey(char key) {
  if (key >= '0' && key <= '9') {
    addDigit(key);
    showPrompt();
    return;
  }

  if (key == '*') {
    clearScreen();
    Serial.println("CLEAR");
    showPrompt();
    return;
  }

  if (key == '#') {
    addSpace();
    showPrompt();
  }
}

void setup() {
  pinMode(LED_PIN, OUTPUT);
  Serial.begin(115200);
  delay(300);
  Serial.println("ESP32 keypad start");

  initKeys();
  clearScreen();
  Wire.begin(SDA_PIN, SCL_PIN);
  Wire.setClock(50000);
  delay(200);
  scanI2C();
  lcdOk = initLcd();

  if (lcdOk) {
    Serial.println("LCD OK");
    showHello();
    delay(1500);
    showPrompt();
  } else {
    Serial.println("use Serial only");
  }
}

void loop() {
  uint32_t now = millis();
  if (now - lastBlink > (lcdOk ? 500 : 150)) {
    lastBlink = now;
    ledOn = !ledOn;
    digitalWrite(LED_PIN, ledOn ? HIGH : LOW);
  }

  char key = readKey();
  if (key) {
    Serial.print("KEY ");
    Serial.println(key);
    handleKey(key);
  }
}
