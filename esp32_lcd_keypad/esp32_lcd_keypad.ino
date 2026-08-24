/*
 * ESP32 + LCD 16x2 + Keypad 3x4 ผ่าน PCF8574 (I2C)
 *
 * บัส I2C ร่วมกัน (ค่าเริ่มต้น ESP32):
 *   SDA = GPIO 21
 *   SCL = GPIO 22
 *
 * อุปกรณ์บนบัส:
 *   1) LCD 1602 I2C backpack  → PCF8574 ที่ 0x27 (หรือ 0x3F)
 *   2) PCF8574 สำหรับคีย์แพด  → 0x20 (A0=A1=A2=GND)
 *
 * ไม่ต้องติดตั้งไลบรารีเพิ่ม ใช้แค่ Wire.h
 */

#include <Arduino.h>
#include <Wire.h>

// ---------------------------------------------------------------------------
// พิน I2C ของ ESP32
// ---------------------------------------------------------------------------
static const int PIN_SDA = 21;
static const int PIN_SCL = 22;

// เปลี่ยนตามผล I2C Scanner ถ้าโมดูลใช้ address อื่น
static const uint8_t LCD_ADDR = 0x27;
static const uint8_t KEYPAD_ADDR = 0x20;

static const uint32_t I2C_FREQ = 100000;  // 100 kHz เสถียรกับสายยาว

// ===========================================================================
// LCD 16x2 ผ่าน PCF8574 backpack
// แมปพินมาตรฐานของโมดูล I2C LCD ส่วนใหญ่:
//   P0=RS  P1=RW  P2=E  P3=Backlight  P4=D4  P5=D5  P6=D6  P7=D7
// ===========================================================================
class LcdPcf8574 {
 public:
  explicit LcdPcf8574(uint8_t addr) : addr_(addr) {}

  bool begin() {
    if (!isPresent()) {
      return false;
    }
    backlight_ = 0x08;
    delay(50);

    // ลำดับเริ่มต้น HD44780 โหมด 4 บิต
    write4(0x03);
    delay(5);
    write4(0x03);
    delayMicroseconds(150);
    write4(0x03);
    delayMicroseconds(150);
    write4(0x02);  // เข้า 4-bit

    command(0x28);  // 2 บรรทัด, 5x8
    command(0x08);  // display off
    command(0x01);  // clear
    delay(2);
    command(0x06);  // entry mode
    command(0x0C);  // display on, cursor off
    return true;
  }

  bool isPresent() const { return devicePresent(addr_); }

  void clear() {
    command(0x01);
    delay(2);
    col_ = 0;
    row_ = 0;
  }

  void setCursor(uint8_t col, uint8_t row) {
    col_ = col;
    row_ = row > 1 ? 1 : row;
    static const uint8_t rowOff[] = {0x00, 0x40};
    command(0x80 | (rowOff[row_] + col_));
  }

  void print(const char *text) {
    while (*text) {
      writeChar(*text++);
    }
  }

  void print(char c) { writeChar(c); }

  void printLine(uint8_t row, const char *text) {
    char line[17];
    memset(line, ' ', 16);
    line[16] = '\0';
    size_t n = strlen(text);
    if (n > 16) {
      n = 16;
    }
    memcpy(line, text, n);
    setCursor(0, row);
    print(line);
  }

  void backlight(bool on) {
    backlight_ = on ? 0x08 : 0x00;
    expanderWrite(backlight_);
  }

 private:
  static const uint8_t RS = 0x01;
  static const uint8_t EN = 0x04;

  uint8_t addr_;
  uint8_t backlight_ = 0x08;
  uint8_t col_ = 0;
  uint8_t row_ = 0;

  static bool devicePresent(uint8_t addr) {
    Wire.beginTransmission(addr);
    return Wire.endTransmission() == 0;
  }

  void expanderWrite(uint8_t data) {
    Wire.beginTransmission(addr_);
    Wire.write(data | backlight_);
    Wire.endTransmission();
  }

  void pulseEnable(uint8_t data) {
    expanderWrite(data | EN);
    delayMicroseconds(1);
    expanderWrite(data & ~EN);
    delayMicroseconds(50);
  }

  void write4(uint8_t nibble) {
    uint8_t data = (nibble << 4) & 0xF0;
    pulseEnable(data);
  }

  void send(uint8_t value, uint8_t mode) {
    uint8_t high = value & 0xF0;
    uint8_t low = (value << 4) & 0xF0;
    pulseEnable(high | mode);
    pulseEnable(low | mode);
  }

  void command(uint8_t value) { send(value, 0); }

  void writeChar(char c) {
    send(static_cast<uint8_t>(c), RS);
    if (col_ < 15) {
      col_++;
    }
  }
};

// ===========================================================================
// Keypad 3x4 ผ่าน PCF8574
//   P0..P3 = แถว 1..4 (output ดึงลงทีละแถว)
//   P4..P6 = คอลัมน์ 1..3 (input, PCF8574 มี weak pull-up เมื่อเขียน 1)
//   P7     = ไม่ใช้
//
// ผังปุ่ม:
//   1 2 3
//   4 5 6
//   7 8 9
//   * 0 #
// ===========================================================================
class KeypadPcf8574 {
 public:
  explicit KeypadPcf8574(uint8_t addr) : addr_(addr) {}

