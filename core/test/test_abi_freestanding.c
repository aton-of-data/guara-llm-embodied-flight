/* SPDX-License-Identifier: Apache-2.0 */
/*
 * Silent ABI runner for the freestanding link (no printf: write is trapped).
 */
#include "guara/guara.h"

#include <math.h>
#include <string.h>

int main(void)
{
  unsigned char buf[1024];
  if (sizeof buf < 64) {
    return 1;
  }
  guara_params p;
  guara_params_default(&p);
  if (guara_core_init(buf, sizeof buf, &p) != GUARA_OK) {
    return 2;
  }
  guara_inputs in;
  memset(&in, 0, sizeof in);
  in.in_charge = 1;
  in.owned_mode_active = 1;
  in.t_daa_s = INFINITY;
  in.t_gf_s = INFINITY;
  in.monitor_action = 1;
  guara_output out;
  for (int k = 1; k <= 1000; ++k) {
    in.t_s = (double)k * 0.05;
    if (guara_core_step(buf, &in, &out) != GUARA_OK) {
      return 3;
    }
  }
  return out.state == 1 ? 0 : 4;
}
