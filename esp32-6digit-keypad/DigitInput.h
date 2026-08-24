#pragma once

#include <stddef.h>
#include <string.h>

#ifdef __cplusplus
extern "C" {
#endif

#ifndef DIGIT_INPUT_MAX
#define DIGIT_INPUT_MAX 6
#endif

typedef enum DigitInputResult {
  DIGIT_INPUT_OK = 0,
  DIGIT_INPUT_IGNORED_FULL,
  DIGIT_INPUT_IGNORED_EMPTY,
  DIGIT_INPUT_CONFIRMED
} DigitInputResult;

typedef struct DigitInput {
  char value[DIGIT_INPUT_MAX + 1];
  size_t length;
} DigitInput;

static inline void digitInputClear(DigitInput *input) {
  input->length = 0;
  input->value[0] = '\0';
}

static inline void digitInputInit(DigitInput *input) {
  digitInputClear(input);
}

static inline DigitInputResult digitInputAppend(DigitInput *input, char digit) {
  if (digit < '0' || digit > '9') {
    return DIGIT_INPUT_IGNORED_EMPTY;
  }
  if (input->length >= DIGIT_INPUT_MAX) {
    return DIGIT_INPUT_IGNORED_FULL;
  }
  input->value[input->length++] = digit;
  input->value[input->length] = '\0';
  return DIGIT_INPUT_OK;
}

static inline DigitInputResult digitInputBackspace(DigitInput *input) {
  if (input->length == 0) {
    return DIGIT_INPUT_IGNORED_EMPTY;
  }
  input->value[--input->length] = '\0';
  return DIGIT_INPUT_OK;
}

static inline DigitInputResult digitInputConfirm(const DigitInput *input) {
  if (input->length == 0) {
    return DIGIT_INPUT_IGNORED_EMPTY;
  }
  return DIGIT_INPUT_CONFIRMED;
}

#ifdef __cplusplus
}
#endif