  bool begin() {
    if (!isPresent()) {
      return false;
    }
    write(0xFF);  // ทุกพินเป็น input / ปล่อยสูง
    return true;
  }

  bool isPresent() const {
    Wire.beginTransmission(addr_);
    return Wire.endTransmission() == 0;
  }

  // คืนค่าปุ่มที่กด หรือ 0 ถ้าไม่มี (เรียกบ่อยใน loop, มี debounce ในตัว)
  char readKey() {
    const uint32_t now = millis();
    const char found = scan();

    if (found == 0) {
      if (now - lastChangeMs_ > RELEASE_MS) {
        held_ = 0;
      }
      return 0;
    }

    if (found == held_) {
      return 0;  // ยังกดค้าง ปุ่มเดิม
    }

    if (now - lastChangeMs_ < DEBOUNCE_MS) {
      return 0;
    }

    held_ = found;
    lastChangeMs_ = now;
    return found;
  }

 private:
  static const uint32_t DEBOUNCE_MS = 40;
  static const uint32_t RELEASE_MS = 80;

  static constexpr char kMap[4][3] = {
      {'1', '2', '3'},
      {'4', '5', '6'},
      {'7', '8', '9'},
      {'*', '0', '#'},
  };

  uint8_t addr_;
  char held_ = 0;
  uint32_t lastChangeMs_ = 0;

  void write(uint8_t data) {
    Wire.beginTransmission(addr_);
    Wire.write(data);
    Wire.endTransmission();
  }

  uint8_t read() {
    Wire.requestFrom(addr_, static_cast<uint8_t>(1));
    if (Wire.available()) {
      return static_cast<uint8_t>(Wire.read());
    }
    return 0xFF;
  }

  char scan() {
    for (uint8_t row = 0; row < 4; row++) {
      // ดึงแถวนี้ลง GND ที่เหลือเป็น 1 (รวมคอลัมน์ที่เป็น input)
      const uint8_t pattern = static_cast<uint8_t>(~(1u << row));
      write(pattern);
      delayMicroseconds(80);
      const uint8_t val = read();
      for (uint8_t col = 0; col < 3; col++) {
        if ((val & (1u << (col + 4))) == 0) {
          write(0xFF);
          return kMap[row][col];
        }
      }
    }
    write(0xFF);
    return 0;
  }
};

LcdPcf8574 lcd(LCD_ADDR);
KeypadPcf8574 keypad(KEYPAD_ADDR);

static char typed[17];
static uint8_t typedLen = 0;

static void scanI2cBus() {
  Serial.println(F("I2C scan:"));
  uint8_t found = 0;
  for (uint8_t addr = 1; addr < 127; addr++) {
    Wire.beginTransmission(addr);
    if (Wire.endTransmission() == 0) {
      Serial.printf("  พบอุปกรณ์ที่ 0x%02X\n", addr);
      found++;
    }
  }
  if (found == 0) {
    Serial.println(F("  ไม่พบอุปกรณ์ — ตรวจสาย SDA/SCL/VCC/GND และ address jumper"));
  }
}

static void resetTyped() {
  typedLen = 0;
  typed[0] = '\0';
  lcd.printLine(1, "                ");
}

void setup() {
  Serial.begin(115200);
  delay(200);
  Serial.println();
  Serial.println(F("ESP32 + LCD 16x2 + Keypad 3x4 ผ่าน PCF8574"));

  Wire.begin(PIN_SDA, PIN_SCL, I2C_FREQ);
  scanI2cBus();

  const bool lcdOk = lcd.begin();
  const bool keyOk = keypad.begin();

  Serial.printf("LCD    0x%02X : %s\n", LCD_ADDR, lcdOk ? "OK" : "ไม่พบ");
  Serial.printf("Keypad 0x%02X : %s\n", KEYPAD_ADDR, keyOk ? "OK" : "ไม่พบ");

  if (lcdOk) {
    lcd.clear();
    lcd.printLine(0, "ESP32 Ready");
    if (keyOk) {
      lcd.printLine(1, "Press 3x4 key");
    } else {
      lcd.printLine(1, "No keypad 0x20");
    }
  }
}

void loop() {
  const char key = keypad.readKey();
  if (key == 0) {
    return;
  }

  Serial.printf("Key: %c\n", key);

  if (key == '*') {
    resetTyped();
    lcd.printLine(0, "* = clear");
    return;
  }

  if (key == '#') {
    lcd.printLine(0, "# entered");
    lcd.printLine(1, typedLen ? typed : "(empty)");
    return;
  }

  if (typedLen < 16) {
    typed[typedLen++] = key;
    typed[typedLen] = '\0';
  }

  lcd.printLine(0, "Input:");
  lcd.printLine(1, typed);
}
