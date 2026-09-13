/* SPDX-License-Identifier: Apache-2.0 */
/*
 * Smoke the monitor C ABI (H-4 / H-6). Golden JSON is driven by the kit.
 */
#include "guara/guara.h"

#include <stdio.h>
#include <stdint.h>
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
  unsigned char raw[4096];
  const size_t a = guara_monitor_storage_align();
  const uintptr_t addr = (uintptr_t)raw;
  unsigned char *buf = (unsigned char *)((addr + (a - 1U)) & ~(uintptr_t)(a - 1U));
  const size_t cap = (size_t)((raw + sizeof raw) - buf);
  CHECK(guara_monitor_init(buf, cap, 0.5) == GUARA_OK);
  CHECK(guara_monitor_expect(buf, "REQ-ALT-01") == GUARA_OK);

  guara_monitor_eval ev;
  CHECK(guara_monitor_evaluate(buf, 0.0, &ev) == GUARA_OK);
  CHECK(ev.invalid == 1);

  guara_monitor_sample s;
  memset(&s, 0, sizeof s);
  s.id = "REQ-ALT-01";
  s.monitor_class = 1;
  s.action = 0;
  s.violated = 0;
  s.inputs_complete = 1;
  CHECK(guara_monitor_observe(buf, &s, 1.0) == GUARA_MONITOR_ACCEPTED);
  CHECK(guara_monitor_evaluate(buf, 1.4, &ev) == GUARA_OK);
  CHECK(ev.invalid == 0);
  CHECK(guara_monitor_evaluate(buf, 1.6, &ev) == GUARA_OK);
  CHECK(ev.invalid == 1);

  s.violated = 1;
  s.action = 1;
  CHECK(guara_monitor_observe(buf, &s, 2.0) == GUARA_MONITOR_ACCEPTED);
  CHECK(guara_monitor_evaluate(buf, 2.0, &ev) == GUARA_OK);
  CHECK(ev.violation == 1);
  CHECK(ev.action == 2);

  s.action = 3;
  CHECK(guara_monitor_observe(buf, &s, 2.1) == GUARA_MONITOR_INVALID_FIELD);
  printf("PASS abi_monitor\n");
  return 0;
}
