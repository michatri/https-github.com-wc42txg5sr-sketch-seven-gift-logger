/*
 * ============================================================
 *  บอร์ด 2 : ESP32-S3 + LED P4 64x32 (HUB75)
 * ============================================================
 *
 * รับข้อความจากบอร์ด 1 ผ่าน ESP-NOW (WiFi MAC)
 * ตอนบูตโชว์ MAC ของบอร์ดนี้บนจอ ~8 วินาที
 * นำไปใส่ที่ ledMac[] ในโค้ดบอร์ด 1
 *
 * ไฟแผง LED: 5V ภายนอก ตั้งแต่ 3A ขึ้นไป + GND ร่วมกับ ESP32-S3
 * อย่าจ่ายไฟแผงจากขา 5V ของบอร์ด
 *
 * ไลบรารี:
 *   Adafruit GFX Library
 *   Adafruit BusIO
 *   ESP32 HUB75 LED MATRIX PANEL DMA Display  (mrfaptastic)
 *
 * บอร์ด Arduino IDE: ESP32S3 Dev Module
 * USB CDC On Boot = Enabled
 */

#include <WiFi.h>
#include <esp_now.h>
#include <esp_wifi.h>
#include <esp_idf_version.h>
#include <ESP32-HUB75-MatrixPanel-I2S-DMA.h>
#include <Fonts/FreeSansBold9pt7b.h>

#define MAX_CHARS        6
#define ESPNOW_CHANNEL   1
#define PANEL_W          64
#define PANEL_H          32
#define BRIGHTNESS       80   // 0-255 เริ่มต่ำไว้ก่อน
#define PANEL_FM6126A    0    // เปลี่ยนเป็น 1 ถ้าสีเพี้ยน / ภาพเบลอ

// สาย HUB75 -> ESP32-S3  (หลีกเลี่ยงขา USB 19/20 และ UART0 43/44)
#define R1_PIN  4
#define G1_PIN  5
#define B1_PIN  6
#define R2_PIN  7
#define G2_PIN  15
#define B2_PIN  16
#define A_PIN   18
#define B_PIN   8
#define C_PIN   9
#define D_PIN   10
#define E_PIN   -1     // แผง 32 แถวไม่ใช้ E
#define LAT_PIN 11
#define OE_PIN  12
#define CLK_PIN 13

MatrixPanel_I2S_DMA *matrix = nullptr;
char shown[MAX_CHARS + 1] = {0};
char myMacStr[18] = {0};
unsigned long showMacUntil = 0;
unsigned long lastBlink = 0;
bool blinkOn = true;
uint16_t cBg, cLine, cTitle, cText;

String macStr(const uint8_t *mac) {
  char s[18];
  sprintf(s, "%02X:%02X:%02X:%02X:%02X:%02X",
          mac[0], mac[1], mac[2], mac[3], mac[4], mac[5]);
  return String(s);
}

void draw() {
  if (!matrix) return;
  matrix->fillScreen(cBg);
  matrix->drawRect(0, 0, PANEL_W, PANEL_H, cLine);
  matrix->setTextWrap(false);

  if (millis() < showMacUntil) {
    matrix->setFont();
    matrix->setTextSize(1);
    matrix->setTextColor(cTitle);
    matrix->setCursor(4, 4);
    matrix->print("WiFi MAC");
    matrix->setTextColor(cText);
    matrix->setCursor(4, 14);
    matrix->print(myMacStr);
    matrix->setCursor(4, 23);
    matrix->print("ch ");
    matrix->print(ESPNOW_CHANNEL);
    return;
  }

  matrix->setFont();
  matrix->setTextSize(1);
  matrix->setTextColor(cTitle);
  matrix->setCursor(4, 2);
  matrix->print("P4 64x32");

  const char *msg = shown[0] ? shown : (blinkOn ? "_" : " ");
  matrix->setTextColor(cText);
  matrix->setFont(&FreeSansBold9pt7b);
  int16_t x1, y1;
  uint16_t w, h;
  matrix->getTextBounds(msg, 0, 0, &x1, &y1, &w, &h);
  if (w > PANEL_W - 6) {
    matrix->setFont();
    matrix->setTextSize(1);
    matrix->getTextBounds(msg, 0, 0, &x1, &y1, &w, &h);
    matrix->setCursor((PANEL_W - w) / 2, 14);
    matrix->print(msg);
    return;
  }
  int x = (PANEL_W - (int)w) / 2 - x1;
  if (x < 3) x = 3;
  matrix->setCursor(x, 24);
  matrix->print(msg);
}

