#pragma once

// ESP-NOW (WiFi MAC) protocol between ESP32 keypad and ESP32-S3 LED panel.
// Keep this file identical in both sketch folders and in shared/.

#define MAX_MESSAGE_LEN      6
#define ESPNOW_WIFI_CHANNEL  1

// MAC ของบอร์ด ESP32-S3 (บอร์ดจอ LED)
// 1) อัปโหลดบอร์ด 2 แล้วดู MAC จาก Serial หรือบนจอ LED ตอนบูต
// 2) ใส่ค่านั้นที่นี่ แล้วอัปโหลดบอร์ด 1 ใหม่
// ตัวอย่าง: ถ้า Serial พิมพ์ 24:6F:28:AA:BB:CC
//   #define LED_BOARD_MAC 0x24, 0x6F, 0x28, 0xAA, 0xBB, 0xCC
//
// ค่า FF:FF:FF:FF:FF:FF = broadcast ส่งถึงทุก ESP-NOW ในช่องเดียวกัน
#define LED_BOARD_MAC 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF

// Commands:
//   SET:<0-6 chars>   display text
//   CLR               clear screen
