#include <WiFi.h>
#include <esp_mac.h>
#include <esp_wifi.h>
#include <string.h>

void dump(const char *name, const uint8_t *m) {
  Serial.print(name);
  for (int i = 0; i < 6; i++) {
    if (i > 0) {
      Serial.print(":");
    }
    if (m[i] < 16) {
      Serial.print("0");
    }
    Serial.print(m[i], HEX);
  }
  Serial.println();
}

void setup() {
  Serial.begin(115200);
  delay(2000);
  Serial.println();
  Serial.println("MAC TEST V2");
  Serial.print("chip ");
  Serial.println(ESP.getChipModel());

  uint8_t mac[6];
  memset(mac, 0, 6);
  Serial.print("efuse err ");
  Serial.println((int)esp_efuse_mac_get_default(mac));
  dump("efuse ", mac);

  memset(mac, 0, 6);
  Serial.print("read_mac err ");
  Serial.println((int)esp_read_mac(mac, ESP_MAC_WIFI_STA));
  dump("read_mac ", mac);

#if defined(ESP_ARDUINO_VERSION_MAJOR) && (ESP_ARDUINO_VERSION_MAJOR >= 3)
  WiFi.STA.begin();
#else
  WiFi.mode(WIFI_STA);
#endif
  delay(800);

  Serial.print("WiFi.macAddress ");
  Serial.println(WiFi.macAddress());

  memset(mac, 0, 6);
  Serial.print("get_mac err ");
  Serial.println((int)esp_wifi_get_mac(WIFI_IF_STA, mac));
  dump("get_mac ", mac);
}

void loop() {
}
