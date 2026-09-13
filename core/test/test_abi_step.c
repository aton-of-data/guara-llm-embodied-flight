/* SPDX-License-Identifier: Apache-2.0 */
/*
 * SPEC §3.5 T2 then T3 through the C ABI: in-charge + owned mode + clear -> CF;
 * a geofence time-to-violation at the threshold -> RF / HOLD.
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
  CHECK(sizeof buf >= guara_core_storage_size());
  guara_params p;
  guara_params_default(&p);
  CHECK(guara_core_init(buf, sizeof buf, &p) == GUARA_OK);

  guara_inputs in;
  memset(&in, 0, sizeof in);
  in.t_s = 1.0;
  in.in_charge = 1;
  in.owned_mode_active = 1;
  in.t_daa_s = INFINITY;
  in.t_gf_s = INFINITY;
  in.monitor_action = 1; /* HOLD */

  guara_output out;
  CHECK(guara_core_step(buf, &in, &out) == GUARA_OK);
  CHECK(out.state == 1); /* CF */
  CHECK(out.transition.id == 2); /* T2 */
  CHECK(out.command == 0);

  in.t_s = 2.0;
  in.t_gf_s = 0.5; /* <= tau_gf_s (1.0) */
  CHECK(guara_core_step(buf, &in, &out) == GUARA_OK);
  CHECK(out.state == 2); /* RF */
  CHECK(out.recovery == 1); /* HOLD */
  CHECK(out.transition.id == 3); /* T3 */
  CHECK(out.command == 1); /* HOLD */
  CHECK((out.unsafe_causes & 2u) != 0); /* geofence */

  printf("PASS abi_step T2->T3 state=%u recovery=%u\n", out.state, out.recovery);
  return 0;
}
