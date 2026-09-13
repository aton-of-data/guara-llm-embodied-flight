/* SPDX-License-Identifier: Apache-2.0 */
/*
 * Minimal out-of-tree consumer of the installed guara_core package (AC-57).
 * It shows the storage contract: the caller owns the memory, sizes it with
 * guara_core_storage_size() and aligns it to guara_core_storage_align().
 */
#include "guara/guara.h"

#include <stdint.h>
#include <stdio.h>

int main(void)
{
  unsigned char raw[1024 + 64];
  const size_t align = guara_core_storage_align();
  unsigned char * buf =
      (unsigned char *)(((uintptr_t)raw + (align - 1U)) & ~(uintptr_t)(align - 1U));
  const size_t cap = sizeof raw - (size_t)(buf - raw);
  guara_params p;
  guara_params_default(&p);
  if (cap < guara_core_storage_size()) {
    return 1;
  }
  if (guara_core_init(buf, cap, &p) != GUARA_OK) {
    return 1;
  }
  printf("guara-core %s abi %s storage=%zu\n",
         guara_core_version(), guara_abi_version(), guara_core_storage_size());
  return 0;
}
