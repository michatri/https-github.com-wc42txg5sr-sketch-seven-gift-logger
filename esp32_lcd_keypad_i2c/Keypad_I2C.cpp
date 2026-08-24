/*
||
|| @file Keypad_I2C.cpp
|| @version 3.0 - multiple WireX support
|| @author G. D. (Joe) Young, ptw
||
|| Vendored from https://github.com/joeyoung/arduino_keypads
|| License: GNU Lesser General Public License v2.1 or later
||
*/

#include "Keypad_I2C.h"

void Keypad_I2C::begin(char *userKeymap) {
  Keypad::begin(userKeymap);
  port_write(0xffff);
  pinState = pinState_set();
}

void Keypad_I2C::begin(void) {
  port_write(0xffff);
  pinState = pinState_set();
}

void Keypad_I2C::pin_write(byte pinNum, boolean level) {
  word mask = (word)1 << pinNum;
  if (level == HIGH) {
    pinState |= mask;
  } else {
    pinState &= ~mask;
  }
  port_write(pinState);
}

int Keypad_I2C::pin_read(byte pinNum) {
  word mask = (word)0x1 << pinNum;
  _wire->requestFrom((int)i2caddr, (int)i2cwidth);
  word pinVal = _wire->read();
  if (i2cwidth > 1) {
    pinVal |= _wire->read() << 8;
  }
  pinVal &= mask;
  return (pinVal == mask) ? 1 : 0;
}

void Keypad_I2C::port_write(word i2cportval) {
  _wire->beginTransmission((int)i2caddr);
  _wire->write(i2cportval & 0x00FF);
  if (i2cwidth > 1) {
    _wire->write(i2cportval >> 8);
  }
  _wire->endTransmission();
  pinState = i2cportval;
}

word Keypad_I2C::pinState_set() {
  _wire->requestFrom((int)i2caddr, (int)i2cwidth);
  pinState = _wire->read();
  if (i2cwidth > 1) {
    pinState |= _wire->read() << 8;
  }
  return pinState;
}
