// SPDX-License-Identifier: Apache-2.0
//
// GatewayLogic: the setpoint-forwarding rule of the owned mode GuaraCfGateway (SPEC §2 Input Manager
// item b; ADR 0001 rule 4; ADR 0005 item 7).
//
// The Complex Function is untrusted by construction, and an LLM-driven CF is untrusted in a stronger
// sense: it may emit well-formed nonsense, and an attacker able to reach the topic controls every
// field of CfSetpoint. The gateway therefore treats a CF setpoint as hostile input
// (docs/adr/0010-untrusted-complex-function-contract.md):
//
//   1. Freshness is measured on the gateway clock from the instant the setpoint was *received*, so
//      the CF cannot extend its own liveness by stamping a setpoint in the future (review H-1).
//   2. The ordering rule "generated after the most recent entry into CF" is evaluated on reception
//      instants, which the CF does not control.
//   3. A stamp that is not plausible on the gateway clock (ahead of now by more than
//      future_stamp_tolerance_s, or non-finite) is rejected outright.
//   4. Velocity is clamped to a configured envelope and yaw is rate limited, so the braking model of
//      the geofence predictor and the PX4 mode limits are not exceeded by the forwarded setpoint
//      (review H-2).
//   5. An optional SetpointGuard shadow-checks the proposed motion (geofence predictor evaluated on
//      the *proposed* velocity) before it is forwarded, so an aggressive planner is filtered before
//      the vehicle moves rather than after (review §4).
//
// In every rejecting case the gateway commands zero velocity, which holds the vehicle while a
// recovery-mode switch is pending (SPEC FM-7).
#pragma once

#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
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

// Envelope of the forwarded setpoint. Defaults are conservative multirotor values; the flight values
// must be consistent with the PX4 limits (MPC_XY_VEL_MAX, MPC_Z_VEL_MAX_UP/DN, MPC_YAWRAUTO_MAX) and
// with the braking model of the geofence predictor (ADR 0004).
struct GatewayLimits
{
  double max_speed_h_m_s{5.0};
  double max_climb_rate_m_s{3.0};
  double max_descent_rate_m_s{2.0};
  double max_yaw_rate_rad_s{1.0};
  double future_stamp_tolerance_s{0.05};
};

// Shadow check applied to the proposed velocity before forwarding. Implementations must be
// allocation-free and bounded in time: this runs in the setpoint callback.
class SetpointGuard
{
public:
  virtual ~SetpointGuard() = default;
  virtual bool admissible(const std::array<float, 3> & velocity_ned_m_s, double t_s) const noexcept = 0;
};

class GatewayLogic
{
public:
  GatewayLogic(double cf_setpoint_timeout_s, const GatewayLimits & limits) noexcept
  : timeout_s_(cf_setpoint_timeout_s), limits_(limits) {}

  explicit GatewayLogic(double cf_setpoint_timeout_s) noexcept
  : GatewayLogic(cf_setpoint_timeout_s, GatewayLimits{}) {}

  // The guard outlives the gateway; nullptr disables the shadow check.
  void setGuard(const SetpointGuard * guard) noexcept {guard_ = guard;}

  // `t_s` is the gateway clock.
  void onCoreState(State state, double t_s) noexcept
  {
    if (state == State::kCf && state_ != State::kCf) {
      t_enter_cf_s_ = t_s;
      yaw_cmd_rad_ = std::numeric_limits<double>::quiet_NaN();
      t_yaw_s_ = std::numeric_limits<double>::quiet_NaN();
    }
    state_ = state;
  }

  // `t_recv_s` is the reception instant on the gateway clock; `stamp_s` is the CF-supplied stamp and
  // is used only for the plausibility test.
  void onCfSetpoint(double t_recv_s, double stamp_s, const std::array<float, 3> & velocity,
    float yaw) noexcept
  {
    for (float v : velocity) {
      if (!std::isfinite(v)) {
        ++rejected_non_finite_;
        return;
      }
    }
    if (!std::isfinite(stamp_s) || !std::isfinite(t_recv_s) ||
      stamp_s > t_recv_s + limits_.future_stamp_tolerance_s ||
      t_recv_s - stamp_s > timeout_s_)
    {
      // A stamp ahead of the gateway clock, or already older than the timeout when it arrives,
      // describes a setpoint the gateway cannot age correctly.
      ++rejected_implausible_stamp_;
      return;
    }
    cf_velocity_ = clamp(velocity);
    cf_yaw_rad_ = (std::isfinite(yaw) && std::fabs(static_cast<double>(yaw)) <= kPi + 1e-3) ?
      static_cast<double>(yaw) : std::numeric_limits<double>::quiet_NaN();
    if (std::isfinite(yaw) && !std::isfinite(cf_yaw_rad_)) {
      ++rejected_yaw_;
    }
    t_recv_s_ = t_recv_s;
    have_cf_ = true;
  }

