/*
 * ============================================================
 *  บอร์ด 1 : ESP32 + Keypad 3x4 + LCD 16x2 I2C
 * ============================================================
 *
 * Keypad:
 *   byte rowPins[ROWS] = {4, 12, 14, 5};
 *   byte colPins[COLS] = {26, 25, 33};
 *   * = ช่องว่าง     # = เคลียร์จอ     พิมพ์ได้ 6 ตัว
 *
 * LCD 16x2 I2C:
 *   SDA=21  SCL=22  VCC=5V  GND=GND
 *
 * ส่งข้อความไปบอร์ด 2 (ESP32-S3) ด้วย ESP-NOW ผ่าน WiFi MAC
 *
 * ไลบรารี: Keypad, LiquidCrystal I2C
 * บอร์ด Arduino IDE: ESP32 Dev Module
 */

#include <WiFi.h>
#include <esp_now.h>
#include <esp_wifi.h>
#include <esp_idf_version.h>
#include <Wire.h>
#include <Keypad.h>
#include <LiquidCrystal_I2C.h>

// ---------- ตั้งค่า ESP-NOW / MAC ----------
#define MAX_CHARS           6
#define ESPNOW_CHANNEL      1

// ใส่ MAC ของบอร์ด ESP32-S3 (ดูจาก Serial หรือจอ LED ตอนบูต)
// ตัวอย่าง 24:6F:28:AA:BB:CC  ->  {0x24, 0x6F, 0x28, 0xAA, 0xBB, 0xCC}
// FF:FF:FF:FF:FF:FF = ส่งแบบ broadcast
uint8_t ledMac[] = {0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF};

// ---------- Keypad 3x4 ----------
const byte ROWS = 4;
const byte COLS = 3;
char keys[ROWS][COLS] = {
  {'1', '2', '3'},
  {'4', '5', '6'},
  {'7', '8', '9'},
  {'*', '0', '#'}
};
byte rowPins[ROWS] = {4, 12, 14, 5};
byte colPins[COLS] = {26, 25, 33};
Keypad keypad = Keypad(makeKeymap(keys), rowPins, colPins, ROWS, COLS);

// ---------- LCD 16x2 I2C ----------
#define LCD_SDA 21
#define LCD_SCL 22
LiquidCrystal_I2C *lcd = nullptr;
bool lcdOk = false;

char textBuf[MAX_CHARS + 1];
byte textLen = 0;
bool nowOk = false;

String macStr(const uint8_t *mac) {
  char s[18];
  sprintf(s, "%02X:%02X:%02X:%02X:%02X:%02X",
          mac[0], mac[1], mac[2], mac[3], mac[4], mac[5]);
  return String(s);
}

String macCompact(const uint8_t *mac) {
  char s[13];
  sprintf(s, "%02X%02X%02X%02X%02X%02X",
          mac[0], mac[1], mac[2], mac[3], mac[4], mac[5]);
  return String(s);
}

uint8_t findLcdAddr() {
  uint8_t tryAddr[] = {0x27, 0x3F};
  for (uint8_t i = 0; i < 2; i++) {
    Wire.beginTransmission(tryAddr[i]);
    if (Wire.endTransmission() == 0) return tryAddr[i];
  }
  for (uint8_t a = 0x20; a <= 0x3F; a++) {
    Wire.beginTransmission(a);
    if (Wire.endTransmission() == 0) return a;
  }
  return 0;
}

void showLcd(const char *line1, const char *line2) {
  if (!lcdOk) return;
  lcd->setCursor(0, 0);
  lcd->print("                ");
  lcd->setCursor(0, 0);
  lcd->print(line1);
  lcd->setCursor(0, 1);
  lcd->print("                ");
  lcd->setCursor(0, 1);
  lcd->print(line2);
}

void refreshLcd(const char *status) {
  char line1[17];
  memset(line1, ' ', 16);
  line1[0] = '>';
  for (byte i = 0; i < MAX_CHARS; i++) {
    line1[1 + i] = (i < textLen) ? textBuf[i] : '_';
  }
  line1[16] = 0;
  showLcd(line1, status);
  Serial.println(status);
}

