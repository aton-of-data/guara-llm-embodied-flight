// SPDX-License-Identifier: Apache-2.0
#include "guara_rta/param_digest.hpp"

#include <cstring>

namespace guara_rta
{
namespace
{

constexpr std::uint64_t kFnvOffset = 14695981039346656037ULL;
constexpr std::uint64_t kFnvPrime = 1099511628211ULL;

void fnv1a(std::uint64_t & h, const void * p, std::size_t n) noexcept
{
  const auto * b = static_cast<const std::uint8_t *>(p);
  for (std::size_t i = 0; i < n; ++i) {
    h ^= b[i];
    h *= kFnvPrime;
  }
}

void write_le16(std::uint8_t * d, std::uint16_t v) noexcept
{
  d[0] = static_cast<std::uint8_t>(v);
  d[1] = static_cast<std::uint8_t>(v >> 8U);
}

void write_le64(std::uint8_t * d, std::uint64_t v) noexcept
{
  for (int i = 0; i < 8; ++i) {
    d[i] = static_cast<std::uint8_t>(v >> (8 * i));
  }
}

void feed_f64(std::uint64_t & h, double x) noexcept
{
  std::uint64_t bits = 0;
  static_assert(sizeof(double) == 8, "IEEE-754 double");
  std::memcpy(&bits, &x, 8);
#if defined(__BYTE_ORDER__) && __BYTE_ORDER__ == __ORDER_BIG_ENDIAN__
  bits = __builtin_bswap64(bits);
#endif
  std::uint8_t buf[8];
  write_le64(buf, bits);
  fnv1a(h, buf, 8);
}

}  // namespace

void paramDigest(const Parameters & p, std::uint8_t out[kParamDigestLen]) noexcept
{
  std::uint64_t h = kFnvOffset;
  feed_f64(h, p.tau_daa_s);
  feed_f64(h, p.tau_gf_s);
  feed_f64(h, p.h_daa_s);
  feed_f64(h, p.h_gf_s);
  feed_f64(h, p.dwell_s);
  std::uint8_t nmax[2];
  write_le16(nmax, p.n_max);
  fnv1a(h, nmax, 2);
  feed_f64(h, p.window_s);
  const std::uint8_t ret = p.return_enabled ? 1U : 0U;
  const std::uint8_t esc = p.escalation_enabled ? 1U : 0U;
  fnv1a(h, &ret, 1);
  fnv1a(h, &esc, 1);
  feed_f64(h, p.escalation_s);
  write_le64(out, h);
}

}  // namespace guara_rta
