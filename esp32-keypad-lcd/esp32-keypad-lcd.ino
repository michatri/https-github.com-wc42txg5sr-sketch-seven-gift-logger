/*
 * Board 1: ESP32 + keypad 3x4 + LCD 16x2 I2C
 *
 * rowPins = {4, 12, 14, 5}
 * colPins = {26, 25, 33}
 * * = space, # = clear, max 6 characters
 * LCD I2C SDA=21 SCL=22
 * Sends SET:/CLR over WiFi UDP and BLE to the ESP32-S3 LED board
 */

#include <Arduino.h>
#include <WiFi.h>
#include <WiFiUdp.h>
#include <Wire.h>
#include <Keypad.h>
#include <LiquidCrystal_I2C.h>
#include <BLEDevice.h>
#include <BLEUtils.h>
#include <BLEScan.h>
#include <BLEAdvertisedDevice.h>
#include "config.h"

static_assert(KEYPAD_ROWS == 4 && KEYPAD_COLS == 3, "This sketch is for a 3x4 keypad");

const char KEYS[KEYPAD_ROWS][KEYPAD_COLS] = {
    {'1', '2', '3'},
    {'4', '5', '6'},
    {'7', '8', '9'},
    {'*', '0', '#'}
};

byte rowPins[KEYPAD_ROWS] = KEYPAD_ROW_PINS;
byte colPins[KEYPAD_COLS] = KEYPAD_COL_PINS;

Keypad keypad = Keypad(makeKeymap(KEYS), rowPins, colPins, KEYPAD_ROWS, KEYPAD_COLS);
LiquidCrystal_I2C *lcd = nullptr;
WiFiUDP udp;

char message[MAX_MESSAGE_LEN + 1] = {0};
uint8_t messageLen = 0;
bool lcdReady = false;
bool wifiReady = false;
String statusLine = "boot...";
unsigned long lastStatusMs = 0;
unsigned long lastWifiAttemptMs = 0;

static BLEUUID kServiceUUID(BLE_NUS_SERVICE_UUID);
static BLEUUID kRxUUID(BLE_NUS_CHARACTERISTIC_RX_UUID);
static BLEClient *bleClient = nullptr;
static BLERemoteCharacteristic *bleRx = nullptr;
static BLEAdvertisedDevice *bleTarget = nullptr;
static bool bleDoConnect = false;
static bool bleConnected = false;
static bool bleScanning = false;
static unsigned long lastBleScanMs = 0;

static void bleScanDone(BLEScanResults results) {
    (void)results;
    bleScanning = false;
    lastBleScanMs = millis();
}

class KeypadBleClientCallbacks : public BLEClientCallbacks {
    void onConnect(BLEClient *client) override {
        bleConnected = true;
        Serial.println("BLE connected to LED board");
    }
    void onDisconnect(BLEClient *client) override {
        bleConnected = false;
        bleRx = nullptr;
        Serial.println("BLE disconnected");
    }
};

class KeypadBleScanCallbacks : public BLEAdvertisedDeviceCallbacks {
    void onResult(BLEAdvertisedDevice advertisedDevice) override {
        bool nameMatch = advertisedDevice.getName() == BLE_DEVICE_NAME;
        bool uuidMatch = advertisedDevice.haveServiceUUID() && advertisedDevice.isAdvertisingService(kServiceUUID);
        if (!nameMatch && !uuidMatch) {
            return;
        }
        BLEDevice::getScan()->stop();
        bleScanning = false;
        delete bleTarget;
        bleTarget = new BLEAdvertisedDevice(advertisedDevice);
        bleDoConnect = true;
    }
};

static uint8_t scanLcdAddress() {
    const uint8_t preferred[] = {LCD_ADDR, LCD_ADDR_ALT};
    for (uint8_t addr : preferred) {
        Wire.beginTransmission(addr);
        if (Wire.endTransmission() == 0) {
            return addr;
        }
    }
    for (uint8_t addr = 0x20; addr <= 0x3F; addr++) {
        Wire.beginTransmission(addr);
        if (Wire.endTransmission() == 0) {
            return addr;
        }
    }
    return 0;
}

static void refreshLcd() {
    if (!lcdReady || !lcd) {
        return;
    }
    lcd->setCursor(0, 0);
    lcd->print('>');
    for (uint8_t i = 0; i < MAX_MESSAGE_LEN; i++) {
        lcd->print(i < messageLen ? message[i] : '_');
    }
    lcd->print("         ");

    String line2 = statusLine;
    if (line2.length() > LCD_COLS) {
        line2 = line2.substring(0, LCD_COLS);
    }
    while (line2.length() < LCD_COLS) {
        line2 += ' ';
    }
    lcd->setCursor(0, 1);
    lcd->print(line2);
}

static void setStatus(const String &text) {
    statusLine = text;
    refreshLcd();
    Serial.println(text);
}

static bool connectBleServer() {
    if (!bleTarget) {
        return false;
    }
    if (!bleClient) {
        bleClient = BLEDevice::createClient();
        bleClient->setClientCallbacks(new KeypadBleClientCallbacks());
    }
    if (!bleClient->connect(bleTarget)) {
        Serial.println("BLE connect failed");
        return false;
    }
    BLERemoteService *service = bleClient->getService(kServiceUUID);
    if (!service) {
        bleClient->disconnect();
        return false;
    }
    bleRx = service->getCharacteristic(kRxUUID);
    if (!bleRx || !bleRx->canWrite()) {
        bleClient->disconnect();
        bleRx = nullptr;
        return false;
    }
    bleConnected = true;
    return true;
}

