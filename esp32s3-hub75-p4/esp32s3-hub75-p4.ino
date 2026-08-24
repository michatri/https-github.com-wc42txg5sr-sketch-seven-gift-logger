#include <WiFi.h>
#include <esp_now.h>
#include <esp_wifi.h>
#include <ESP32-HUB75-MatrixPanel-I2S-DMA.h>

#define PANEL_W 64
#define PANEL_H 32

#define R1_PIN 4
#define G1_PIN 5
#define B1_PIN 6
#define R2_PIN 7
#define G2_PIN 15
#define B2_PIN 16
#define A_PIN 18
#define B_PIN 8
#define C_PIN 3
#define D_PIN 42
#define E_PIN -1
#define LAT_PIN 40
#define OE_PIN 2
#define CLK_PIN 41

MatrixPanel_I2S_DMA *panel = nullptr;
char shown[20];
char incoming[20];
volatile bool gotMsg = false;

void drawText(const char *text) {
  panel->fillScreen(0);
  if (text[0] == '\0') {
    return;
  }

  panel->setTextWrap(false);
  uint8_t size = 2;
  panel->setTextSize(size);

  int16_t x1 = 0;
  int16_t y1 = 0;
  uint16_t w = 0;
  uint16_t h = 0;
  panel->getTextBounds(text, 0, 0, &x1, &y1, &w, &h);
  if (w > PANEL_W - 2) {
    size = 1;
    panel->setTextSize(size);
    panel->getTextBounds(text, 0, 0, &x1, &y1, &w, &h);
  }

  int x = ((int)PANEL_W - (int)w) / 2;
  int y = ((int)PANEL_H - (int)h) / 2;
  if (x < 0) {
    x = 0;
  }
  if (y < 0) {
    y = 0;
  }

  panel->setCursor(x, y);
  panel->setTextColor(panel->color565(255, 160, 0));
  panel->print(text);
}

#if ESP_IDF_VERSION_MAJOR >= 5
void onRecv(const esp_now_recv_info_t *info, const uint8_t *data, int len) {
  (void)info;
#else
void onRecv(const uint8_t *mac, const uint8_t *data, int len) {
  (void)mac;
#endif
  if (len < 0) {
    return;
  }
  int n = len;
  if (n > 19) {
    n = 19;
  }
  memcpy(incoming, data, n);
  incoming[n] = '\0';
  gotMsg = true;
}

void setupPanel() {
  HUB75_I2S_CFG::i2s_pins pins = {
    R1_PIN, G1_PIN, B1_PIN,
    R2_PIN, G2_PIN, B2_PIN,
    A_PIN, B_PIN, C_PIN, D_PIN, E_PIN,
    LAT_PIN, OE_PIN, CLK_PIN
  };
  HUB75_I2S_CFG cfg(PANEL_W, PANEL_H, 1, pins);
  cfg.clkphase = false;
  panel = new MatrixPanel_I2S_DMA(cfg);
  panel->begin();
  panel->setBrightness8(80);
  panel->clearScreen();
}

void setupEspNow() {
  WiFi.mode(WIFI_AP_STA);
  WiFi.softAP("ESP-HUB75", NULL, 1);
  esp_wifi_set_channel(1, WIFI_SECOND_CHAN_NONE);
  Serial.print("WiFi name ");
  Serial.println("ESP-HUB75");
  Serial.print("MAC ");
  Serial.println(WiFi.macAddress());
  if (esp_now_init() != ESP_OK) {
    Serial.println("ESP-NOW fail");
    return;
  }
  esp_now_register_recv_cb(onRecv);
  Serial.println("HUB75 wait keypad");
}

void setup() {
  Serial.begin(115200);
  delay(300);
  Serial.println("ESP32-S3 P4 64x32");
  shown[0] = '\0';
  incoming[0] = '\0';
  setupPanel();
  setupEspNow();
  drawText("ESP-HUB75");
}

void loop() {
  if (!gotMsg) {
    return;
  }
  gotMsg = false;
  strncpy(shown, incoming, 19);
  shown[19] = '\0';
  Serial.print("SHOW ");
  Serial.println(shown);
  drawText(shown);
}
