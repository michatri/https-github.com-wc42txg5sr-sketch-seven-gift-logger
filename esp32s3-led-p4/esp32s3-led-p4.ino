/*
 * Board 2: ESP32-S3 + LED P4 64x32 HUB75
 *
 * Receives SET:/CLR over ESP-NOW (WiFi MAC) from the keypad ESP32.
 * On boot the panel shows this board's WiFi MAC so you can copy it
 * into protocol.h as LED_BOARD_MAC.
 */

#include <Arduino.h>
#include <WiFi.h>
#include <esp_now.h>
#include <esp_wifi.h>
#include <esp_idf_version.h>
#include <ESP32-HUB75-MatrixPanel-I2S-DMA.h>
#include <Fonts/FreeSansBold9pt7b.h>
#include "config.h"

MatrixPanel_I2S_DMA *display = nullptr;

char currentText[MAX_MESSAGE_LEN + 1] = {0};
char bootMac[18] = {0};
unsigned long lastBlinkMs = 0;
unsigned long bootMacUntilMs = 0;
bool cursorOn = true;
uint16_t colorBg;
uint16_t colorBorder;
uint16_t colorTitle;
uint16_t colorText;

static String macToString(const uint8_t *mac) {
    char buf[18];
    snprintf(buf, sizeof(buf), "%02X:%02X:%02X:%02X:%02X:%02X",
             mac[0], mac[1], mac[2], mac[3], mac[4], mac[5]);
    return String(buf);
}

static void sanitizeText(const char *input, char *output) {
    size_t n = 0;
    for (size_t i = 0; input[i] != '\0' && n < MAX_MESSAGE_LEN; i++) {
        char c = input[i];
        if (c == '\r' || c == '\n') {
            break;
        }
        if (c >= 32 && c <= 126) {
            output[n++] = c;
        }
    }
    output[n] = '\0';
}

static void drawScreen() {
    if (!display) {
        return;
    }

    display->fillScreen(colorBg);
    display->drawRect(0, 0, PANEL_WIDTH, PANEL_HEIGHT, colorBorder);
    display->drawRect(1, 1, PANEL_WIDTH - 2, PANEL_HEIGHT - 2, colorBorder);
    display->setTextWrap(false);

    if (millis() < bootMacUntilMs) {
        display->setFont();
        display->setTextSize(1);
        display->setTextColor(colorTitle);
        display->setCursor(4, 4);
        display->print("WiFi MAC");
        display->setTextColor(colorText);
        display->setCursor(4, 14);
        display->print(bootMac);
        display->setCursor(4, 23);
        display->print("ch ");
        display->print(ESPNOW_WIFI_CHANNEL);
        return;
    }

    display->setFont();
    display->setTextSize(1);
    display->setTextColor(colorTitle);
    display->setCursor(4, 2);
    display->print("P4 64x32");

    const char *text = currentText[0] ? currentText : (cursorOn ? "_" : " ");
    display->setTextColor(colorText);
    display->setFont(&FreeSansBold9pt7b);

    int16_t x1, y1;
    uint16_t w, h;
    display->getTextBounds(text, 0, 0, &x1, &y1, &w, &h);
    if (w > PANEL_WIDTH - 6) {
        display->setFont();
        display->setTextSize(1);
        display->getTextBounds(text, 0, 0, &x1, &y1, &w, &h);
        int x = (PANEL_WIDTH - (int)w) / 2;
        display->setCursor(x, 14);
        display->print(text);
        return;
    }
    int x = (PANEL_WIDTH - (int)w) / 2 - x1;
    if (x < 3) {
        x = 3;
    }
    display->setCursor(x, 24);
    display->print(text);
}

static void showText(const char *text) {
    sanitizeText(text, currentText);
    bootMacUntilMs = 0;
    Serial.printf("DISPLAY [%s]\n", currentText);
    drawScreen();
}

static void clearText() {
    currentText[0] = '\0';
    bootMacUntilMs = 0;
    Serial.println("DISPLAY cleared");
    drawScreen();
}

