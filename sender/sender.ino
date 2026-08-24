#include <Wire.h>
#include <esp_now.h>
#include <WiFi.h>
#include <esp_wifi.h>
#include <LiquidCrystal_I2C.h>
#include <Keypad.h>

// MAC ของจอรับ — เปิด display3 เมื่อต่อจอที่ 3
uint8_t display1[] = {0x90, 0x70, 0x69, 0x98, 0xAD, 0xAC};
uint8_t display2[] = {0x90, 0x70, 0x69, 0x98, 0xA7, 0xEC};
// uint8_t display3[] = {0x90, 0x70, 0x69, 0x98, 0xCF, 0xCC};

uint8_t *peers[] = {
  display1,
  display2,
  // display3,
};
const int peerCount = sizeof(peers) / sizeof(peers[0]);

LiquidCrystal_I2C lcd(0x27, 16, 2);

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
String inputString = "";

volatile bool sendPending = false;
volatile esp_now_send_status_t lastSendStatus = ESP_NOW_SEND_FAIL;
unsigned long statusUntilMs = 0;

void OnDataSent(const wifi_tx_info_t *txInfo, esp_now_send_status_t status) {
  lastSendStatus = status;
  sendPending = false;
}

void showPageLine() {
  lcd.setCursor(0, 0);
  lcd.print("Page Num:       ");
  lcd.setCursor(10, 0);
  lcd.print(inputString);
}

void showStatus(const char *msg, unsigned long holdMs) {
  lcd.setCursor(0, 1);
  lcd.print("                ");
  lcd.setCursor(0, 1);
  lcd.print(msg);
  statusUntilMs = (holdMs == 0) ? 0 : (millis() + holdMs);
}

void refreshReadyIfIdle() {
  if (statusUntilMs != 0 && millis() >= statusUntilMs) {
    statusUntilMs = 0;
    showPageLine();
    showStatus("Ready...", 0);
  }
}

bool sendToAll(const uint8_t *data, size_t len) {
  bool allOk = true;

  for (int i = 0; i < peerCount; i++) {
    sendPending = true;
    lastSendStatus = ESP_NOW_SEND_FAIL;

    if (esp_now_send(peers[i], data, len) != ESP_OK) {
      allOk = false;
      sendPending = false;
      continue;
    }

    unsigned long start = millis();
    while (sendPending && (millis() - start < 80)) {
      delay(1);
    }

    if (sendPending || lastSendStatus != ESP_NOW_SEND_SUCCESS) {
      allOk = false;
    }
  }

  return allOk;
}

void sendText(const String &text) {
  char sendData[6];
  memset(sendData, 0, sizeof(sendData));
  text.toCharArray(sendData, sizeof(sendData));

  showStatus("Sending...", 0);
  bool ok = sendToAll(reinterpret_cast<uint8_t *>(sendData), sizeof(sendData));
  showStatus(ok ? "Sent" : "Sent Failed!", 1000);
}

void sendClear() {
  char clearCmd[6] = "CLEAR";
  inputString = "";
  showPageLine();
  showStatus("Clearing LEDs...", 0);

  bool ok = sendToAll(reinterpret_cast<uint8_t *>(clearCmd), sizeof(clearCmd));
  showStatus(ok ? "Cleared" : "Clear Failed!", 1000);
}

void setup() {
  Serial.begin(115200);
  delay(1000);

  Wire.begin(21, 22);
  lcd.init();
  lcd.backlight();
  showPageLine();
  showStatus("Ready...", 0);

  WiFi.mode(WIFI_STA);
  WiFi.setTxPower(WIFI_POWER_19_5dBm);
  esp_wifi_set_channel(1, WIFI_SECOND_CHAN_NONE);

  if (esp_now_init() != ESP_OK) {
    showStatus("ESP-NOW Error", 0);
    return;
  }

  esp_now_register_send_cb(OnDataSent);

  esp_now_peer_info_t peerInfo;
  memset(&peerInfo, 0, sizeof(peerInfo));
  peerInfo.channel = 1;
  peerInfo.encrypt = false;
  peerInfo.ifidx = WIFI_IF_STA;

  for (int i = 0; i < peerCount; i++) {
    memcpy(peerInfo.peer_addr, peers[i], 6);
    if (esp_now_add_peer(&peerInfo) != ESP_OK) {
      showStatus("Add Peer Fail", 0);
      return;
    }
  }
}

void loop() {
  refreshReadyIfIdle();

  char key = keypad.getKey();
  if (!key) {
    return;
  }

  if (key >= '0' && key <= '9') {
    if (inputString.length() < 5) {
      inputString += key;
      showPageLine();
      sendText(inputString);
    }
  } else if (key == '*') {
    // ช่องว่าง — ส่งขึ้นจอใหญ่ตามข้อความปัจจุบัน
    if (inputString.length() < 5) {
      inputString += ' ';
      showPageLine();
      sendText(inputString);
    }
  } else if (key == '#') {
    // เคลียร์จอ LED ทุกจอให้มืด
    sendClear();
  }
}