#if ESP_IDF_VERSION >= ESP_IDF_VERSION_VAL(5, 5, 0)
void onSent(const esp_now_send_info_t *info, esp_now_send_status_t status) {
  (void)info;
  Serial.println(status == ESP_NOW_SEND_SUCCESS ? "NOW OK" : "NOW fail");
}
#else
void onSent(const uint8_t *mac, esp_now_send_status_t status) {
  (void)mac;
  Serial.println(status == ESP_NOW_SEND_SUCCESS ? "NOW OK" : "NOW fail");
}
#endif

bool startNow() {
  WiFi.mode(WIFI_STA);
  WiFi.disconnect(true);
  delay(80);
  esp_wifi_set_promiscuous(true);
  esp_wifi_set_channel(ESPNOW_CHANNEL, WIFI_SECOND_CHAN_NONE);
  esp_wifi_set_promiscuous(false);

  uint8_t myMac[6];
  WiFi.macAddress(myMac);
  Serial.print("Keypad MAC = ");
  Serial.println(macStr(myMac));
  Serial.print("LED MAC    = ");
  Serial.println(macStr(ledMac));

  if (esp_now_init() != ESP_OK) return false;
  esp_now_register_send_cb(onSent);

  esp_now_peer_info_t peer = {};
  memcpy(peer.peer_addr, ledMac, 6);
  peer.channel = ESPNOW_CHANNEL;
  peer.encrypt = false;
  peer.ifidx = WIFI_IF_STA;
  if (esp_now_is_peer_exist(ledMac)) esp_now_del_peer(ledMac);
  return esp_now_add_peer(&peer) == ESP_OK;
}

void sendNow() {
  char pkt[16];
  if (textLen == 0) strcpy(pkt, "CLR");
  else sprintf(pkt, "SET:%s", textBuf);

  Serial.print("TX ");
  Serial.print(pkt);
  Serial.print(" -> ");
  Serial.println(macStr(ledMac));

  if (!nowOk) return;
  if (esp_now_send(ledMac, (uint8_t *)pkt, strlen(pkt)) != ESP_OK) {
    refreshLcd("NOW send fail");
  }
}

void clearAll() {
  memset(textBuf, 0, sizeof(textBuf));
  textLen = 0;
  refreshLcd("# cleared");
  sendNow();
}

void onKey(char k) {
  if (k == '#') {
    clearAll();
    return;
  }
  if (k != '*' && (k < '0' || k > '9')) return;
  if (textLen >= MAX_CHARS) {
    refreshLcd("full 6  # clear");
    return;
  }

  textBuf[textLen++] = (k == '*') ? ' ' : k;
  textBuf[textLen] = 0;

  char st[17];
  if (textLen >= MAX_CHARS) strcpy(st, "sent 6 chars");
  else if (k == '*') strcpy(st, "* space");
  else sprintf(st, "typed %d/6", textLen);
  refreshLcd(st);
  sendNow();
}

void setup() {
  Serial.begin(115200);
  delay(200);
  Serial.println("BOARD 1 ESP32 keypad + LCD");

  memset(textBuf, 0, sizeof(textBuf));
  Wire.begin(LCD_SDA, LCD_SCL);
  delay(50);
  uint8_t addr = findLcdAddr();
  if (addr) {
    lcd = new LiquidCrystal_I2C(addr, 16, 2);
    lcd->init();
    lcd->backlight();
    lcd->clear();
    lcdOk = true;
    Serial.print("LCD addr 0x");
    Serial.println(addr, HEX);
  } else {
    Serial.println("ไม่พบ LCD I2C (SDA21 SCL22)");
  }

  keypad.setDebounceTime(40);
  nowOk = startNow();

  uint8_t myMac[6];
  WiFi.macAddress(myMac);
  showLcd("My MAC", macCompact(myMac).c_str());
  delay(1500);
  showLcd("LED MAC", macCompact(ledMac).c_str());
  delay(1500);
  refreshLcd(nowOk ? "ESP-NOW ready" : "ESP-NOW fail");
}

void loop() {
  char k = keypad.getKey();
  if (k) onKey(k);

  if (Serial.available()) {
    char c = Serial.read();
    if (c != '\r' && c != '\n') onKey(c);
  }
}
