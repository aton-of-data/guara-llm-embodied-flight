/* SPDX-License-Identifier: Apache-2.0 */
/*
 * Aligned caller storage for the ABI tests and for the published example.
 *
 * A plain `unsigned char[N]` carries no alignment guarantee, and the init entry
 * points reject a buffer that does not meet *_storage_align().
 */
#ifndef GUARA_TEST_STORAGE_H
#define GUARA_TEST_STORAGE_H

#include <stddef.h>
#include <stdint.h>

/* First address at or after `raw` that is a multiple of `align`. */
static inline unsigned char * guara_test_align(unsigned char * raw, size_t align)
{
  const uintptr_t addr = (uintptr_t)raw;
  const uintptr_t a = (uintptr_t)(align == 0U ? 1U : align);
  return (unsigned char *)((addr + (a - 1U)) & ~(a - 1U));
}

/* Bytes still usable after aligning `raw` (capacity `n`) up to `align`. */
static inline size_t guara_test_capacity(unsigned char * raw, size_t n, size_t align)
{
  const unsigned char * base = guara_test_align(raw, align);
  const size_t used = (size_t)(base - raw);
  return used >= n ? 0U : n - used;
}

#endif /* GUARA_TEST_STORAGE_H */
