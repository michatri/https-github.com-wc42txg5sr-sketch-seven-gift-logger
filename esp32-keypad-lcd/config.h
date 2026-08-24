#pragma once

#include "protocol.h"

// ---- Keypad 3x4 ----
// Layout:
//   1  2  3
//   4  5  6
//   7  8  9
//   *  0  #
#define KEYPAD_ROWS 4
#define KEYPAD_COLS 3

// User-specified wiring
#define KEYPAD_ROW_PINS {4, 12, 14, 5}
#define KEYPAD_COL_PINS {26, 25, 33}

// ---- LCD 16x2 I2C (PCF8574 backpack) ----
#define LCD_SDA_PIN     21
#define LCD_SCL_PIN     22
#define LCD_ADDR        0x27
#define LCD_ADDR_ALT    0x3F
#define LCD_COLS        16
#define LCD_ROWS        2
