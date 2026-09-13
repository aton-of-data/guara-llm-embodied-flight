/* SPDX-License-Identifier: Apache-2.0 */
/*
 * AC-57 / AC-59: caller-supplied storage, rejection of short buffers and
 * invalid parameters, and a successful init of the default parameter set.
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
  CHECK(guara_core_storage_size() >= sizeof(void *));
  CHECK(guara_core_storage_align() >= 1);
  CHECK(strcmp(guara_core_version(), GUARA_CORE_VERSION) == 0);
  CHECK(strcmp(guara_abi_version(), GUARA_ABI_VERSION) == 0);
  CHECK(strstr(guara_abi_version(), "provisional") != NULL);

  CHECK(guara_core_init(NULL, 64, NULL) == GUARA_ERR_NULL);

  unsigned char tiny[8];
  guara_params p;
  guara_params_default(&p);
  CHECK(guara_core_init(tiny, sizeof tiny, &p) == GUARA_ERR_STORAGE);

  p.n_max = 0;
  unsigned char buf[1024];
  CHECK(sizeof buf >= guara_core_storage_size());
  CHECK(guara_core_init(buf, sizeof buf, &p) == GUARA_ERR_PARAMS);
  CHECK(strcmp(guara_params_error(&p), "n_max must be >= 1") == 0);
  CHECK(guara_params_error(NULL) != NULL);

  guara_params_default(&p);
  CHECK(guara_core_init(buf, guara_core_storage_size(), &p) == GUARA_OK);

  guara_output out;
  CHECK(guara_core_step(buf, NULL, &out) == GUARA_ERR_NULL);

  unsigned char uninit[1024];
  memset(uninit, 0, sizeof uninit);
  guara_inputs in;
  memset(&in, 0, sizeof in);
  CHECK(guara_core_step(uninit, &in, &out) == GUARA_ERR_UNINIT);

  printf("PASS abi_storage size=%zu align=%zu\n",
         guara_core_storage_size(), guara_core_storage_align());
  return 0;
}
