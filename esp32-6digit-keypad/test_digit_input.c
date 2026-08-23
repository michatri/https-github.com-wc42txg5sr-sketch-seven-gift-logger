#include <stdio.h>
#include <string.h>
#include "DigitInput.h"

static int failures = 0;

static void expectEq(const char *name, int actual, int expected) {
  if (actual != expected) {
    printf("FAIL %s: got %d expected %d\n", name, actual, expected);
    failures++;
  }
}

static void expectStr(const char *name, const char *actual, const char *expected) {
  if (strcmp(actual, expected) != 0) {
    printf("FAIL %s: got \"%s\" expected \"%s\"\n", name, actual, expected);
    failures++;
  }
}

int main(void) {
  DigitInput input;
  digitInputInit(&input);

  expectEq("empty confirm", digitInputConfirm(&input), DIGIT_INPUT_IGNORED_EMPTY);
  expectEq("empty backspace", digitInputBackspace(&input), DIGIT_INPUT_IGNORED_EMPTY);

  expectEq("append 1", digitInputAppend(&input, '1'), DIGIT_INPUT_OK);
  expectEq("append 2", digitInputAppend(&input, '2'), DIGIT_INPUT_OK);
  expectEq("append 3", digitInputAppend(&input, '3'), DIGIT_INPUT_OK);
  expectEq("append 4", digitInputAppend(&input, '4'), DIGIT_INPUT_OK);
  expectEq("append 5", digitInputAppend(&input, '5'), DIGIT_INPUT_OK);
  expectEq("append 6", digitInputAppend(&input, '6'), DIGIT_INPUT_OK);
  expectStr("six digits", input.value, "123456");
  expectEq("length 6", (int)input.length, 6);
  expectEq("7th digit ignored", digitInputAppend(&input, '7'), DIGIT_INPUT_IGNORED_FULL);
  expectStr("still six digits", input.value, "123456");
  expectEq("confirm six", digitInputConfirm(&input), DIGIT_INPUT_CONFIRMED);

  expectEq("backspace", digitInputBackspace(&input), DIGIT_INPUT_OK);
  expectStr("after backspace", input.value, "12345");
  expectEq("append after delete", digitInputAppend(&input, '9'), DIGIT_INPUT_OK);
  expectStr("replaced last", input.value, "123459");

  digitInputClear(&input);
  expectStr("cleared", input.value, "");
  expectEq("letter ignored", digitInputAppend(&input, 'A'), DIGIT_INPUT_IGNORED_EMPTY);

  if (failures == 0) {
    printf("PASS 6-digit keypad buffer\n");
    return 0;
  }
  printf("%d failure(s)\n", failures);
  return 1;
}
