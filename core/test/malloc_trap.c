/* SPDX-License-Identifier: Apache-2.0 */
/*
 * GNU ld --wrap heap traps. Linked only into the ABI no-alloc tests.
 * A heap call after init means the kernel allocated.
 */
#include <stddef.h>
#include <stdlib.h>

static void trap(void)
{
  abort();
}

void * __wrap_malloc(size_t n)
{
  (void)n;
  trap();
  return NULL;
}

void __wrap_free(void * p)
{
  (void)p;
  trap();
}

void * __wrap_calloc(size_t n, size_t sz)
{
  (void)n;
  (void)sz;
  trap();
  return NULL;
}

void * __wrap_realloc(void * p, size_t n)
{
  (void)p;
  (void)n;
  trap();
  return NULL;
}