  GatewaySetpoint compute(double t_s) noexcept
  {
    GatewaySetpoint out;
    const bool fresh = have_cf_ && t_recv_s_ > t_enter_cf_s_ && t_s - t_recv_s_ <= timeout_s_;
    if (state_ != State::kCf || !fresh) {
      return out;
    }
    if (guard_ != nullptr && !guard_->admissible(cf_velocity_, t_s)) {
      ++rejected_by_guard_;
      return out;
    }
    out.velocity_ned_m_s = cf_velocity_;
    out.yaw_ned_rad = slewYaw(t_s);
    out.forwarding_cf = true;
    return out;
  }

  std::uint32_t rejectedNonFinite() const noexcept {return rejected_non_finite_;}
  std::uint32_t rejectedImplausibleStamp() const noexcept {return rejected_implausible_stamp_;}
  std::uint32_t rejectedYaw() const noexcept {return rejected_yaw_;}
  std::uint32_t rejectedByGuard() const noexcept {return rejected_by_guard_;}
  std::uint32_t clamped() const noexcept {return clamped_;}

private:
  static constexpr double kPi = 3.14159265358979323846;

  std::array<float, 3> clamp(const std::array<float, 3> & v) noexcept
  {
    std::array<float, 3> out = v;
    bool changed = false;
    const double speed = std::hypot(static_cast<double>(v[0]), static_cast<double>(v[1]));
    if (speed > limits_.max_speed_h_m_s && speed > 0.0) {
      const double scale = limits_.max_speed_h_m_s / speed;
      out[0] = static_cast<float>(static_cast<double>(v[0]) * scale);
      out[1] = static_cast<float>(static_cast<double>(v[1]) * scale);
      changed = true;
    }
    // NED: negative z is upwards.
    const double vz = static_cast<double>(v[2]);
    const double vz_clamped = std::clamp(vz, -limits_.max_climb_rate_m_s,
      limits_.max_descent_rate_m_s);
    if (vz_clamped != vz) {
      out[2] = static_cast<float>(vz_clamped);
      changed = true;
    }
    if (changed) {
      ++clamped_;
    }
    return out;
  }

  // Limits the commanded heading change to max_yaw_rate_rad_s. The first accepted yaw after entering
  // CF is adopted as is; afterwards the command follows the request at the bounded rate.
  float slewYaw(double t_s) noexcept
  {
    if (!std::isfinite(cf_yaw_rad_)) {
      yaw_cmd_rad_ = std::numeric_limits<double>::quiet_NaN();
      t_yaw_s_ = t_s;
      return std::numeric_limits<float>::quiet_NaN();
    }
    if (!std::isfinite(yaw_cmd_rad_) || !std::isfinite(t_yaw_s_)) {
      yaw_cmd_rad_ = cf_yaw_rad_;
    } else {
      const double dt = std::max(0.0, t_s - t_yaw_s_);
      const double max_step = limits_.max_yaw_rate_rad_s * dt;
      double error = cf_yaw_rad_ - yaw_cmd_rad_;
      while (error > kPi) {error -= 2.0 * kPi;}
      while (error < -kPi) {error += 2.0 * kPi;}
      yaw_cmd_rad_ += std::clamp(error, -max_step, max_step);
      while (yaw_cmd_rad_ > kPi) {yaw_cmd_rad_ -= 2.0 * kPi;}
      while (yaw_cmd_rad_ < -kPi) {yaw_cmd_rad_ += 2.0 * kPi;}
    }
    t_yaw_s_ = t_s;
    return static_cast<float>(yaw_cmd_rad_);
  }

  double timeout_s_;
  GatewayLimits limits_;
  const SetpointGuard * guard_{nullptr};
  State state_{State::kInactive};
  double t_enter_cf_s_{std::numeric_limits<double>::infinity()};
  bool have_cf_{false};
  double t_recv_s_{-std::numeric_limits<double>::infinity()};
  std::array<float, 3> cf_velocity_{0.0F, 0.0F, 0.0F};
  double cf_yaw_rad_{std::numeric_limits<double>::quiet_NaN()};
  double yaw_cmd_rad_{std::numeric_limits<double>::quiet_NaN()};
  double t_yaw_s_{std::numeric_limits<double>::quiet_NaN()};
  std::uint32_t rejected_non_finite_{0};
  std::uint32_t rejected_implausible_stamp_{0};
  std::uint32_t rejected_yaw_{0};
  std::uint32_t rejected_by_guard_{0};
  std::uint32_t clamped_{0};
};

}  // namespace guara_rta
