/*
 * Board 2: ESP32-S3 + LED P4 64x32 HUB75
 *
 * WiFi AP ESP32-LED-P4 / 12345678
 * UDP 4210, HTTP http://192.168.4.1/ , BLE name ESP32S3-LED
 * Edit HUB75 pins in config.h if you use a different adapter.
 */

#include <Arduino.h>
#include <WiFi.h>
#include <WiFiUdp.h>
#include <WebServer.h>
#include <BLEDevice.h>
#include <BLEServer.h>
#include <BLEUtils.h>
#include <BLE2902.h>
#include <ESP32-HUB75-MatrixPanel-I2S-DMA.h>
#include <Fonts/FreeSansBold9pt7b.h>
#include "config.h"

MatrixPanel_I2S_DMA *display = nullptr;
WiFiUDP udp;
WebServer server(80);
BLECharacteristic *bleTx = nullptr;

char currentText[MAX_MESSAGE_LEN + 1] = {0};
bool bleClientConnected = false;
unsigned long lastBlinkMs = 0;
bool cursorOn = true;
uint16_t colorBg;
uint16_t colorBorder;
uint16_t colorTitle;
uint16_t colorText;

class LedBleCallbacks : public BLEServerCallbacks {
    void onConnect(BLEServer *bleServer) override {
        bleClientConnected = true;
        Serial.println("BLE client connected");
    }
    void onDisconnect(BLEServer *bleServer) override {
        bleClientConnected = false;
        Serial.println("BLE client disconnected");
        bleServer->startAdvertising();
    }
};

class LedBleRxCallbacks : public BLECharacteristicCallbacks {
    void onWrite(BLECharacteristic *characteristic) override;
};

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

    display->setFont();
    display->setTextSize(1);
    display->setTextWrap(false);
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
    Serial.printf("DISPLAY [%s]\n", currentText);
    drawScreen();
}

static void clearText() {
    currentText[0] = '\0';
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

void LedBleRxCallbacks::onWrite(BLECharacteristic *characteristic) {
    String value(characteristic->getValue().c_str());
    if (value.length() > 0) {
        applyPayload(value.c_str());
        if (bleTx) {
            bleTx->setValue(currentText);
            bleTx->notify();
        }
    }
}

static void pollUdp() {
    int size = udp.parsePacket();
    if (size <= 0) {
        return;
    }
    char buf[64];
    int len = udp.read(buf, sizeof(buf) - 1);
    if (len <= 0) {
        return;
    }
    buf[len] = '\0';
    Serial.printf("UDP from %s: %s\n", udp.remoteIP().toString().c_str(), buf);
    applyPayload(buf);
}

static String htmlPage() {
    String page;
    page.reserve(900);
    page += F("<!DOCTYPE html><html><head><meta charset='utf-8'>"
              "<meta name='viewport' content='width=device-width,initial-scale=1'>"
              "<title>LED P4</title>"
              "<style>body{font-family:sans-serif;background:#111;color:#eee;text-align:center;padding:24px}"
              "input{font-size:28px;letter-spacing:8px;text-align:center;width:220px;padding:8px}"
              "button{font-size:18px;margin:8px;padding:10px 16px}</style></head><body>");
    page += F("<h2>ESP32-S3 LED P4 64x32</h2><p>Now: <b>");
    page += currentText[0] ? currentText : "(empty)";
    page += F("</b></p><form action='/set' method='GET'>"
              "<p><input name='text' maxlength='6' value='");
    page += currentText;
    page += F("' autofocus></p>"
              "<button type='submit'>Show</button>"
              "<button type='submit' formaction='/clear'>Clear</button>"
              "</form><p>WiFi: ");
    page += WIFI_AP_SSID;
    page += F(" / UDP ");
    page += String(WIFI_UDP_PORT);
    page += F("</p></body></html>");
    return page;
}

static void handleRoot() {
    server.send(200, "text/html", htmlPage());
}

static void handleSet() {
    if (server.hasArg("text")) {
        applyPayload(server.arg("text").c_str());
    }
    server.sendHeader("Location", "/");
    server.send(303);
}

static void handleClear() {
    applyPayload("CLR");
    server.sendHeader("Location", "/");
    server.send(303);
}

static void startWifiAp() {
    WiFi.mode(WIFI_AP);
    WiFi.softAP(WIFI_AP_SSID, WIFI_AP_PASSWORD);
    delay(150);
    IPAddress ip = WiFi.softAPIP();
    Serial.printf("WiFi AP %s  IP %s\n", WIFI_AP_SSID, ip.toString().c_str());
    udp.begin(WIFI_UDP_PORT);
    Serial.printf("UDP listen %d\n", WIFI_UDP_PORT);
}

static void startHttp() {
    server.on("/", handleRoot);
    server.on("/set", handleSet);
    server.on("/clear", handleClear);
    server.begin();
    Serial.println("HTTP http://192.168.4.1/");
}

static void startBle() {
    BLEDevice::init(BLE_DEVICE_NAME);
    BLEServer *serverBle = BLEDevice::createServer();
    serverBle->setCallbacks(new LedBleCallbacks());

    BLEService *service = serverBle->createService(BLE_NUS_SERVICE_UUID);
    BLECharacteristic *bleRx = service->createCharacteristic(
        BLE_NUS_CHARACTERISTIC_RX_UUID,
        BLECharacteristic::PROPERTY_WRITE | BLECharacteristic::PROPERTY_WRITE_NR);
    bleRx->setCallbacks(new LedBleRxCallbacks());

    bleTx = service->createCharacteristic(
        BLE_NUS_CHARACTERISTIC_TX_UUID,
        BLECharacteristic::PROPERTY_NOTIFY | BLECharacteristic::PROPERTY_READ);
    bleTx->addDescriptor(new BLE2902());

    service->start();
    BLEAdvertising *advertising = BLEDevice::getAdvertising();
    advertising->addServiceUUID(BLE_NUS_SERVICE_UUID);
    advertising->setScanResponse(true);
    advertising->start();
    Serial.printf("BLE advertising as %s\n", BLE_DEVICE_NAME);
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
    drawScreen();
}

void setup() {
    Serial.begin(115200);
    delay(300);
    Serial.println();
    Serial.println("ESP32-S3 LED P4 64x32");

    startPanel();
#if ENABLE_WIFI_AP
    startWifiAp();
#endif
#if ENABLE_HTTP
    startHttp();
#endif
#if ENABLE_BLE
    startBle();
#endif
}

void loop() {
    pollUdp();
#if ENABLE_HTTP
    server.handleClient();
#endif
    if (millis() - lastBlinkMs > 500) {
        lastBlinkMs = millis();
        cursorOn = !cursorOn;
        if (currentText[0] == '\0') {
            drawScreen();
        }
    }
}
