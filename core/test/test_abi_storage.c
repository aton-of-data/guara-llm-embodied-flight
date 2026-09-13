/* SPDX-License-Identifier: Apache-2.0 */
/*
 * AC-57 / AC-59: caller-supplied storage, rejection of short buffers and
 * invalid parameters, and a successful init of the default parameter set.
 */
#include "guara/guara.h"

#include "storage.h"

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
  CHECK(guara_core_storage_size() >= sizeof(void *));
  CHECK(guara_core_storage_align() >= 1);
  CHECK(strcmp(guara_core_version(), GUARA_CORE_VERSION) == 0);
  CHECK(strcmp(guara_abi_version(), GUARA_ABI_VERSION) == 0);
  CHECK(strstr(guara_abi_version(), "provisional") != NULL);
  CHECK(strcmp(guara_err_name(GUARA_OK), "OK") == 0);
  CHECK(strcmp(guara_err_name(GUARA_ERR_UNINIT), "UNINIT") == 0);
  CHECK(strcmp(guara_err_name(9), "UNKNOWN") == 0);

  CHECK(guara_core_init(NULL, 64, NULL) == GUARA_ERR_NULL);

  unsigned char tiny[8];
  guara_params p;
  guara_params_default(&p);
  CHECK(guara_core_init(tiny, sizeof tiny, &p) == GUARA_ERR_STORAGE);

  p.n_max = 0;
  unsigned char raw[1024 + 64];
  unsigned char * buf = guara_test_align(raw, guara_core_storage_align());
  const size_t cap = guara_test_capacity(raw, sizeof raw, guara_core_storage_align());
  CHECK(cap >= guara_core_storage_size());
  CHECK(guara_core_init(buf, cap, &p) == GUARA_ERR_PARAMS);
  CHECK(strcmp(guara_params_error(&p), "n_max must be >= 1") == 0);
  CHECK(guara_params_error(NULL) != NULL);

  guara_params_default(&p);
  CHECK(guara_core_init(buf, guara_core_storage_size(), &p) == GUARA_OK);

  guara_output out;
  CHECK(guara_core_step(buf, NULL, &out) == GUARA_ERR_NULL);

  if (guara_core_storage_align() > 1U) {
    CHECK(guara_core_init(buf + 1, cap - 1U, &p) == GUARA_ERR_STORAGE);
  }

  unsigned char uninit_raw[1024 + 64];
  unsigned char * uninit = guara_test_align(uninit_raw, guara_core_storage_align());
  memset(uninit, 0, guara_core_storage_size());
  guara_inputs in;
  memset(&in, 0, sizeof in);
  CHECK(guara_core_step(uninit, &in, &out) == GUARA_ERR_UNINIT);

  printf("PASS abi_storage size=%zu align=%zu\n",
         guara_core_storage_size(), guara_core_storage_align());
  return 0;
}
