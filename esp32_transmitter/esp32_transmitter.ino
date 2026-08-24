#include <Wire.h>
#include <LiquidCrystal_I2C.h>
#include <I2CKeyPad.h>
#include <WiFi.h>
#include <esp_now.h>
#include <esp_wifi.h>

// LCD backpack (PCF8574) + keypad expander (PCF8574) อยู่บน I2C เส้นเดียวกัน
LiquidCrystal_I2C lcd(0x27, 16, 2);
I2CKeyPad keyPad(0x20);

// แผนผังปุ่ม 3x4 บน PCF8574 โหมด 4x4 — คอลัมน์ที่ 4 เป็น N
char keymap[19] = "123N456N789N*0#NNN";

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

String inputString = "";
const int MAX_DIGITS = 5;

volatile bool sendPending = false;
volatile esp_now_send_status_t lastSendStatus = ESP_NOW_SEND_FAIL;
unsigned long statusUntilMs = 0;
uint8_t lastRawKey = 16;  // I2C_KEYPAD_NOKEY

#if defined(ESP_ARDUINO_VERSION_MAJOR) && ESP_ARDUINO_VERSION_MAJOR >= 3
void OnDataSent(const wifi_tx_info_t *info, esp_now_send_status_t status) {
  lastSendStatus = status;
  sendPending = false;
}
#else
void OnDataSent(const uint8_t *mac_addr, esp_now_send_status_t status) {
  lastSendStatus = status;
  sendPending = false;
}
#endif

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
  Serial.print(ok ? "Sent: " : "Send failed: ");
  Serial.println(text);
}

void sendClear() {
  char clearCmd[6] = "CLEAR";
  inputString = "";
  showPageLine();
  showStatus("Clearing LEDs...", 0);
  bool ok = sendToAll(reinterpret_cast<uint8_t *>(clearCmd), sizeof(clearCmd));
  showStatus(ok ? "Cleared" : "Clear Failed!", 1000);
  Serial.println(ok ? "Cleared" : "Clear failed");
}

void handleKey(char key) {
  if (key >= '0' && key <= '9') {
    if (inputString.length() < MAX_DIGITS) {
      inputString += key;
      showPageLine();
      sendText(inputString);
    }
  } else if (key == '*') {
    // ช่องว่าง — ส่งขึ้นจอใหญ่ตามข้อความปัจจุบัน
    if (inputString.length() < MAX_DIGITS) {
      inputString += ' ';
      showPageLine();
      sendText(inputString);
    }
  } else if (key == '#') {
    // เคลียร์จอ LED ทุกจอให้มืด
    sendClear();
  }
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
  WiFi.channel(1);
  esp_wifi_set_channel(1, WIFI_SECOND_CHAN_NONE);

  if (esp_now_init() != ESP_OK) {
    showStatus("ESP-NOW Error", 0);
    Serial.println("Error initializing ESP-NOW");
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
    esp_err_t addResult = esp_now_add_peer(&peerInfo);
    if (addResult != ESP_OK && addResult != ESP_ERR_ESPNOW_EXIST) {
      showStatus("Add Peer Fail", 0);
      Serial.println("Failed to add peer");
      return;
    }
  }

  if (!keyPad.begin()) {
    showStatus("Keypad Error", 0);
    Serial.println("หา PCF8574 keypad ไม่พบ!");
    while (1) {
      delay(1000);
    }
  }
  keyPad.loadKeyMap(keymap);
  Serial.println("Transmitter ready");
}

void loop() {
  refreshReadyIfIdle();

  uint8_t raw = keyPad.getKey();
  if (raw == lastRawKey) {
    return;
  }
  lastRawKey = raw;

  // 16 = ไม่มีปุ่ม, 17 = อ่านไม่สำเร็จ
  if (raw >= 16) {
    return;
  }

  char key = keymap[raw];
  if (key == 'N') {
    return;
  }

  handleKey(key);
}
