// SPDX-License-Identifier: Apache-2.0
//
// AC-21 (SPEC FM-7): with an actuator whose mode requests are never acknowledged, the gateway
// commands zero velocity from the tick of transition T3 onwards and discards every CF setpoint; after
// the retry budget is exhausted the recovery is latched. The arbiter tick loop is reproduced here
// without ROS: DecisionCore -> ActuatorLogic -> GatewayLogic, sampled at T_s.
#include <gtest/gtest.h>

#include <array>
#include <cmath>
#include <cstdint>
#include <limits>

#include "guara_rta/actuator_logic.hpp"
#include "guara_rta/decision_core.hpp"
#include "guara_rta/gateway_logic.hpp"
#include "guara_rta/input_manager.hpp"

namespace guara_rta
{
namespace
{

constexpr double kTs = 0.05;
constexpr double kCfTimeout = 0.5;
const std::array<float, 3> kCfVelocity{3.0F, -1.0F, -0.5F};

bool isZero(const GatewaySetpoint & sp)
{
  return sp.velocity_ned_m_s[0] == 0.0F && sp.velocity_ned_m_s[1] == 0.0F &&
         sp.velocity_ned_m_s[2] == 0.0F && !sp.forwarding_cf;
}

struct Arbiter
{
  DecisionCore core{Parameters{}};
  ActuatorLogic actuator{ActuatorParameters{}};
  GatewayLogic gateway{kCfTimeout};
  int latch_events{0};

