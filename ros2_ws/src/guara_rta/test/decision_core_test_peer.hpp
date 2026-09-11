// SPDX-License-Identifier: Apache-2.0
//
// Test-only access to the internal state of DecisionCore, used to place the core in an arbitrary
// pre-state before evaluating one tick.
#pragma once

#include <cmath>
#include <cstddef>
#include <limits>

#include "guara_rta/decision_core.hpp"

namespace guara_rta
{

struct DecisionCoreTestPeer
{
  static void set(
    DecisionCore & core, State state, Recovery recovery, double t_prev_s, double t_switch_s,
    double clear_since_s)
  {
    core.state_ = state;
    core.recovery_ = recovery;
    core.t_prev_s_ = t_prev_s;
    core.t_switch_s_ = t_switch_s;
    core.clear_since_s_ = clear_since_s;
    core.unsafe_since_s_ = std::numeric_limits<double>::quiet_NaN();
  }

  static void setSwitchHistory(DecisionCore & core, const double * times, std::size_t n)
  {
    core.switch_head_ = 0;
    core.switch_count_ = 0;
    for (std::size_t i = 0; i < n; ++i) {
      core.recordSwitch(times[i]);
    }
  }
};

}  // namespace guara_rta
