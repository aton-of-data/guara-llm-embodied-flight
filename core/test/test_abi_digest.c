/* SPDX-License-Identifier: Apache-2.0 */
/*
 * G-K8: the parameter digest is a function of the canonical field order, not
 * of struct padding. A single field change must change the digest, and the
 * digest stored at init must match guara_params_digest of the same set.
 */
#include "guara/guara.h"

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
  guara_params p;
  guara_params_default(&p);
  uint8_t a[GUARA_PARAM_DIGEST_LEN];
  uint8_t b[GUARA_PARAM_DIGEST_LEN];
  uint8_t stored[GUARA_PARAM_DIGEST_LEN];
  guara_params_digest(&p, a);
  guara_params_digest(&p, b);
  CHECK(memcmp(a, b, GUARA_PARAM_DIGEST_LEN) == 0);

  p.n_max = 4;
  guara_params_digest(&p, b);
  CHECK(memcmp(a, b, GUARA_PARAM_DIGEST_LEN) != 0);

  guara_params_default(&p);
  unsigned char buf[1024];
  CHECK(guara_core_init(buf, sizeof buf, &p) == GUARA_OK);
  CHECK(guara_core_param_digest(buf, stored) == GUARA_OK);
  CHECK(memcmp(a, stored, GUARA_PARAM_DIGEST_LEN) == 0);

  unsigned char uninit[1024];
  memset(uninit, 0, sizeof uninit);
  CHECK(guara_core_param_digest(uninit, stored) == GUARA_ERR_UNINIT);

  printf("PASS abi_digest\n");
  return 0;
}
