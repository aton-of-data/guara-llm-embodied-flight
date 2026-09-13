/* SPDX-License-Identifier: Apache-2.0 */
/*
 * Silent ABI runner for the freestanding link (no printf: write is trapped).
 */
#include "guara/guara.h"

#include "storage.h"

#include <math.h>
#include <string.h>

int main(void)
{
  unsigned char raw[1024 + 64];
  unsigned char * buf = guara_test_align(raw, guara_core_storage_align());
  const size_t cap = guara_test_capacity(raw, sizeof raw, guara_core_storage_align());
  if (cap < guara_core_storage_size()) {
    return 1;
  }
  guara_params p;
  guara_params_default(&p);
  if (guara_core_init(buf, cap, &p) != GUARA_OK) {
    return 2;
  }
  unsigned char gwraw[1024 + 64];
  unsigned char * gwbuf = guara_test_align(gwraw, guara_gateway_storage_align());
  const size_t gwcap = guara_test_capacity(gwraw, sizeof gwraw, guara_gateway_storage_align());
  guara_gateway_limits lim;
  guara_gateway_limits_default(&lim);
  if (guara_gateway_init(gwbuf, gwcap, &lim) != GUARA_OK) {
    return 5;
  }
  if (guara_gateway_on_core_state(gwbuf, 1, 0.0) != GUARA_OK) {
    return 6;
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
    const float v[3] = {1.0F, 0.0F, 0.0F};
    const double t = (double)k * 0.05;
    if (guara_gateway_on_cf_setpoint(gwbuf, t, t, v, 0.0F) != GUARA_OK) {
      return 7;
    }
    guara_gateway_output gout;
    if (guara_gateway_compute(gwbuf, t, &gout) != GUARA_OK) {
      return 8;
    }
  }
  return out.state == 1 ? 0 : 4;
}
