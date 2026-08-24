#pragma once

// Shared wireless protocol between ESP32 keypad and ESP32-S3 LED panel.
// Keep this file identical in both sketch folders and in shared/.

#define WIFI_AP_SSID        "ESP32-LED-P4"
#define WIFI_AP_PASSWORD    "12345678"
#define WIFI_UDP_PORT       4210

// SoftAP on the ESP32-S3 is always 192.168.4.1
#define LED_BOARD_IP_OCTET1 192
#define LED_BOARD_IP_OCTET2 168
#define LED_BOARD_IP_OCTET3 4
#define LED_BOARD_IP_OCTET4 1

#define MAX_MESSAGE_LEN     6

#define BLE_DEVICE_NAME     "ESP32S3-LED"
#define BLE_NUS_SERVICE_UUID           "6E400001-B5A3-F393-E0A9-E50E24DCCA9E"
#define BLE_NUS_CHARACTERISTIC_RX_UUID "6E400002-B5A3-F393-E0A9-E50E24DCCA9E"
#define BLE_NUS_CHARACTERISTIC_TX_UUID "6E400003-B5A3-F393-E0A9-E50E24DCCA9E"

#define BT_CLASSIC_NAME     "ESP32-Keypad"

// Commands over UDP / BLE / HTTP
//   SET:<0-6 chars>   display text
//   CLR               clear screen
// A bare payload of 0-6 printable chars is treated as SET.
