// SPDX-License-Identifier: Apache-2.0
//
// Gateway defences against an untrusted Complex Function (review 2026-09-11 H-1, H-2 and §5 item 3).
// The CF is adversarial by assumption (SPEC §2; docs/research/LLM-EMBODIMENT.md §4): it controls the
// content of every field of CfSetpoint, including the stamp. The gateway therefore measures
// freshness on its own clock, rejects stamps that are not plausible, keeps the commanded motion
// inside a configured envelope, and consults a shadow guard before forwarding.
#include <array>
#include <cmath>
#include <limits>

#include <gtest/gtest.h>

#include "guara_rta/gateway_logic.hpp"

namespace
{

using guara_rta::GatewayLimits;
using guara_rta::GatewayLogic;
using guara_rta::GatewaySetpoint;
using guara_rta::SetpointGuard;
using guara_rta::State;

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

// Enters CF at t = 0 and returns a gateway ready to forward.
GatewayLogic makeGateway(double timeout_s = 0.5)
{
  GatewayLogic g(timeout_s, limits());
  g.onCoreState(State::kCf, 0.0);
  return g;
}

class RejectingGuard : public SetpointGuard
{
public:
  bool admissible(const std::array<float, 3> &, double) const noexcept override {return false;}
};

// H-1: a CF that stamps a setpoint in the future and then dies must not keep the vehicle moving.
TEST(GatewayEnvelope, FutureStampDoesNotDefeatTheLivenessTimeout)
{
  GatewayLogic g = makeGateway(0.5);
  // Received at t = 1.0 s but stamped 100 s ahead.
  g.onCfSetpoint(1.0, 101.0, {1.0F, 0.0F, 0.0F}, NAN);
  EXPECT_FALSE(g.compute(1.0).forwarding_cf) << "an implausible future stamp must be rejected";
  EXPECT_EQ(1U, g.rejectedImplausibleStamp());

  // Same setpoint stamped honestly is forwarded, and expires one timeout after reception.
  g.onCfSetpoint(1.0, 1.0, {1.0F, 0.0F, 0.0F}, NAN);
  EXPECT_TRUE(g.compute(1.2).forwarding_cf);
  const GatewaySetpoint expired = g.compute(1.6);
  EXPECT_FALSE(expired.forwarding_cf);
  EXPECT_FLOAT_EQ(0.0F, expired.velocity_ned_m_s[0]);
}

// H-1: freshness is measured from reception, not from the CF clock, so a slow CF clock cannot
// extend the forwarding window either.
TEST(GatewayEnvelope, AgeIsMeasuredFromReception)
{
  GatewayLogic g = makeGateway(0.5);
  g.onCfSetpoint(1.0, 0.9, {2.0F, 0.0F, 0.0F}, NAN);
  EXPECT_TRUE(g.compute(1.4).forwarding_cf);
  EXPECT_FALSE(g.compute(1.55).forwarding_cf);
}

// A setpoint received before the most recent entry into CF is never forwarded; the ordering rule
// uses the reception instant (trusted) rather than the CF-supplied stamp.
TEST(GatewayEnvelope, SetpointReceivedBeforeEntryIsDiscarded)
{
  GatewayLogic g(0.5, limits());
  g.onCoreState(State::kRf, 0.0);
  g.onCfSetpoint(1.0, 1.0, {2.0F, 0.0F, 0.0F}, NAN);  // stamped and received while in RF
  g.onCoreState(State::kCf, 1.1);
  EXPECT_FALSE(g.compute(1.2).forwarding_cf);
}

// H-2: horizontal speed, climb and descent rates are clamped to the configured envelope.
TEST(GatewayEnvelope, VelocityIsClampedToTheEnvelope)
{
  GatewayLogic g = makeGateway();
  g.onCfSetpoint(1.0, 1.0, {30.0F, 40.0F, -20.0F}, NAN);  // 50 m/s horizontal, 20 m/s climb
  const GatewaySetpoint sp = g.compute(1.0);
  ASSERT_TRUE(sp.forwarding_cf);
  const double speed = std::hypot(sp.velocity_ned_m_s[0], sp.velocity_ned_m_s[1]);
  EXPECT_NEAR(5.0, speed, 1e-5);
  EXPECT_NEAR(0.6, sp.velocity_ned_m_s[0] / speed, 1e-5) << "direction must be preserved";
  EXPECT_NEAR(-3.0, sp.velocity_ned_m_s[2], 1e-5) << "climb clamped to max_climb_rate_m_s";
  EXPECT_EQ(1U, g.clamped());

  g.onCfSetpoint(2.0, 2.0, {0.0F, 0.0F, 9.0F}, NAN);  // descent
  EXPECT_NEAR(2.0, g.compute(2.0).velocity_ned_m_s[2], 1e-5);
}

// H-2: non-finite components are rejected outright (no clamping of NaN into a number).
TEST(GatewayEnvelope, NonFiniteIsRejected)
{
  GatewayLogic g = makeGateway();
  g.onCfSetpoint(1.0, 1.0, {NAN, 0.0F, 0.0F}, NAN);
  EXPECT_FALSE(g.compute(1.0).forwarding_cf);
  g.onCfSetpoint(1.0, 1.0, {0.0F, std::numeric_limits<float>::infinity(), 0.0F}, NAN);
  EXPECT_FALSE(g.compute(1.0).forwarding_cf);
  EXPECT_EQ(2U, g.rejectedNonFinite());
}

// H-2: yaw is slewed at most at max_yaw_rate_rad_s, so a CF cannot command a step in heading.
TEST(GatewayEnvelope, YawIsRateLimited)
{
  GatewayLogic g = makeGateway();
  g.onCfSetpoint(1.0, 1.0, {0.0F, 0.0F, 0.0F}, 0.0F);
  EXPECT_NEAR(0.0, g.compute(1.0).yaw_ned_rad, 1e-5);
  g.onCfSetpoint(1.1, 1.1, {0.0F, 0.0F, 0.0F}, 3.0F);
  // 0.1 s at 1 rad/s from yaw 0.
  EXPECT_NEAR(0.1, g.compute(1.1).yaw_ned_rad, 1e-3);
  EXPECT_NEAR(0.6, g.compute(1.6).yaw_ned_rad, 1e-3);
}

// A yaw command outside [-pi, pi] or non-finite leaves yaw uncontrolled instead of being forwarded.
TEST(GatewayEnvelope, OutOfRangeYawLeavesYawUncontrolled)
{
  GatewayLogic g = makeGateway();
  g.onCfSetpoint(1.0, 1.0, {1.0F, 0.0F, 0.0F}, 40.0F);
  const GatewaySetpoint sp = g.compute(1.0);
  EXPECT_TRUE(sp.forwarding_cf);
  EXPECT_TRUE(std::isnan(sp.yaw_ned_rad));
}

// Review §4 "Return ignores the CF's intent": a setpoint the shadow guard rejects is replaced by
// zero velocity, so an aggressive or hallucinating planner is filtered before the vehicle moves.
TEST(GatewayEnvelope, ShadowGuardBlocksTheSetpoint)
{
  RejectingGuard guard;
  GatewayLogic g(0.5, limits());
  g.setGuard(&guard);
  g.onCoreState(State::kCf, 0.0);
  g.onCfSetpoint(1.0, 1.0, {4.0F, 0.0F, 0.0F}, NAN);
  const GatewaySetpoint sp = g.compute(1.0);
  EXPECT_FALSE(sp.forwarding_cf);
  EXPECT_FLOAT_EQ(0.0F, sp.velocity_ned_m_s[0]);
  EXPECT_EQ(1U, g.rejectedByGuard());
}

}  // namespace
