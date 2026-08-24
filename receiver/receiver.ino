#include <Adafruit_Protomatter.h>
#include <esp_now.h>
#include <WiFi.h>
#include <esp_wifi.h>

uint8_t rgbPins[] = {42, 41, 40, 39, 38, 37};
uint8_t addrPins[] = {48, 36, 45, 35};
uint8_t clockPin = 2;
uint8_t latchPin = 47;
uint8_t oePin = 14;

Adafruit_Protomatter matrix(
  64, 4, 1, rgbPins, 4, addrPins, clockPin, latchPin, oePin, false
);

char pendingText[32];
volatile bool dataReady = false;

void updateDisplay(const char *text) {
  matrix.fillScreen(matrix.color565(0, 0, 0));

  if (strcmp(text, "CLEAR") == 0) {
    matrix.show();
    return;
  }

  matrix.setTextSize(2);
  int textWidth = strlen(text) * 11;
  int cursorX = (64 - textWidth) / 2;
  if (cursorX < 2) {
    cursorX = 2;
  }

  matrix.setCursor(cursorX, 9);
  matrix.setTextColor(matrix.color565(0, 0, 255));
  matrix.print(text);
  matrix.show();
}

void OnDataRecv(const esp_now_recv_info *recvInfo, const uint8_t *incomingData, int len) {
  char buffer[32];
  memset(buffer, 0, sizeof(buffer));

  int bytesToCopy = (len < (int)sizeof(buffer) - 1) ? len : (int)sizeof(buffer) - 1;
  memcpy(buffer, incomingData, bytesToCopy);
  buffer[bytesToCopy] = '\0';

  memcpy(pendingText, buffer, sizeof(pendingText));
  dataReady = true;
}

void setup(void) {
  Serial.begin(115200);
  delay(1000);

  memset(pendingText, 0, sizeof(pendingText));
  strncpy(pendingText, "---", sizeof(pendingText) - 1);

  ProtomatterStatus status = matrix.begin();
  if (status != PROTOMATTER_OK) {
    for (;;) {
    }
  }

  updateDisplay(pendingText);

  WiFi.mode(WIFI_STA);
  WiFi.disconnect();
  esp_wifi_set_channel(1, WIFI_SECOND_CHAN_NONE);

  if (esp_now_init() != ESP_OK) {
    return;
  }

  esp_now_register_recv_cb(OnDataRecv);
}

void loop(void) {
  if (dataReady) {
    dataReady = false;

    char text[32];
    memcpy(text, pendingText, sizeof(text));
    text[sizeof(text) - 1] = '\0';

    Serial.print("Received Data: [");
    Serial.print(text);
    Serial.println("]");

    updateDisplay(text);
  }

  delay(10);
}
