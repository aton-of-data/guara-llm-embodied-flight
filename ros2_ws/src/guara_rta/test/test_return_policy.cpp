// SPDX-License-Identifier: Apache-2.0
//
// Return and latch policy against an adversarial Complex Function (review 2026-09-11 §4: "Latch
// bypass" and "Return ignores the CF's intent").
//
//  * The switch history is the anti-chattering budget of SPEC §3.5. Resetting it on T1 lets any
//    agent that can select modes — a pilot, or an LLM with a mode tool — clear N_max by leaving and
//    re-entering the owned mode, so the budget is now kept across T1 and only decays with the
//    window W.
//  * T5 hands control back to the CF that caused the recovery. A stopped vehicle is always "clear",
//    so the return is now additionally conditioned on the CF's *proposed* motion being clear
//    (cf_intent_unsafe), which the arbiter evaluates with the geofence predictor before returning.
#include <cmath>
#include <limits>

#include <gtest/gtest.h>

#include "guara_rta/decision_core.hpp"

namespace guara_rta
{
namespace
{

constexpr double kTs = 0.05;
constexpr double kInf = std::numeric_limits<double>::infinity();

struct Driver
{
  DecisionCore core;
  double t{0.0};

  explicit Driver(const Parameters & p)
  : core(p) {}

  Output tick(bool unsafe, bool in_charge = true, bool cf_intent_unsafe = false)
  {
    Inputs in;
    in.t_s = t;
    t += kTs;
    in.in_charge = in_charge;
    in.owned_mode_active = true;
    in.t_gf_s = unsafe ? 0.0 : kInf;
    in.cf_intent_unsafe = cf_intent_unsafe;
    return core.step(in);
  }

  // Runs `seconds` of clear ticks and returns true if a T5 return occurred.
  bool runClear(double seconds, bool cf_intent_unsafe = false)
  {
    bool returned = false;
    const auto ticks = static_cast<int>(seconds / kTs);
    for (int i = 0; i < ticks; ++i) {
      if (tick(false, true, cf_intent_unsafe).transition.id == transition::kT5) {
        returned = true;
      }
    }
    return returned;
  }
};

// The CF->RF switch budget survives a loss and reacquisition of charge.
TEST(ReturnPolicy, SwitchHistorySurvivesLossOfCharge)
{
  Parameters p{};
  p.n_max = 2;
  Driver d(p);
  d.tick(false);
  ASSERT_EQ(transition::kT3, d.tick(true).transition.id);  // first CF->RF switch
  ASSERT_TRUE(d.runClear(6.0));                            // T5 back to CF

  d.tick(false, /*in_charge=*/false);                      // T1: pilot takes over
  d.tick(false);                                           // T2: arbiter back in charge
  const Output out = d.tick(true);                         // second switch reaches N_max
  EXPECT_EQ(transition::kT3, out.transition.id);
  EXPECT_EQ(2U, out.switches_in_window) << "T1 must not clear the anti-chattering budget";
  bool latched = false;
  for (int i = 0; i < 40; ++i) {
    if (d.tick(false).transition.id == transition::kT4) {
      latched = true;
    }
  }
  EXPECT_TRUE(latched) << "N_max switches inside W must latch even across T1";
}

// Entries older than the window still decay, so the budget is not a permanent penalty.
TEST(ReturnPolicy, SwitchHistoryDecaysWithTheWindow)
{
  Parameters p{};
  p.n_max = 2;
  p.window_s = 10.0;
  Driver d(p);
  d.tick(false);
  ASSERT_EQ(transition::kT3, d.tick(true).transition.id);
  ASSERT_TRUE(d.runClear(6.0));
  d.runClear(12.0);  // the first switch leaves the window
  const Output out = d.tick(true);
  EXPECT_EQ(transition::kT3, out.transition.id);
  EXPECT_EQ(1U, out.switches_in_window);
}

// T5 is withheld while the CF's proposed setpoint would re-enter the unsafe set.
TEST(ReturnPolicy, ReturnIsWithheldWhileTheCfIntentIsUnsafe)
{
  Parameters p{};
  Driver d(p);
  d.tick(false);
  ASSERT_EQ(transition::kT3, d.tick(true).transition.id);
  EXPECT_FALSE(d.runClear(20.0, /*cf_intent_unsafe=*/true))
    << "a vehicle stopped at the fence is clear, but the CF still wants to fly into it";
  EXPECT_TRUE(d.runClear(6.0, /*cf_intent_unsafe=*/false));
}

// The CF's intent alone never forces a recovery: while the vehicle is in CF the gateway filters the
// setpoint, so cf_intent_unsafe must not by itself trigger T3 and consume the switch budget.
TEST(ReturnPolicy, CfIntentAloneDoesNotSwitch)
{
  Parameters p{};
  Driver d(p);
  d.tick(false);
  const Output out = d.tick(false, true, /*cf_intent_unsafe=*/true);
  EXPECT_EQ(transition::kNone, out.transition.id);
  EXPECT_EQ(State::kCf, out.state);
}

}  // namespace
}  // namespace guara_rta
