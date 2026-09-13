/* SPDX-License-Identifier: Apache-2.0 */
#include "guara/guara.h"

#include <stdio.h>

int main(void)
{
  unsigned char buf[1024];
  guara_params p;
  guara_params_default(&p);
  if (guara_core_init(buf, sizeof buf, &p) != GUARA_OK) {
    return 1;
  }
  printf("guara-core %s abi %s storage=%zu\n",
         guara_core_version(), guara_abi_version(), guara_core_storage_size());
  return 0;
}
