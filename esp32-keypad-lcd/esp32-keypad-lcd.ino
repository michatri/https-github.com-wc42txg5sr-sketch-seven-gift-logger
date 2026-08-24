/*
 * Board 1: ESP32 + keypad 3x4 + LCD 16x2 I2C
 *
 * rowPins = {4, 12, 14, 5}
 * colPins = {26, 25, 33}
 * * = space, # = clear, max 6 characters
 * LCD I2C SDA=21 SCL=22
 * Sends SET:/CLR to the ESP32-S3 over ESP-NOW (WiFi MAC)
 */

#include <Arduino.h>
#include <WiFi.h>
#include <esp_now.h>
#include <esp_wifi.h>
#include <esp_idf_version.h>
#include <Wire.h>
#include <Keypad.h>
#include <LiquidCrystal_I2C.h>
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

char message[MAX_MESSAGE_LEN + 1] = {0};
uint8_t messageLen = 0;
bool lcdReady = false;
bool nowReady = false;
volatile bool lastSendOk = false;
String statusLine = "boot...";

static uint8_t ledMac[6] = {LED_BOARD_MAC};

static String macToString(const uint8_t *mac) {
    char buf[18];
    snprintf(buf, sizeof(buf), "%02X:%02X:%02X:%02X:%02X:%02X",
             mac[0], mac[1], mac[2], mac[3], mac[4], mac[5]);
    return String(buf);
}

static String macNoColon(const uint8_t *mac) {
    char buf[13];
    snprintf(buf, sizeof(buf), "%02X%02X%02X%02X%02X%02X",
             mac[0], mac[1], mac[2], mac[3], mac[4], mac[5]);
    return String(buf);
}

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

#if ESP_IDF_VERSION >= ESP_IDF_VERSION_VAL(5, 5, 0)
void onNowSent(const esp_now_send_info_t *info, esp_now_send_status_t status) {
    (void)info;
    lastSendOk = (status == ESP_NOW_SEND_SUCCESS);
}
#else
void onNowSent(const uint8_t *mac, esp_now_send_status_t status) {
    (void)mac;
    lastSendOk = (status == ESP_NOW_SEND_SUCCESS);
}
#endif

static bool startEspNow() {
    WiFi.mode(WIFI_STA);
    WiFi.disconnect(true);
    delay(80);
    esp_wifi_set_promiscuous(true);
    esp_wifi_set_channel(ESPNOW_WIFI_CHANNEL, WIFI_SECOND_CHAN_NONE);
    esp_wifi_set_promiscuous(false);

    uint8_t myMac[6];
    WiFi.macAddress(myMac);
    Serial.printf("Keypad MAC: %s\n", macToString(myMac).c_str());
    Serial.printf("LED MAC:    %s\n", macToString(ledMac).c_str());
    Serial.printf("ESP-NOW channel %d\n", ESPNOW_WIFI_CHANNEL);

    if (esp_now_init() != ESP_OK) {
        setStatus("NOW init fail");
        return false;
    }
    esp_now_register_send_cb(onNowSent);

    esp_now_peer_info_t peer = {};
    memcpy(peer.peer_addr, ledMac, 6);
    peer.channel = ESPNOW_WIFI_CHANNEL;
    peer.encrypt = false;
    peer.ifidx = WIFI_IF_STA;
    if (esp_now_is_peer_exist(ledMac)) {
        esp_now_del_peer(ledMac);
    }
    if (esp_now_add_peer(&peer) != ESP_OK) {
        setStatus("NOW peer fail");
        return false;
    }
    return true;
}

static void sendToLedBoard(const char *text) {
    char packet[32];
    if (text[0] == '\0') {
        snprintf(packet, sizeof(packet), "CLR");
    } else {
        snprintf(packet, sizeof(packet), "SET:%s", text);
    }
    Serial.printf("TX %s -> %s\n", packet, macToString(ledMac).c_str());

    if (!nowReady) {
        return;
    }
    esp_err_t err = esp_now_send(ledMac, reinterpret_cast<const uint8_t *>(packet), strlen(packet));
    if (err != ESP_OK) {
        lastSendOk = false;
        setStatus("NOW send fail");
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

void setup() {
    Serial.begin(115200);
    delay(200);
    Serial.println();
    Serial.println("ESP32 keypad + LCD 16x2  (ESP-NOW / WiFi MAC)");

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
    }

    keypad.setDebounceTime(40);
    keypad.setHoldTime(400);

    nowReady = startEspNow();

    uint8_t myMac[6];
    WiFi.macAddress(myMac);
    if (lcdReady) {
        lcd->setCursor(0, 0);
        lcd->print("My MAC          ");
        lcd->setCursor(0, 1);
        lcd->print(macNoColon(myMac));
        delay(1500);
        lcd->setCursor(0, 0);
        lcd->print("LED MAC         ");
        lcd->setCursor(0, 1);
        lcd->print(macNoColon(ledMac));
        delay(1500);
    }

    setStatus(nowReady ? "ESP-NOW ready" : "ESP-NOW fail");
    refreshLcd();
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
}
