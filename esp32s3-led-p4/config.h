#pragma once

#include "protocol.h"

// P4 64x32 HUB75 RGB LED matrix
#define PANEL_WIDTH   64
#define PANEL_HEIGHT  32
#define PANEL_CHAIN   1

// Set to 1 if the panel looks washed out / ghosting / wrong colors (FM6126A chips)
#define PANEL_FM6126A 0

// Brightness 0-255 (P4 panels are very bright; start low)
#define PANEL_BRIGHTNESS 80

// ---- HUB75 pin map for ESP32-S3-DevKitC-1 ----
// Avoids USB (19/20), UART0 (43/44), and octal-PSRAM pins (35-37).
// Change these if you use an adapter board with a fixed pinout.
#define HUB75_R1  4
#define HUB75_G1  5
#define HUB75_B1  6
#define HUB75_R2  7
#define HUB75_G2  15
#define HUB75_B2  16
#define HUB75_A   18
#define HUB75_B   8
#define HUB75_C   9
#define HUB75_D   10
#define HUB75_E   -1    // 32-row panels do not use E
#define HUB75_LAT 11
#define HUB75_OE  12
#define HUB75_CLK 13

#define ENABLE_WIFI_AP  1
#define ENABLE_BLE      1
#define ENABLE_HTTP     1
