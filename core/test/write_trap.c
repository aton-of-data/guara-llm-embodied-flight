/* SPDX-License-Identifier: Apache-2.0 */
/*
 * GNU ld --wrap write trap. Linked only into the freestanding ABI test.
 * The kernel must not write after init; the test itself does not print.
 */
#include <stddef.h>
#include <stdlib.h>
#include <unistd.h>

ssize_t __wrap_write(int fd, const void * buf, size_t n)
{
  (void)fd;
  (void)buf;
  (void)n;
  abort();
  return -1;
}