static void bleBegin() {
    BLEDevice::init("ESP32-Keypad");
    BLEScan *scan = BLEDevice::getScan();
    scan->setAdvertisedDeviceCallbacks(new KeypadBleScanCallbacks());
    scan->setActiveScan(true);
    scan->setInterval(320);
    scan->setWindow(160);
    bleScanning = true;
    scan->start(3, bleScanDone, false);
    lastBleScanMs = millis();
}

static void blePoll() {
    if (bleDoConnect) {
        bleDoConnect = false;
        if (connectBleServer()) {
            setStatus("BLE+WiFi ready");
            message[messageLen] = '\0';
            // resend current buffer after link-up
            char packet[32];
            if (messageLen == 0) {
                snprintf(packet, sizeof(packet), "CLR");
            } else {
                snprintf(packet, sizeof(packet), "SET:%s", message);
            }
            bleRx->writeValue(reinterpret_cast<uint8_t *>(packet), strlen(packet), false);
        } else {
            setStatus("BLE retry");
        }
    }

    if (!bleConnected && !bleScanning && millis() - lastBleScanMs > 6000) {
        lastBleScanMs = millis();
        bleScanning = true;
        BLEDevice::getScan()->start(3, bleScanDone, false);
    }
}

static void sendToLedBoard(const char *text) {
    char packet[32];
    if (text[0] == '\0') {
        snprintf(packet, sizeof(packet), "CLR");
    } else {
        snprintf(packet, sizeof(packet), "SET:%s", text);
    }
    Serial.printf("TX %s\n", packet);

#if ENABLE_WIFI
    if (wifiReady) {
        IPAddress dest(LED_BOARD_IP_OCTET1, LED_BOARD_IP_OCTET2, LED_BOARD_IP_OCTET3, LED_BOARD_IP_OCTET4);
        udp.beginPacket(dest, WIFI_UDP_PORT);
        udp.write(reinterpret_cast<const uint8_t *>(packet), strlen(packet));
        udp.endPacket();
    }
#endif

    if (bleConnected && bleRx) {
        bleRx->writeValue(reinterpret_cast<uint8_t *>(packet), strlen(packet), false);
    }
}

static void applyMessage() {
    message[messageLen] = '\0';
    refreshLcd();
    sendToLedBoard(message);
}

static void clearMessage() {
    memset(message, 0, sizeof(message));
    messageLen = 0;
    setStatus("# cleared");
    sendToLedBoard("");
    refreshLcd();
}

static void handleKey(char key) {
    if (key == '#') {
        clearMessage();
        return;
    }

    if (key != '*' && (key < '0' || key > '9') && key != ' ') {
        return;
    }

    if (messageLen >= MAX_MESSAGE_LEN) {
        setStatus("full 6, # clear");
        return;
    }

    char ch = (key == '*') ? ' ' : key;
    message[messageLen++] = ch;
    message[messageLen] = '\0';

    if (messageLen >= MAX_MESSAGE_LEN) {
        setStatus("sent 6 chars");
    } else if (key == '*') {
        setStatus("* space");
    } else {
        char buf[17];
        snprintf(buf, sizeof(buf), "typed %d/6", messageLen);
        setStatus(buf);
    }
    applyMessage();
}

static void pollWifi() {
#if ENABLE_WIFI
    if (WiFi.status() == WL_CONNECTED) {
        if (!wifiReady) {
            wifiReady = true;
            udp.begin(WIFI_UDP_PORT);
            setStatus("WiFi OK");
            applyMessage();
        }
        return;
    }

    wifiReady = false;
    if (millis() - lastWifiAttemptMs < 5000) {
        return;
    }
    lastWifiAttemptMs = millis();
    WiFi.mode(WIFI_STA);
    WiFi.begin(WIFI_AP_SSID, WIFI_AP_PASSWORD);
    setStatus("WiFi joining...");
#endif
}

void setup() {
    Serial.begin(115200);
    delay(200);
    Serial.println();
    Serial.println("ESP32 keypad + LCD 16x2");

    Wire.begin(LCD_SDA_PIN, LCD_SCL_PIN);
    delay(50);
    uint8_t lcdAddress = scanLcdAddress();
    if (lcdAddress == 0) {
        Serial.println("LCD I2C not found. Check SDA=21 SCL=22 VCC GND.");
    } else {
        Serial.printf("LCD I2C address 0x%02X\n", lcdAddress);
        lcd = new LiquidCrystal_I2C(lcdAddress, LCD_COLS, LCD_ROWS);
        lcd->init();
        lcd->backlight();
        lcd->clear();
        lcdReady = true;
        lcd->setCursor(0, 0);
        lcd->print("ESP32 Keypad");
        lcd->setCursor(0, 1);
        lcd->print("LCD OK");
        delay(400);
    }

    keypad.setDebounceTime(40);
    keypad.setHoldTime(400);
    setStatus("* space  # clr");
    refreshLcd();

    WiFi.mode(WIFI_STA);
    WiFi.begin(WIFI_AP_SSID, WIFI_AP_PASSWORD);
    lastWifiAttemptMs = millis();
    bleBegin();
}

void loop() {
    char key = keypad.getKey();
    if (key) {
        Serial.printf("KEY %c\n", key);
        handleKey(key);
    }

    if (Serial.available()) {
        char incoming = Serial.read();
        if (incoming != '\r' && incoming != '\n') {
            handleKey(incoming);
        }
    }

    pollWifi();
    blePoll();

    if (millis() - lastStatusMs > 2500) {
        lastStatusMs = millis();
        if (!wifiReady && !bleConnected) {
            setStatus("wait LED board");
        } else if (!wifiReady) {
            setStatus("BLE only");
        } else if (!bleConnected) {
            setStatus("WiFi only");
        }
    }
}
