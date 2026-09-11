// SPDX-License-Identifier: Apache-2.0
//
// Mode-request acknowledgement and effect confirmation (review 2026-09-11 §4 "Mode effect not
// confirmed"). VehicleCommandAck only says that PX4 accepted the command; it does not say that the
// vehicle is in the requested mode. A recovery that is accepted and then silently overridden left
// the arbiter believing the vehicle was in Hold. The actuator now confirms the *effect* on
// vehicle_status.nav_state within a bounded time and reports a failure otherwise, which the core
// converts into the FM-7 actuation latch.
#include <gtest/gtest.h>

#include "guara_rta/actuator_logic.hpp"

namespace guara_rta
{
namespace
{

constexpr std::uint8_t kNavLoiter = 4;
constexpr std::uint8_t kNavRtl = 5;

ActuatorParameters params()
{
  ActuatorParameters p;
  p.retry_period_s = 0.3;
  p.n_retry = 3;
  p.confirm_timeout_s = 1.0;
  return p;
}

TEST(ActuatorConfirmation, AcceptedAndConfirmedRequestCompletes)
{
  ActuatorLogic a(params());
  a.request(Command::kHold, kNavLoiter, 0.0);
  EXPECT_EQ(ActuatorAction::kPublish, a.tick(0.0));
  a.onAck(Command::kHold, true, 0.1);
  a.onNavState(kNavLoiter, 0.2);
  for (double t = 0.3; t < 5.0; t += 0.1) {
    EXPECT_EQ(ActuatorAction::kIdle, a.tick(t)) << t;
  }
}

// An accepted acknowledgement that never takes effect must not be reported as success.
TEST(ActuatorConfirmation, AcceptedButNotEffectiveFails)
{
  ActuatorLogic a(params());
  a.request(Command::kHold, kNavLoiter, 0.0);
  ASSERT_EQ(ActuatorAction::kPublish, a.tick(0.0));
  a.onAck(Command::kHold, true, 0.1);
  a.onNavState(kNavRtl, 0.2);  // some other authority switched the mode
  bool failed = false;
  for (double t = 0.3; t < 3.0; t += 0.1) {
    failed = failed || a.tick(t) == ActuatorAction::kFailed;
  }
  EXPECT_TRUE(failed);
}

// The failure is reported once, so the caller latches once.
TEST(ActuatorConfirmation, FailureIsReportedOnce)
{
  ActuatorLogic a(params());
  a.request(Command::kRtl, kNavRtl, 0.0);
  ASSERT_EQ(ActuatorAction::kPublish, a.tick(0.0));
  a.onAck(Command::kRtl, true, 0.1);
  int failures = 0;
  for (double t = 0.2; t < 5.0; t += 0.1) {
    failures += a.tick(t) == ActuatorAction::kFailed ? 1 : 0;
  }
  EXPECT_EQ(1, failures);
}

// A newer request replaces the confirmation target: an escalation from Hold to RTL is not failed by
// the pending Hold confirmation.
TEST(ActuatorConfirmation, NewRequestReplacesTheConfirmationTarget)
{
  ActuatorLogic a(params());
  a.request(Command::kHold, kNavLoiter, 0.0);
  ASSERT_EQ(ActuatorAction::kPublish, a.tick(0.0));
  a.onAck(Command::kHold, true, 0.1);
  a.request(Command::kRtl, kNavRtl, 0.2);
  EXPECT_EQ(ActuatorAction::kPublish, a.tick(0.2));
  a.onAck(Command::kRtl, true, 0.3);
  a.onNavState(kNavRtl, 0.4);
  for (double t = 0.5; t < 3.0; t += 0.1) {
    EXPECT_EQ(ActuatorAction::kIdle, a.tick(t)) << t;
  }
}

// Retries and the publication budget are unchanged (SPEC FM-7).
TEST(ActuatorConfirmation, RetryBudgetIsUnchanged)
{
  ActuatorLogic a(params());
  a.request(Command::kHold, kNavLoiter, 0.0);
  int publications = 0;
  bool failed = false;
  for (double t = 0.0; t < 3.0; t += 0.1) {
    const ActuatorAction action = a.tick(t);
    publications += action == ActuatorAction::kPublish ? 1 : 0;
    failed = failed || action == ActuatorAction::kFailed;
  }
  EXPECT_EQ(3, publications);
  EXPECT_TRUE(failed);
}

}  // namespace
}  // namespace guara_rta