void setText(const char *src) {
  memset(shown, 0, sizeof(shown));
  size_t n = 0;
  for (size_t i = 0; src[i] && n < MAX_CHARS; i++) {
    if (src[i] >= 32 && src[i] <= 126) shown[n++] = src[i];
  }
  showMacUntil = 0;
  Serial.print("DISPLAY [");
  Serial.print(shown);
  Serial.println("]");
  draw();
}

void applyPacket(const char *raw) {
  String s = String(raw);
  s.trim();
  if (s.length() == 0 || s.equalsIgnoreCase("CLR") || s.equalsIgnoreCase("CLEAR")) {
    shown[0] = 0;
    showMacUntil = 0;
    Serial.println("DISPLAY cleared");
    draw();
    return;
  }
  if (s.startsWith("SET:")) s = s.substring(4);
  setText(s.c_str());
}

void handleNow(const uint8_t *mac, const uint8_t *data, int len) {
  char buf[64];
  int n = (len < 63) ? len : 63;
  memcpy(buf, data, n);
  buf[n] = 0;
  Serial.print("from ");
  Serial.print(macStr(mac));
  Serial.print(" : ");
  Serial.println(buf);
  applyPacket(buf);
}

#if ESP_IDF_VERSION >= ESP_IDF_VERSION_VAL(5, 0, 0)
void onRecv(const esp_now_recv_info_t *info, const uint8_t *data, int len) {
  if (info && data && len > 0) handleNow(info->src_addr, data, len);
}
#else
void onRecv(const uint8_t *mac, const uint8_t *data, int len) {
  if (mac && data && len > 0) handleNow(mac, data, len);
}
#endif

void startNow() {
  WiFi.mode(WIFI_STA);
  WiFi.disconnect(true);
  delay(80);
  esp_wifi_set_promiscuous(true);
  esp_wifi_set_channel(ESPNOW_CHANNEL, WIFI_SECOND_CHAN_NONE);
  esp_wifi_set_promiscuous(false);

  uint8_t mac[6];
  WiFi.macAddress(mac);
  String m = macStr(mac);
  strncpy(myMacStr, m.c_str(), sizeof(myMacStr) - 1);

  Serial.println("BOARD 2 ESP32-S3 LED P4 64x32");
  Serial.print("This board MAC = ");
  Serial.println(myMacStr);
  Serial.println("Copy this MAC into ledMac[] on board 1");

  if (esp_now_init() != ESP_OK) {
    Serial.println("ESP-NOW init failed");
    return;
  }
  esp_now_register_recv_cb(onRecv);
}

void startPanel() {
  HUB75_I2S_CFG::i2s_pins pins = {
    R1_PIN, G1_PIN, B1_PIN, R2_PIN, G2_PIN, B2_PIN,
    A_PIN, B_PIN, C_PIN, D_PIN, E_PIN, LAT_PIN, OE_PIN, CLK_PIN
  };
  HUB75_I2S_CFG cfg(PANEL_W, PANEL_H, 1, pins);
  cfg.clkphase = false;
  cfg.latch_blanking = 1;
#if PANEL_FM6126A
  cfg.driver = HUB75_I2S_CFG::FM6126A;
#endif

  matrix = new MatrixPanel_I2S_DMA(cfg);
  matrix->begin();
  matrix->setBrightness8(BRIGHTNESS);
  matrix->clearScreen();
  cBg    = matrix->color565(0, 0, 20);
  cLine  = matrix->color565(0, 80, 180);
  cTitle = matrix->color565(120, 180, 255);
  cText  = matrix->color565(255, 220, 40);
  showMacUntil = millis() + 8000;
  draw();
}

void setup() {
  Serial.begin(115200);
  delay(300);
  startNow();
  startPanel();
}

void loop() {
  if (millis() - lastBlink > 500) {
    lastBlink = millis();
    blinkOn = !blinkOn;
    if (!shown[0]) draw();
  }
}
