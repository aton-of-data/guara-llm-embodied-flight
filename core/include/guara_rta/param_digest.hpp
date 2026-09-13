// SPDX-License-Identifier: Apache-2.0
//
// Canonical parameter-set digest (G-K8). FNV-1a-64 over IEEE-754 little-endian
// fields in guara_params header order. Padding is not hashed.
#pragma once

#include <cstddef>
#include <cstdint>

#include "guara_rta/decision_core.hpp"

namespace guara_rta
{

inline constexpr std::size_t kParamDigestLen = 8;

void paramDigest(const Parameters & p, std::uint8_t out[kParamDigestLen]) noexcept;

}  // namespace guara_rta
