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

}  // namespace guara_rta
