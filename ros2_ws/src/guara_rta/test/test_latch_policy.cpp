// SPDX-License-Identifier: Apache-2.0
//
// AC-13 (property P-4): after N_max CF->RF switches inside the window W the recovery is latched and
// no further return occurs until the executor loses charge; in any window of length W the number of
// CF->RF switches never exceeds N_max (SPEC §3.5, ADR 0005 item 3).
#include <gtest/gtest.h>

#include <cmath>
#include <cstdint>
#include <deque>
#include <limits>
#include <random>

#include "guara_rta/decision_core.hpp"

namespace guara_rta
{
namespace
{

constexpr double kTs = 0.05;
constexpr double kInf = std::numeric_limits<double>::infinity();

std::uint64_t ticksFor(double seconds) {return static_cast<std::uint64_t>(std::llround(seconds / kTs));}

// Drives a fixed unsafe/clear cycle of period `period_s` (unsafe during the first tick).
struct CycleDriver
{
  Parameters p;
  DecisionCore core;
  std::uint64_t k{0};

  explicit CycleDriver(const Parameters & params)
  : p(params), core(params) {}

  Output tick(bool unsafe, bool in_charge = true)
  {
    Inputs in;
    in.t_s = static_cast<double>(k++) * kTs;
    in.in_charge = in_charge;
    in.owned_mode_active = true;
    in.t_gf_s = unsafe ? 0.0 : kInf;
    return core.step(in);
  }
};

TEST(LatchPolicy, LatchesAfterNmaxSwitchesInsideWindow)
{
  const Parameters p{};  // N_max = 3, W = 120 s, T_d = 5 s
  CycleDriver d(p);
  int switches = 0;
  bool latched = false;
  double t_latch = -1.0;
  const std::uint64_t cycle = ticksFor(10.0);  // unsafe tick, then clear: return after T_d
  for (std::uint64_t k = 0; k < ticksFor(119.0); ++k) {
    const Output out = d.tick((k % cycle) == 0U);
    if (out.transition.id == transition::kT3 || out.transition.id == transition::kT2b) {
      ++switches;
    }
    if (out.transition.id == transition::kT4) {
      latched = true;
      t_latch = static_cast<double>(k) * kTs;
      EXPECT_NE(out.transition.cause & cause::kLatch, 0U);
    }
    if (latched) {
      EXPECT_EQ(out.state, State::kLatched) << "t=" << static_cast<double>(k) * kTs;
      EXPECT_NE(out.command, Command::kOwnedMode);
    }
  }
  EXPECT_TRUE(latched);
  EXPECT_EQ(switches, p.n_max);
  EXPECT_NEAR(t_latch, 20.0 + kTs, 1e-9);  // third switch at t = 20 s, latch at the next tick
}

TEST(LatchPolicy, LatchedStateSurvivesLongClearPeriodsAndClearsOnlyWhenNotInCharge)
{
  const Parameters p{};
  CycleDriver d(p);
  const std::uint64_t cycle = ticksFor(10.0);
  for (std::uint64_t k = 0; k < ticksFor(30.0); ++k) {
    d.tick((k % cycle) == 0U);
  }
  ASSERT_EQ(d.core.state(), State::kLatched);
  for (std::uint64_t k = 0; k < ticksFor(600.0); ++k) {
    EXPECT_EQ(d.tick(false).state, State::kLatched);
  }
  const Output released = d.tick(false, false);
  EXPECT_EQ(released.state, State::kInactive);
  EXPECT_EQ(released.transition.id, transition::kT1);
}

TEST(LatchPolicy, SwitchesSpreadBeyondWindowDoNotLatch)
{
  const Parameters p{};
  CycleDriver d(p);
  const std::uint64_t cycle = ticksFor(61.0);  // at most two switches inside any 120 s window
  for (std::uint64_t k = 0; k < ticksFor(1200.0); ++k) {
    const Output out = d.tick((k % cycle) == 0U);
    ASSERT_NE(out.state, State::kLatched) << "t=" << static_cast<double>(k) * kTs;
  }
}

TEST(LatchPolicy, EscalationIsPermittedWhileLatched)
{
  const Parameters p{};
  DecisionCore core(p);
  std::uint64_t k = 0;
  const auto step = [&core, &k](double t_gf, bool m, Recovery action) {
      Inputs in;
      in.t_s = static_cast<double>(k++) * kTs;
      in.in_charge = true;
      in.owned_mode_active = true;
      in.t_gf_s = t_gf;
      in.monitor_violation = m;
      in.monitor_action = action;
      return core.step(in);
    };
  const std::uint64_t cycle = ticksFor(10.0);
  for (std::uint64_t i = 0; i < ticksFor(25.0); ++i) {
    step((i % cycle) == 0U ? 0.0 : kInf, false, Recovery::kHold);
  }
  ASSERT_EQ(core.state(), State::kLatched);
  ASSERT_EQ(core.recovery(), Recovery::kHold);
  const Output out = step(kInf, true, Recovery::kLand);
  EXPECT_EQ(out.transition.id, transition::kT7);
  EXPECT_EQ(out.state, State::kLatched);
  EXPECT_EQ(out.recovery, Recovery::kLand);
  EXPECT_EQ(out.command, Command::kLand);
  // Rank never decreases.
  const Output lower = step(0.0, true, Recovery::kRtl);
  EXPECT_EQ(lower.recovery, Recovery::kLand);
  EXPECT_EQ(lower.command, Command::kNone);
}

TEST(LatchPolicy, RandomisedSwitchCountInAnyWindowNeverExceedsNmax)
{
  Parameters p{};
  p.dwell_s = 0.5;  // short dwell to maximise switching opportunities
  p.h_gf_s = 0.0;
  DecisionCore core(p);
  std::mt19937_64 rng(42);
  std::bernoulli_distribution unsafe(0.2);
  std::deque<double> recent;
  std::size_t max_in_window = 0;
  for (std::uint64_t k = 0; k < 2000000; ++k) {
    Inputs in;
    in.t_s = static_cast<double>(k) * kTs;
    // Rare loss of charge resets the latch, so the run revisits the switching regime.
    in.in_charge = (k % 20000U) != 0U;
    in.owned_mode_active = true;
    in.t_gf_s = unsafe(rng) ? 0.0 : kInf;
    const Output out = core.step(in);
    if (out.transition.id == transition::kT1) {
      recent.clear();  // the window property is stated per activation of the executor
    }
    if (out.transition.id == transition::kT3 || out.transition.id == transition::kT2b) {
      recent.push_back(in.t_s);
    }
    while (!recent.empty() && recent.front() <= in.t_s - p.window_s) {
      recent.pop_front();
    }
    max_in_window = std::max(max_in_window, recent.size());
  }
  std::printf("[latch_policy] max CF->RF switches in any %.0f s window: %zu (N_max=%u)\n",
    p.window_s, max_in_window, static_cast<unsigned>(p.n_max));
  EXPECT_LE(max_in_window, p.n_max);
  EXPECT_EQ(max_in_window, p.n_max) << "run did not reach the latch condition";
}

}  // namespace
}  // namespace guara_rta
