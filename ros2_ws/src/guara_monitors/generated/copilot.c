#include <stdint.h>
#include <stdbool.h>
#include <string.h>
#include <stdlib.h>
#include <math.h>

#include "copilot_types.h"
#include "copilot.h"

static float input_signal_cpy;

static bool handlerAltitudeBelowCeiling_0_guard(void) {
  return !((input_signal_cpy) >= ((float)(0.0f)));
}

void step(void) {
  (input_signal_cpy) = (input_signal);
  if ((handlerAltitudeBelowCeiling_0_guard)()) {
    {(handlerAltitudeBelowCeiling)();}
  };
}
