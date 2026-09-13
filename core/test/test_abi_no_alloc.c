/* SPDX-License-Identifier: Apache-2.0 */
/*
 * After init, 10000 ABI steps must not call malloc/free/write (GNU --wrap).
 */
#include "guara/guara.h"

#include <math.h>
#include <stdio.h>
#include <string.h>

#define CHECK(cond) \
  do { \
    if (!(cond)) { \
      fprintf(stderr, "FAIL %s:%d: %s\n", __FILE__, __LINE__, #cond); \
      return 1; \
    } \
  } while (0)

int main(void)
{
  unsigned char buf[1024];
  guara_params p;
  guara_params_default(&p);
  CHECK(guara_core_init(buf, sizeof buf, &p) == GUARA_OK);

  unsigned char gwbuf[1024];
  guara_gateway_limits lim;
  guara_gateway_limits_default(&lim);
  CHECK(guara_gateway_init(gwbuf, sizeof gwbuf, &lim) == GUARA_OK);
  CHECK(guara_gateway_on_core_state(gwbuf, 1, 0.0) == GUARA_OK);

  guara_inputs in;
  memset(&in, 0, sizeof in);
  in.in_charge = 1;
  in.owned_mode_active = 1;
  in.t_daa_s = INFINITY;
  in.t_gf_s = INFINITY;
  in.monitor_action = 1;

  guara_output out;
  for (int k = 1; k <= 10000; ++k) {
    in.t_s = (double)k * 0.05;
    in.t_gf_s = (k % 17 == 0) ? 0.1 : INFINITY;
    CHECK(guara_core_step(buf, &in, &out) == GUARA_OK);
    {
      const float v[3] = {1.0F, 0.0F, 0.0F};
      CHECK(guara_gateway_on_cf_setpoint(gwbuf, in.t_s, in.t_s, v, 0.0F) == GUARA_OK);
      guara_gateway_output gout;
      CHECK(guara_gateway_compute(gwbuf, in.t_s, &gout) == GUARA_OK);
    }
    if (k % 1000 == 0) {
      CHECK(guara_core_latch_on_actuation_failure(buf, in.t_s, &out) == GUARA_OK);
    }
  }
  printf("PASS abi_no_alloc ticks=10000 last_state=%u\n", out.state);
  return 0;
}
