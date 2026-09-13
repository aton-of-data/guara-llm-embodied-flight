// SPDX-License-Identifier: Apache-2.0
#include "guara_rta/types.hpp"

namespace guara_rta
{

const char * toString(State s) noexcept
{
  switch (s) {
    case State::kInactive: return "INACTIVE";
    case State::kCf: return "CF";
    case State::kRf: return "RF";
    case State::kLatched: return "LATCHED";
  }
  return "UNKNOWN";
}

const char * toString(Recovery r) noexcept
{
  switch (r) {
    case Recovery::kNone: return "NONE";
    case Recovery::kHold: return "HOLD";
    case Recovery::kRtl: return "RTL";
    case Recovery::kLand: return "LAND";
  }
  return "UNKNOWN";
}

const char * toString(Command c) noexcept
{
  switch (c) {
    case Command::kNone: return "NONE";
    case Command::kHold: return "HOLD";
    case Command::kRtl: return "RTL";
    case Command::kLand: return "LAND";
    case Command::kOwnedMode: return "OWNED_MODE";
  }
  return "UNKNOWN";
}

const char * transitionName(std::uint8_t id) noexcept
{
  switch (id) {
    case transition::kNone: return "NONE";
    case transition::kT1: return "T1";
    case transition::kT2: return "T2";
    case transition::kT3: return "T3";
    case transition::kT4: return "T4";
    case transition::kT5: return "T5";
    case transition::kT6: return "T6";
    case transition::kT7: return "T7";
    case transition::kT2b: return "T2B";
    case transition::kActuationLatch: return "ACTUATION";
    default: return "UNKNOWN";
  }
}

// Names a single cause bit, or zero. A union of bits has no name.
const char * causeName(std::uint32_t bits) noexcept
{
  switch (bits) {
    case 0U: return "NONE";
    case cause::kDaa: return "DAA";
    case cause::kGeofence: return "GEOFENCE";
    case cause::kMonitor: return "MONITOR";
    case cause::kInput: return "INPUT";
    case cause::kLatch: return "LATCH";
    case cause::kReturn: return "RETURN";
    case cause::kNotInCharge: return "NOT_IN_CHARGE";
    case cause::kEscalation: return "ESCALATION";
    case cause::kActuation: return "ACTUATION";
    default: return "UNKNOWN";
  }
}

}  // namespace guara_rta