  // One arbiter tick followed by one gateway update, as ordered in the node.
  GatewaySetpoint tick(double t, bool unsafe, bool ack_available)
  {
    Inputs in;
    in.t_s = t;
    in.in_charge = true;
    in.owned_mode_active = true;
    in.monitor_violation = unsafe;
    const Output out = core.step(in);
    actuator.request(out.command, t);
    const ActuatorAction action = actuator.tick(t);
    if (action == ActuatorAction::kPublish && ack_available) {
      actuator.onAck(actuator.pending(), true, t);
    }
    if (action == ActuatorAction::kFailed) {
      if (core.latchOnActuationFailure(t).transition.id == transition::kActuationLatch) {
        ++latch_events;
      }
    }
    gateway.onCoreState(core.state(), t);
    // The CF keeps publishing at every tick, stamped with the current time.
    gateway.onCfSetpoint(t, kCfVelocity, 0.0F);
    return gateway.compute(t);
  }
};

TEST(GatewayBlocksCf, ZeroVelocityFromT3TickWithUnacknowledgedActuator)
{
  Arbiter a;
  // Nominal flight in CF for 1 s: the CF setpoint is forwarded.
  for (int k = 0; k < 20; ++k) {
    const GatewaySetpoint sp = a.tick(k * kTs, false, true);
    if (k > 0) {
      EXPECT_TRUE(sp.forwarding_cf) << "k=" << k;
      EXPECT_EQ(sp.velocity_ned_m_s, kCfVelocity);
    }
  }
  ASSERT_EQ(a.core.state(), State::kCf);

  // T3 at k = 20; the actuator never receives an acknowledgement afterwards.
  const GatewaySetpoint at_t3 = a.tick(20 * kTs, true, false);
  EXPECT_EQ(a.core.state(), State::kRf);
  EXPECT_TRUE(isZero(at_t3)) << "gateway forwarded CF in the T3 tick";

  bool latched = false;
  for (int k = 21; k < 200; ++k) {
    const GatewaySetpoint sp = a.tick(k * kTs, k < 25, false);
    EXPECT_TRUE(isZero(sp)) << "k=" << k;
    latched = latched || a.core.state() == State::kLatched;
  }
  EXPECT_TRUE(latched) << "retry budget exhaustion did not latch the recovery";
  EXPECT_EQ(a.latch_events, 1);
  EXPECT_EQ(a.core.state(), State::kLatched);
}

TEST(GatewayBlocksCf, SetpointsStampedBeforeReturnAreDiscarded)
{
  GatewayLogic gateway(kCfTimeout);
  gateway.onCoreState(State::kCf, 0.0);
  gateway.onCfSetpoint(0.1, kCfVelocity, 0.0F);
  EXPECT_TRUE(gateway.compute(0.1).forwarding_cf);

  gateway.onCoreState(State::kRf, 1.0);
  EXPECT_FALSE(gateway.compute(1.0).forwarding_cf);

  // A setpoint generated during RF is still buffered when the core returns to CF at t = 6.0.
  gateway.onCfSetpoint(5.9, kCfVelocity, 0.0F);
  gateway.onCoreState(State::kCf, 6.0);
  EXPECT_TRUE(isZero(gateway.compute(6.0)));
  gateway.onCfSetpoint(6.05, kCfVelocity, 0.0F);
  EXPECT_TRUE(gateway.compute(6.05).forwarding_cf);
}

TEST(GatewayBlocksCf, StaleAndNonFiniteCfSetpointsAreNotForwarded)
{
  GatewayLogic gateway(kCfTimeout);
  gateway.onCoreState(State::kCf, 0.0);
  gateway.onCfSetpoint(0.1, kCfVelocity, 0.0F);
  EXPECT_TRUE(gateway.compute(0.5).forwarding_cf);
  EXPECT_TRUE(isZero(gateway.compute(0.1 + kCfTimeout + 0.01)));

  const float nan = std::numeric_limits<float>::quiet_NaN();
  gateway.onCfSetpoint(1.0, {nan, 0.0F, 0.0F}, 0.0F);
  EXPECT_TRUE(isZero(gateway.compute(1.0)));
}

TEST(GatewayBlocksCf, ActuatorRetriesAtRetryPeriodThenReportsFailureOnce)
{
  ActuatorParameters p;
  ActuatorLogic act(p);
  act.request(Command::kHold, 0.0);
  int publications = 0;
  int failures = 0;
  for (int k = 0; k < 100; ++k) {
    const ActuatorAction a = act.tick(k * kTs);
    publications += a == ActuatorAction::kPublish ? 1 : 0;
    failures += a == ActuatorAction::kFailed ? 1 : 0;
  }
  EXPECT_EQ(publications, p.n_retry);
  EXPECT_EQ(failures, 1);

  act.request(Command::kHold, 10.0);
  EXPECT_EQ(act.tick(10.0), ActuatorAction::kPublish);
  act.onAck(Command::kRtl, true, 10.01);  // acknowledgement of a different request is ignored
  EXPECT_EQ(act.pending(), Command::kHold);
  act.onAck(Command::kHold, true, 10.02);
  EXPECT_EQ(act.pending(), Command::kNone);
  EXPECT_EQ(act.tick(11.0), ActuatorAction::kIdle);
}

TEST(InputManager, MissingStaleAndInvalidRequiredChannelsSetMask)
{
  InputManager::Config cfg{};
  cfg[static_cast<std::size_t>(Channel::kLocalPosition)] = {true, 0.2};
  cfg[static_cast<std::size_t>(Channel::kDaa)] = {false, 1.0};
  InputManager im(cfg);
  const std::uint32_t lpos_bit = 1U << static_cast<unsigned>(Channel::kLocalPosition);

  EXPECT_EQ(im.invalidMask(0.0), lpos_bit);  // never received
  im.onReceive(Channel::kLocalPosition, 1.0, true);
  EXPECT_EQ(im.invalidMask(1.2), 0U);        // age = A_i is still valid
  EXPECT_EQ(im.invalidMask(1.2001), lpos_bit);
  im.onReceive(Channel::kLocalPosition, 1.3, false);
  EXPECT_EQ(im.invalidMask(1.3), lpos_bit);  // semantic invalidity
  EXPECT_EQ(im.invalidMask(100.0) & (1U << static_cast<unsigned>(Channel::kDaa)), 0U);
}

}  // namespace
}  // namespace guara_rta
