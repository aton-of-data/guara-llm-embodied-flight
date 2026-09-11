// SPDX-License-Identifier: Apache-2.0
//
// GatewayLogic: the setpoint-forwarding rule of the owned mode GuaraCfGateway (SPEC §2 Input Manager
// item b; ADR 0001 rule 4; ADR 0005 item 7). The CF setpoint is forwarded only while the decision
// core is in state CF, the setpoint was generated after the most recent entry into CF, and it is not
// older than the configured timeout. In every other case the gateway commands zero velocity, which
// holds the vehicle while a recovery-mode switch is pending (SPEC FM-7).
#pragma once

#include <array>
#include <cmath>
#include <limits>

#include "guara_rta/types.hpp"

namespace guara_rta
{

struct GatewaySetpoint
{
  std::array<float, 3> velocity_ned_m_s{0.0F, 0.0F, 0.0F};
  float yaw_ned_rad{std::numeric_limits<float>::quiet_NaN()};
  bool forwarding_cf{false};
};

class GatewayLogic
{
public:
  explicit GatewayLogic(double cf_setpoint_timeout_s) noexcept
  : timeout_s_(cf_setpoint_timeout_s) {}

  // `t_s` is the gateway clock, the same clock on which CF setpoints are stamped.
  void onCoreState(State state, double t_s) noexcept
  {
    if (state == State::kCf && state_ != State::kCf) {
      t_enter_cf_s_ = t_s;
    }
    state_ = state;
  }

  void onCfSetpoint(double stamp_s, const std::array<float, 3> & velocity, float yaw) noexcept
  {
    for (float v : velocity) {
      if (!std::isfinite(v)) {
        return;  // non-finite velocity components are rejected, not forwarded
      }
    }
    cf_stamp_s_ = stamp_s;
    cf_velocity_ = velocity;
    cf_yaw_ = yaw;
    have_cf_ = true;
  }

  GatewaySetpoint compute(double t_s) const noexcept
  {
    GatewaySetpoint out;
    const bool fresh = have_cf_ && cf_stamp_s_ > t_enter_cf_s_ && t_s - cf_stamp_s_ <= timeout_s_;
    if (state_ == State::kCf && fresh) {
      out.velocity_ned_m_s = cf_velocity_;
      out.yaw_ned_rad = cf_yaw_;
      out.forwarding_cf = true;
    }
    return out;
  }

private:
  double timeout_s_;
  State state_{State::kInactive};
  double t_enter_cf_s_{std::numeric_limits<double>::infinity()};
  bool have_cf_{false};
  double cf_stamp_s_{-std::numeric_limits<double>::infinity()};
  std::array<float, 3> cf_velocity_{0.0F, 0.0F, 0.0F};
  float cf_yaw_{std::numeric_limits<float>::quiet_NaN()};
};

}  // namespace guara_rta
