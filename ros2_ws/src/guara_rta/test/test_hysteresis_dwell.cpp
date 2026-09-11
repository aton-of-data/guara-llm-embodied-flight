// SPDX-License-Identifier: Apache-2.0
//
// AC-12 (property P-3): return from RF(HOLD) to CF happens only after the clear condition C has held
// continuously for T_d and at least T_d has elapsed since the CF->RF switch; the hysteresis band
// (tau, tau + h] never permits a return (SPEC §3.4-§3.5, ADR 0005).
#include <gtest/gtest.h>

#include <cmath>
#include <cstdint>
#include <functional>
#include <limits>
#include <vector>

#include "guara_rta/decision_core.hpp"

namespace guara_rta
{
namespace
{

constexpr double kTs = 0.05;
constexpr double kInf = std::numeric_limits<double>::infinity();

struct TickRecord
{
  double t_s;
  Output out;
  bool clear_reference;  // C(k) recomputed from the inputs, independent of the core
};

// Runs the core for `ticks` ticks from t = 0 with inputs produced by `signals(k, in)`.
std::vector<TickRecord> simulate(
  const Parameters & p, std::uint64_t ticks, const std::function<void(std::uint64_t, Inputs &)> & signals)
{
  DecisionCore core(p);
  std::vector<TickRecord> trace;
  trace.reserve(ticks);
  for (std::uint64_t k = 0; k < ticks; ++k) {
    Inputs in;
    in.t_s = static_cast<double>(k) * kTs;
    in.in_charge = true;
    in.owned_mode_active = true;
    signals(k, in);
    const bool clear = in.t_daa_s > p.tau_daa_s + p.h_daa_s && in.t_gf_s > p.tau_gf_s + p.h_gf_s &&
      !in.monitor_violation && !in.input_invalid;
    trace.push_back({in.t_s, core.step(in), clear});
  }
  return trace;
}

// Checks P-3 on every T5 transition of a trace and returns the number of returns observed.
int checkReturns(const Parameters & p, const std::vector<TickRecord> & trace)
{
  int returns = 0;
  double t_switch = -kInf;
  for (std::size_t k = 0; k < trace.size(); ++k) {
    const auto & rec = trace[k];
    if (rec.out.transition.id == transition::kT3 || rec.out.transition.id == transition::kT2b) {
      t_switch = rec.t_s;
    }
    if (rec.out.transition.id != transition::kT5) {
      continue;
    }
    ++returns;
    EXPECT_GE(rec.t_s - t_switch, p.dwell_s - 1e-9) << "return at t=" << rec.t_s;
    // C must have been true at every tick in [t_k - T_d, t_k].
    for (std::size_t j = 0; j <= k; ++j) {
      if (trace[j].t_s >= rec.t_s - p.dwell_s - 1e-9) {
        EXPECT_TRUE(trace[j].clear_reference) << "C false at t=" << trace[j].t_s <<
          " inside dwell window of return at t=" << rec.t_s;
      }
    }
  }
  return returns;
}

std::uint64_t ticksFor(double seconds) {return static_cast<std::uint64_t>(std::llround(seconds / kTs));}

TEST(HysteresisDwell, SignalOscillatingAroundThresholdNeverReturns)
{
  const Parameters p{};
  const auto trace = simulate(p, ticksFor(300.0), [&p](std::uint64_t k, Inputs & in) {
        in.t_gf_s = (k % 2U) == 0U ? p.tau_gf_s - 0.1 : p.tau_gf_s + 0.1;
      });
  EXPECT_EQ(trace.front().out.state, State::kRf);
  EXPECT_EQ(checkReturns(p, trace), 0);
  for (const auto & rec : trace) {
    EXPECT_NE(rec.out.state, State::kCf) << "t=" << rec.t_s;
  }
}

TEST(HysteresisDwell, SignalInsideHysteresisBandNeverReturns)
{
  const Parameters p{};
  const auto trace = simulate(p, ticksFor(300.0), [&p](std::uint64_t k, Inputs & in) {
        in.t_gf_s = k < 10U ? 0.0 : p.tau_gf_s + 0.5 * p.h_gf_s;
        in.t_daa_s = p.tau_daa_s + p.h_daa_s + 1.0;
      });
  EXPECT_EQ(checkReturns(p, trace), 0);
  EXPECT_EQ(trace.back().out.state, State::kRf);
  EXPECT_EQ(trace.back().out.recovery, Recovery::kHold);
}

TEST(HysteresisDwell, ReturnOccursAtFirstTickSatisfyingDwellAndNotBefore)
{
  const Parameters p{};
  // Unsafe for one tick at k = 20 (t = 1.0 s), clear afterwards.
  const auto trace = simulate(p, ticksFor(20.0), [](std::uint64_t k, Inputs & in) {
        in.t_gf_s = k == 20U ? 0.0 : kInf;
      });
  ASSERT_EQ(trace[20].out.transition.id, transition::kT3);
  // C becomes true at k = 21 (t = 1.05 s); T5 requires Cdur >= T_d and t - t_sw >= T_d.
  const double expected_return_t = 1.05 + p.dwell_s;
  int returns = 0;
  for (const auto & rec : trace) {
    if (rec.out.transition.id == transition::kT5) {
      ++returns;
      EXPECT_NEAR(rec.t_s, expected_return_t, 1e-9);
      EXPECT_EQ(rec.out.command, Command::kOwnedMode);
    }
    if (rec.t_s < expected_return_t - 1e-9 && rec.t_s > 1.0) {
      EXPECT_EQ(rec.out.state, State::kRf) << "t=" << rec.t_s;
    }
  }
  EXPECT_EQ(returns, 1);
  EXPECT_EQ(checkReturns(p, trace), 1);
}

TEST(HysteresisDwell, InterruptionOfClearConditionRestartsDwell)
{
  const Parameters p{};
  // Trigger at t = 0; clear from t = 0.05; a single band sample (not clear, not unsafe) at t = 4.0 s.
  const std::uint64_t k_band = ticksFor(4.0);
  const auto trace = simulate(p, ticksFor(20.0), [&p, k_band](std::uint64_t k, Inputs & in) {
        if (k == 0U) {
          in.t_gf_s = 0.0;
        } else if (k == k_band) {
          in.t_gf_s = p.tau_gf_s + 0.5 * p.h_gf_s;
        }
      });
  double t_return = -1.0;
  for (const auto & rec : trace) {
    if (rec.out.transition.id == transition::kT5) {
      t_return = rec.t_s;
      break;
    }
  }
  EXPECT_NEAR(t_return, 4.05 + p.dwell_s, 1e-9);
  checkReturns(p, trace);
}

TEST(HysteresisDwell, ReturnDisabledKeepsHold)
{
  Parameters p{};
  p.return_enabled = false;
  const auto trace = simulate(p, ticksFor(60.0), [](std::uint64_t k, Inputs & in) {
        in.t_gf_s = k == 0U ? 0.0 : kInf;
      });
  EXPECT_EQ(checkReturns(p, trace), 0);
  EXPECT_EQ(trace.back().out.state, State::kRf);
}

TEST(HysteresisDwell, NoAutomaticReturnFromRtlOrLand)
{
  const Parameters p{};
  for (Recovery action : {Recovery::kRtl, Recovery::kLand}) {
    const auto trace = simulate(p, ticksFor(60.0), [action](std::uint64_t k, Inputs & in) {
          if (k == 0U) {
            in.monitor_violation = true;
            in.monitor_action = action;
          }
        });
    EXPECT_EQ(trace.front().out.recovery, action);
    EXPECT_EQ(checkReturns(p, trace), 0);
    EXPECT_EQ(trace.back().out.state, State::kRf);
    EXPECT_EQ(trace.back().out.recovery, action);
  }
}

TEST(HysteresisDwell, NoIntentionalDelayFromCfToRf)
{
  // Obligation O-3: the CF->RF direction is not delayed by hysteresis or dwell.
  const Parameters p{};
  const auto trace = simulate(p, ticksFor(30.0), [&p](std::uint64_t k, Inputs & in) {
        // Returns to CF at some point, then becomes unsafe exactly at the threshold.
        in.t_gf_s = (k == 0U || k == 300U) ? p.tau_gf_s : kInf;
      });
  EXPECT_EQ(trace[0].out.transition.id, transition::kT2b);
  ASSERT_EQ(trace[299].out.state, State::kCf);
  EXPECT_EQ(trace[300].out.transition.id, transition::kT3);
}

TEST(HysteresisDwell, PersistenceEscalationSelectsLandAfterTesc)
{
  Parameters p{};
  p.escalation_enabled = true;
  const auto trace = simulate(p, ticksFor(40.0), [](std::uint64_t, Inputs & in) {
        in.t_gf_s = 0.0;
      });
  double t_escalation = -1.0;
  for (const auto & rec : trace) {
    if (rec.out.transition.id == transition::kT6) {
      t_escalation = rec.t_s;
      EXPECT_EQ(rec.out.recovery, Recovery::kLand);
      EXPECT_NE(rec.out.transition.cause & cause::kEscalation, 0U);
      break;
    }
  }
  EXPECT_GT(t_escalation, p.escalation_s);
  EXPECT_LE(t_escalation, p.escalation_s + 2.0 * kTs);
}

}  // namespace
}  // namespace guara_rta
