// SPDX-License-Identifier: Apache-2.0
//
// Vocabulary types of the Guará switching logic (SPEC §3). The encodings of State, Recovery and the
// cause bits equal the constants of guara_msgs/RtaEvent so that conversion is a cast.
#pragma once

#include <cstdint>

namespace guara_rta
{

enum class State : std::uint8_t
{
  kInactive = 0,
  kCf = 1,
  kRf = 2,
  kLatched = 3,
};

// Recovery functions ordered by rank (SPEC §3.5, ADR 0005 item 4): HOLD < RTL < LAND.
enum class Recovery : std::uint8_t
{
  kNone = 0,
  kHold = 1,
  kRtl = 2,
  kLand = 3,
};

// Mode request emitted by the decision core towards the actuator.
enum class Command : std::uint8_t
{
  kNone = 0,
  kHold = 1,
  kRtl = 2,
  kLand = 3,
  kOwnedMode = 4,
};

namespace cause
{
constexpr std::uint32_t kDaa = 1U << 0U;
constexpr std::uint32_t kGeofence = 1U << 1U;
constexpr std::uint32_t kMonitor = 1U << 2U;
constexpr std::uint32_t kInput = 1U << 3U;
constexpr std::uint32_t kLatch = 1U << 4U;
constexpr std::uint32_t kReturn = 1U << 5U;
constexpr std::uint32_t kNotInCharge = 1U << 6U;
constexpr std::uint32_t kEscalation = 1U << 7U;
constexpr std::uint32_t kActuation = 1U << 8U;
constexpr std::uint32_t kUnsafeMask = kDaa | kGeofence | kMonitor | kInput;
}  // namespace cause

// Transition identifiers of SPEC §3.5. T2b is encoded as 8; the FM-7 actuation latch as 9.
namespace transition
{
constexpr std::uint8_t kNone = 0;
constexpr std::uint8_t kT1 = 1;
constexpr std::uint8_t kT2 = 2;
constexpr std::uint8_t kT3 = 3;
constexpr std::uint8_t kT4 = 4;
constexpr std::uint8_t kT5 = 5;
constexpr std::uint8_t kT6 = 6;
constexpr std::uint8_t kT7 = 7;
constexpr std::uint8_t kT2b = 8;
constexpr std::uint8_t kActuationLatch = 9;
}  // namespace transition

constexpr std::uint8_t rank(Recovery r) noexcept {return static_cast<std::uint8_t>(r);}

constexpr Recovery maxRank(Recovery a, Recovery b) noexcept {return rank(a) >= rank(b) ? a : b;}

constexpr Command commandFor(Recovery r) noexcept
{
  switch (r) {
    case Recovery::kHold: return Command::kHold;
    case Recovery::kRtl: return Command::kRtl;
    case Recovery::kLand: return Command::kLand;
    case Recovery::kNone: return Command::kNone;
  }
  return Command::kNone;
}

const char * toString(State s) noexcept;
const char * toString(Recovery r) noexcept;
const char * toString(Command c) noexcept;

}  // namespace guara_rta
