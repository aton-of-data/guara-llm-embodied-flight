// SPDX-License-Identifier: Apache-2.0
//
// Property test of the gateway against an adversarial Complex Function (RQ5, ADR 0010).
//
// The named cases in test_gateway_envelope.cpp cover the failure modes the review of 2026-09-11
// found. This test covers the space around them: a deterministic pseudo-random CF that emits
// NaN, infinities, extreme velocities, stamps in the past and in the future, replayed stamps and
// silences, against a guard that refuses at random instants. Whatever the CF does, four invariants
// must hold at every tick.
//
//   I1  A forwarded setpoint is always inside the configured envelope.
//   I2  Nothing is forwarded unless the core state is CF.
//   I3  Nothing is forwarded whose newest accepted sample is older than the timeout, or that was
//       received before the most recent entry into CF.
//   I4  Nothing is forwarded while the shadow guard refuses.
//
// Deterministic seed: a failure is reproducible from the printed seed.
#include <array>
#include <cmath>
#include <cstdint>
#include <limits>
#include <random>

#include <gtest/gtest.h>

#include "guara_rta/gateway_logic.hpp"

namespace guara_rta
{
namespace
{

constexpr double kTimeout = 0.5;
constexpr std::uint64_t kSeed = 20260911U;
constexpr int kTicks = 200000;

GatewayLimits limits()
{
  GatewayLimits l;
  l.max_speed_h_m_s = 5.0;
  l.max_climb_rate_m_s = 3.0;
  l.max_descent_rate_m_s = 2.0;
  l.max_yaw_rate_rad_s = 1.0;
  l.future_stamp_tolerance_s = 0.05;
  return l;
}

// Refuses on demand, and records every velocity it was asked about.
class SwitchableGuard : public SetpointGuard
{
public:
  bool refuse{false};
  mutable std::array<float, 3> last{0.0F, 0.0F, 0.0F};

  bool admissible(const std::array<float, 3> & v, double) const noexcept override
  {
    last = v;
    return !refuse;
  }
};

class HostileCf
{
public:
  explicit HostileCf(std::uint64_t seed)
  : rng_(seed) {}

  // One CF publication at gateway time t_s, or none.
  bool maybePublish(GatewayLogic & gateway, double t_s)
  {
    if (u_(rng_) < 0.25) {
      return false;  // the CF goes quiet
    }
    std::array<float, 3> v{value(), value(), value()};
    gateway.onCfSetpoint(t_s, stamp(t_s), v, yaw());
    return true;
  }

private:
  float value()
  {
    const double u = u_(rng_);
    if (u < 0.05) {return std::numeric_limits<float>::quiet_NaN();}
    if (u < 0.10) {return std::numeric_limits<float>::infinity();}
    if (u < 0.30) {return static_cast<float>(-1000.0 + 2000.0 * u_(rng_));}  // extreme
    return static_cast<float>(-4.0 + 8.0 * u_(rng_));                        // plausible
  }

  double stamp(double t_s)
  {
    const double u = u_(rng_);
    if (u < 0.10) {return t_s + 100.0 * u_(rng_);}          // future
    if (u < 0.20) {return t_s - 100.0 * u_(rng_);}          // ancient
    if (u < 0.25) {return std::numeric_limits<double>::quiet_NaN();}
    return t_s - 0.01 * u_(rng_);                           // honest
  }

  float yaw()
  {
    const double u = u_(rng_);
    if (u < 0.10) {return std::numeric_limits<float>::quiet_NaN();}
    if (u < 0.25) {return static_cast<float>(-100.0 + 200.0 * u_(rng_));}  // out of range
    return static_cast<float>(-3.14 + 6.28 * u_(rng_));
  }

  std::mt19937_64 rng_;
  std::uniform_real_distribution<double> u_{0.0, 1.0};
};

TEST(GatewayFuzz, InvariantsHoldAgainstAnAdversarialCf)
{
  std::mt19937_64 rng(kSeed);
  std::uniform_real_distribution<double> u(0.0, 1.0);
  SwitchableGuard guard;
  GatewayLogic gateway(kTimeout, limits());
  gateway.setGuard(&guard);

  State state = State::kInactive;
  double t = 0.0;
  double t_enter_cf = std::numeric_limits<double>::infinity();
  double t_last_accepted = -std::numeric_limits<double>::infinity();
  int forwarded = 0;

  for (int k = 0; k < kTicks; ++k) {
    t += 0.02;
    if (u(rng) < 0.01) {
      const State next = static_cast<State>(1U + (rng() % 3U));
      if (next == State::kCf && state != State::kCf) {
        t_enter_cf = t;
      }
      state = next;
      gateway.onCoreState(state, t);
    }
    guard.refuse = u(rng) < 0.2;

    const std::uint32_t rejected_before = gateway.rejectedNonFinite() +
      gateway.rejectedImplausibleStamp();
    if (HostileCf(kSeed + static_cast<std::uint64_t>(k)).maybePublish(gateway, t)) {
      const bool accepted = gateway.rejectedNonFinite() + gateway.rejectedImplausibleStamp() ==
        rejected_before;
      if (accepted) {
        t_last_accepted = t;
      }
    }

    const GatewaySetpoint sp = gateway.compute(t);
    if (!sp.forwarding_cf) {
      EXPECT_FLOAT_EQ(0.0F, sp.velocity_ned_m_s[0]) << "k=" << k;
      EXPECT_FLOAT_EQ(0.0F, sp.velocity_ned_m_s[1]) << "k=" << k;
      EXPECT_FLOAT_EQ(0.0F, sp.velocity_ned_m_s[2]) << "k=" << k;
      continue;
    }
    ++forwarded;

    // I1: inside the envelope, and always a number.
    const double speed = std::hypot(static_cast<double>(sp.velocity_ned_m_s[0]),
      static_cast<double>(sp.velocity_ned_m_s[1]));
    ASSERT_TRUE(std::isfinite(speed)) << "k=" << k;
    EXPECT_LE(speed, limits().max_speed_h_m_s + 1e-4) << "k=" << k;
    EXPECT_GE(sp.velocity_ned_m_s[2], -limits().max_climb_rate_m_s - 1e-4) << "k=" << k;
    EXPECT_LE(sp.velocity_ned_m_s[2], limits().max_descent_rate_m_s + 1e-4) << "k=" << k;
    EXPECT_TRUE(std::isnan(sp.yaw_ned_rad) || std::fabs(sp.yaw_ned_rad) <= 3.15) << "k=" << k;

    // I2, I3, I4.
    EXPECT_EQ(State::kCf, state) << "k=" << k;
    EXPECT_GT(t_last_accepted, t_enter_cf) << "k=" << k;
    EXPECT_LE(t - t_last_accepted, kTimeout + 1e-9) << "k=" << k;
    EXPECT_FALSE(guard.refuse) << "k=" << k;
  }

  // The generator must actually exercise the forwarding path, otherwise the invariants are vacuous.
  EXPECT_GT(forwarded, kTicks / 100) << "seed " << kSeed << " never forwarded a setpoint";
  std::cout << "[gateway_fuzz] seed=" << kSeed << " ticks=" << kTicks << " forwarded=" << forwarded
            << " rejected_stamp=" << gateway.rejectedImplausibleStamp()
            << " rejected_non_finite=" << gateway.rejectedNonFinite()
            << " rejected_guard=" << gateway.rejectedByGuard()
            << " clamped=" << gateway.clamped() << std::endl;
}

}  // namespace
}  // namespace guara_rta
