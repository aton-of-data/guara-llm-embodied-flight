// SPDX-License-Identifier: Apache-2.0
//
// AC-4: exhaustive single-tick truth table of the decision core.
//
// Every combination of pre-state, in-charge flag, owned-mode flag, quantised time signals, monitor
// verdict, input validity, dwell history and switch history is evaluated. Each outcome is compared
// with a reference model transcribed from the transition table of SPEC §3.5, and properties P-1, P-2
// and P-6 of SPEC §3.5 are asserted independently of the reference model.
#include <gtest/gtest.h>

#include <array>
#include <cmath>
#include <cstdint>
#include <limits>
#include <sstream>
#include <string>

#include "decision_core_test_peer.hpp"
#include "guara_rta/decision_core.hpp"

namespace guara_rta
{
namespace
{

constexpr double kInf = std::numeric_limits<double>::infinity();
constexpr double kNaN = std::numeric_limits<double>::quiet_NaN();
constexpr double kNow = 1000.0;
constexpr double kTs = 0.05;

// Quantisation of a time signal T relative to its threshold tau and hysteresis h.
enum class Level { kBelow, kAtThreshold, kBand, kAbove, kInfinite };
constexpr std::array<Level, 5> kLevels{
  Level::kBelow, Level::kAtThreshold, Level::kBand, Level::kAbove, Level::kInfinite};

double valueOf(Level level, double tau, double h)
{
  switch (level) {
    case Level::kBelow: return 0.5 * tau;
    case Level::kAtThreshold: return tau;
    case Level::kBand: return tau + 0.5 * h;
    case Level::kAbove: return tau + h + 1.0;
    case Level::kInfinite: return kInf;
  }
  return kNaN;
}

struct PreState
{
  State state;
  Recovery recovery;
};

constexpr std::array<PreState, 8> kPreStates{{
  {State::kInactive, Recovery::kNone},
  {State::kCf, Recovery::kNone},
  {State::kRf, Recovery::kHold},
  {State::kRf, Recovery::kRtl},
  {State::kRf, Recovery::kLand},
  {State::kLatched, Recovery::kHold},
  {State::kLatched, Recovery::kRtl},
  {State::kLatched, Recovery::kLand},
}};

// Dwell history: instant at which C became continuously true (NaN if C was false at k-1) and the
// instant of the last CF->RF switch.
struct DwellHistory
{
  double clear_since_s;
  double t_switch_s;
};

struct Expected
{
  State state;
  Recovery recovery;
  Command command;
  std::uint8_t transition;
};

// Reference model of one tick (SPEC §3.4-§3.5), one transition per tick, rows in table order.
Expected reference(
  const Parameters & p, const PreState & pre, const Inputs & in, const DwellHistory & dwell,
  std::uint16_t switches_in_window)
{
  const bool unsafe = in.t_daa_s <= p.tau_daa_s || in.t_gf_s <= p.tau_gf_s ||
    in.monitor_violation || in.input_invalid;
  const bool clear = in.t_daa_s > p.tau_daa_s + p.h_daa_s && in.t_gf_s > p.tau_gf_s + p.h_gf_s &&
    !in.monitor_violation && !in.input_invalid;
  const double clear_duration = clear ? (std::isnan(dwell.clear_since_s) ? 0.0 :
    in.t_s - dwell.clear_since_s) : 0.0;

  Recovery selected = Recovery::kNone;
  if (in.input_invalid || in.t_gf_s <= p.tau_gf_s || in.t_daa_s <= p.tau_daa_s) {
    selected = Recovery::kHold;
  }
  if (in.monitor_violation) {
    selected = maxRank(selected, in.monitor_action);
  }

  if (!in.in_charge) {
    return {State::kInactive, Recovery::kNone, Command::kNone,
      pre.state == State::kInactive ? transition::kNone : transition::kT1};
  }

  switch (pre.state) {
    case State::kInactive:
      if (!in.owned_mode_active) {
        return {State::kInactive, Recovery::kNone, Command::kNone, transition::kNone};
      }
      if (unsafe) {
        return {State::kRf, selected, commandFor(selected), transition::kT2b};
      }
      return {State::kCf, Recovery::kNone, Command::kNone, transition::kT2};

    case State::kCf:
      if (unsafe) {
        return {State::kRf, selected, commandFor(selected), transition::kT3};
      }
      return {State::kCf, Recovery::kNone, Command::kNone, transition::kNone};

    case State::kRf:
      if (switches_in_window >= p.n_max) {
        return {State::kLatched, pre.recovery, Command::kNone, transition::kT4};
      }
      if (pre.recovery == Recovery::kHold && clear && clear_duration >= p.dwell_s &&
        in.t_s - dwell.t_switch_s >= p.dwell_s && p.return_enabled)
      {
        return {State::kCf, Recovery::kNone, Command::kOwnedMode, transition::kT5};
      }
      if (unsafe && rank(selected) > rank(pre.recovery)) {
        return {State::kRf, selected, commandFor(selected), transition::kT6};
      }
      return {State::kRf, pre.recovery, Command::kNone, transition::kNone};

    case State::kLatched:
      if (unsafe && rank(selected) > rank(pre.recovery)) {
        return {State::kLatched, selected, commandFor(selected), transition::kT7};
      }
      return {State::kLatched, pre.recovery, Command::kNone, transition::kNone};
  }
  return {State::kInactive, Recovery::kNone, Command::kNone, transition::kNone};
}

TEST(DecisionCoreTruthTable, ExhaustiveSingleTickAgreesWithSpecificationAndProperties)
{
  const Parameters p{};
  ASSERT_EQ(validate(p), nullptr);

  const std::array<DwellHistory, 3> dwell_histories{{
    {kNow - 2.0 * p.dwell_s, kNow - 2.0 * p.dwell_s},   // dwell and clear duration satisfied
    {kNow - 2.0 * p.dwell_s, kNow - 0.5 * p.dwell_s},   // clear long enough, switch too recent
    {kNaN, kNow - 2.0 * p.dwell_s},                     // clear starts at this tick
  }};
  // Number of CF->RF switches already inside the window before this tick.
  const std::array<std::uint16_t, 3> prior_switches{0, static_cast<std::uint16_t>(p.n_max - 1),
    p.n_max};
  const std::array<Recovery, 3> actions{Recovery::kHold, Recovery::kRtl, Recovery::kLand};

  std::uint64_t cases = 0;
  std::uint64_t failures = 0;

  for (const auto & pre : kPreStates) {
    for (int ic = 0; ic < 2; ++ic) {
      for (int owned = 0; owned < 2; ++owned) {
        for (Level daa : kLevels) {
          for (Level gf : kLevels) {
            for (int m = 0; m < 4; ++m) {
              for (int v = 0; v < 2; ++v) {
                for (const auto & dwell : dwell_histories) {
                  for (std::uint16_t prior : prior_switches) {
                    DecisionCore core(p);
                    std::array<double, kSwitchHistoryCapacity> times{};
                    for (std::uint16_t i = 0; i < prior; ++i) {
                      times[i] = kNow - 1.0 - static_cast<double>(i);
                    }
                    DecisionCoreTestPeer::setSwitchHistory(core, times.data(), prior);
                    DecisionCoreTestPeer::set(
                      core, pre.state, pre.recovery, kNow - kTs, dwell.t_switch_s,
                      dwell.clear_since_s);

                    Inputs in;
                    in.t_s = kNow;
                    in.in_charge = ic != 0;
                    in.owned_mode_active = owned != 0;
                    in.t_daa_s = valueOf(daa, p.tau_daa_s, p.h_daa_s);
                    in.t_gf_s = valueOf(gf, p.tau_gf_s, p.h_gf_s);
                    in.monitor_violation = m != 0;
                    in.monitor_action = m == 0 ? Recovery::kHold : actions[m - 1];
                    in.input_invalid = v != 0;

                    const Output out = core.step(in);
                    const Expected exp = reference(p, pre, in, dwell, prior);
                    const bool unsafe = out.unsafe_causes != 0U;
                    const bool ref_unsafe = in.t_daa_s <= p.tau_daa_s ||
                      in.t_gf_s <= p.tau_gf_s || in.monitor_violation || in.input_invalid;
                    ++cases;

                    bool ok = out.state == exp.state && out.recovery == exp.recovery &&
                      out.command == exp.command && out.transition.id == exp.transition &&
                      unsafe == ref_unsafe;
                    // P-1: U(k) in state CF (with IC) leaves CF in the same tick.
                    if (pre.state == State::kCf && in.in_charge && ref_unsafe) {
                      ok = ok && out.state == State::kRf;
                    }
                    // P-2: state CF at k implies not U(k).
                    if (out.state == State::kCf) {
                      ok = ok && !ref_unsafe;
                    }
                    // P-6: not IC(k) implies no command.
                    if (!in.in_charge) {
                      ok = ok && out.command == Command::kNone && out.state == State::kInactive;
                    }
                    if (!ok && ++failures <= 10) {
                      std::ostringstream os;
                      os << "pre=" << toString(pre.state) << "/" << toString(pre.recovery) <<
                        " ic=" << ic << " owned=" << owned << " daa=" << in.t_daa_s <<
                        " gf=" << in.t_gf_s << " m=" << m << " v=" << v <<
                        " clear_since=" << dwell.clear_since_s << " t_sw=" << dwell.t_switch_s <<
                        " prior=" << prior << " | got " << toString(out.state) << "/" <<
                        toString(out.recovery) << " cmd=" << toString(out.command) << " T" <<
                        static_cast<int>(out.transition.id) << " | expected " <<
                        toString(exp.state) << "/" << toString(exp.recovery) << " cmd=" <<
                        toString(exp.command) << " T" << static_cast<int>(exp.transition);
                      ADD_FAILURE() << os.str();
                    }
                  }
                }
              }
            }
          }
        }
      }
    }
  }
  std::printf("[truth_table] cases=%llu failures=%llu\n",
    static_cast<unsigned long long>(cases), static_cast<unsigned long long>(failures));
  EXPECT_EQ(failures, 0U);
  EXPECT_EQ(cases, 8ULL * 2 * 2 * 5 * 5 * 4 * 2 * 3 * 3);
}

TEST(DecisionCoreTruthTable, NonFiniteSignalsAndNonMonotonicTimeAreInvalidInputs)
{
  const Parameters p{};
  for (double bad : {kNaN}) {
    DecisionCore core(p);
    DecisionCoreTestPeer::set(core, State::kCf, Recovery::kNone, kNow - kTs, -kInf, kNaN);
    Inputs in;
    in.t_s = kNow;
    in.in_charge = true;
    in.owned_mode_active = true;
    in.t_daa_s = bad;
    const Output out = core.step(in);
    EXPECT_EQ(out.state, State::kRf);
    EXPECT_NE(out.unsafe_causes & cause::kInput, 0U);
  }
  {
    DecisionCore core(p);
    DecisionCoreTestPeer::set(core, State::kCf, Recovery::kNone, kNow, -kInf, kNaN);
    Inputs in;
    in.t_s = kNow - kTs;  // time moved backwards
    in.in_charge = true;
    in.owned_mode_active = true;
    const Output out = core.step(in);
    EXPECT_EQ(out.state, State::kRf);
    EXPECT_NE(out.unsafe_causes & cause::kInput, 0U);
  }
}

TEST(DecisionCoreTruthTable, ParameterValidationRejectsInadmissibleValues)
{
  EXPECT_EQ(validate(Parameters{}), nullptr);
  Parameters p{};
  p.h_gf_s = -0.1;
  EXPECT_NE(validate(p), nullptr);
  p = Parameters{};
  p.n_max = 0;
  EXPECT_NE(validate(p), nullptr);
  p = Parameters{};
  p.n_max = static_cast<std::uint16_t>(kSwitchHistoryCapacity + 1);
  EXPECT_NE(validate(p), nullptr);
  p = Parameters{};
  p.dwell_s = std::numeric_limits<double>::quiet_NaN();
  EXPECT_NE(validate(p), nullptr);
  p = Parameters{};
  p.window_s = 0.0;
  EXPECT_NE(validate(p), nullptr);
}

}  // namespace
}  // namespace guara_rta
