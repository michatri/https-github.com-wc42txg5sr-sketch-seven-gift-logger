/*
||
|| @file Keypad_I2C.h
|| @version 3.0 - multiple WireX support
|| @version 2.0 - PCF8575 support added by Paul Williamson
|| @author G. D. (Joe) Young, ptw
|| @contact "G. D. (Joe) Young" <jyoung@islandnet.com>
||
|| Vendored from https://github.com/joeyoung/arduino_keypads
|| License: GNU Lesser General Public License v2.1 or later
||
*/

#ifndef KEYPAD_I2C_H
#define KEYPAD_I2C_H

#include "Keypad.h"
#include "Wire.h"

#define PCF8574 1  // PCF8574 I/O expander device is 1 byte wide
#define PCF8575 2  // PCF8575 I/O expander device is 2 bytes wide

class Keypad_I2C : public Keypad {
 public:
  Keypad_I2C(char *userKeymap, byte *row, byte *col, byte numRows, byte numCols,
             byte address, byte width = 1, TwoWire *awire = &Wire)
      : Keypad(userKeymap, row, col, numRows, numCols) {
    i2caddr = address;
    i2cwidth = width;
    _wire = awire;
  }

  void begin(char *userKeymap);
  void begin(void);

  void pin_mode(byte pinNum, byte mode) {
    (void)pinNum;
    (void)mode;
  }
  void pin_write(byte pinNum, boolean level);
  int pin_read(byte pinNum);
  word pinState_set();
  void port_write(word i2cportval);

 private:
  byte i2caddr;
  byte i2cwidth;
  word pinState;
  TwoWire *_wire;
};

#endif  // KEYPAD_I2C_H