static void applyPayload(const char *raw) {
    String payload = String(raw);
    payload.trim();
    if (payload.length() == 0 || payload.equalsIgnoreCase("CLR") || payload.equalsIgnoreCase("CLEAR")) {
        clearText();
        return;
    }
    if (payload.startsWith("SET:")) {
        showText(payload.substring(4).c_str());
        return;
    }
    showText(payload.c_str());
}

static void handleNowPacket(const uint8_t *mac, const uint8_t *data, int len) {
    char buf[64];
    int n = len;
    if (n > (int)sizeof(buf) - 1) {
        n = sizeof(buf) - 1;
    }
    memcpy(buf, data, n);
    buf[n] = '\0';
    Serial.printf("ESP-NOW from %s: %s\n", macToString(mac).c_str(), buf);
    applyPayload(buf);
}

#if ESP_IDF_VERSION >= ESP_IDF_VERSION_VAL(5, 0, 0)
void onNowRecv(const esp_now_recv_info_t *info, const uint8_t *data, int len) {
    if (!info || !data || len <= 0) {
        return;
    }
    handleNowPacket(info->src_addr, data, len);
}
#else
void onNowRecv(const uint8_t *mac, const uint8_t *data, int len) {
    if (!mac || !data || len <= 0) {
        return;
    }
    handleNowPacket(mac, data, len);
}
#endif

static void startEspNow() {
    WiFi.mode(WIFI_STA);
    WiFi.disconnect(true);
    delay(80);
    esp_wifi_set_promiscuous(true);
    esp_wifi_set_channel(ESPNOW_WIFI_CHANNEL, WIFI_SECOND_CHAN_NONE);
    esp_wifi_set_promiscuous(false);

    uint8_t myMac[6];
    WiFi.macAddress(myMac);
    String mac = macToString(myMac);
    strncpy(bootMac, mac.c_str(), sizeof(bootMac) - 1);
    Serial.println("ESP32-S3 LED P4 64x32  (ESP-NOW / WiFi MAC)");
    Serial.printf("This board MAC: %s\n", bootMac);
    Serial.printf("Copy into keypad protocol.h as LED_BOARD_MAC\n");
    Serial.printf("ESP-NOW channel %d\n", ESPNOW_WIFI_CHANNEL);

    if (esp_now_init() != ESP_OK) {
        Serial.println("ESP-NOW init failed");
        return;
    }
    esp_now_register_recv_cb(onNowRecv);
}

static void startPanel() {
    HUB75_I2S_CFG::i2s_pins pins = {
        HUB75_R1, HUB75_G1, HUB75_B1,
        HUB75_R2, HUB75_G2, HUB75_B2,
        HUB75_A, HUB75_B, HUB75_C, HUB75_D, HUB75_E,
        HUB75_LAT, HUB75_OE, HUB75_CLK
    };

    HUB75_I2S_CFG mxconfig(PANEL_WIDTH, PANEL_HEIGHT, PANEL_CHAIN, pins);
    mxconfig.clkphase = false;
    mxconfig.latch_blanking = 1;
#if PANEL_FM6126A
    mxconfig.driver = HUB75_I2S_CFG::FM6126A;
#endif

    display = new MatrixPanel_I2S_DMA(mxconfig);
    display->begin();
    display->setBrightness8(PANEL_BRIGHTNESS);
    display->clearScreen();

    colorBg = display->color565(0, 0, 20);
    colorBorder = display->color565(0, 80, 180);
    colorTitle = display->color565(120, 180, 255);
    colorText = display->color565(255, 220, 40);
    bootMacUntilMs = millis() + 8000;
    drawScreen();
}

void setup() {
    Serial.begin(115200);
    delay(300);
    startEspNow();
    startPanel();
}

void loop() {
    if (millis() - lastBlinkMs > 500) {
        lastBlinkMs = millis();
        cursorOn = !cursorOn;
        if (currentText[0] == '\0') {
            drawScreen();
        }
    }
}
