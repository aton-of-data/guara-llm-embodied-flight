// SPDX-License-Identifier: Apache-2.0
//
// Implementation of the transition table of SPEC §3.5. At most one transition is taken per tick; the
// rows are evaluated in table order for the current state. Comparisons against dwell durations use a
// tolerance of kTimeEpsilonS so that a tick nominally at t_sw + T_d is not deferred by the binary
// representation of the sampled clock.
#include "guara_rta/decision_core.hpp"

#include <cmath>

namespace guara_rta
{
namespace
{

constexpr double kTimeEpsilonS = 1e-9;

bool finiteNonNegative(double v) noexcept {return std::isfinite(v) && v >= 0.0;}

}  // namespace

const char * validate(const Parameters & p) noexcept
{
  if (!finiteNonNegative(p.tau_daa_s)) {return "tau_daa_s must be finite and >= 0";}
  if (!finiteNonNegative(p.tau_gf_s)) {return "tau_gf_s must be finite and >= 0";}
  if (!finiteNonNegative(p.h_daa_s)) {return "h_daa_s must be finite and >= 0";}
  if (!finiteNonNegative(p.h_gf_s)) {return "h_gf_s must be finite and >= 0";}
  if (!finiteNonNegative(p.dwell_s)) {return "dwell_s must be finite and >= 0";}
  if (!(std::isfinite(p.window_s) && p.window_s > 0.0)) {return "window_s must be finite and > 0";}
  if (p.n_max == 0U) {return "n_max must be >= 1";}
  if (p.n_max > kSwitchHistoryCapacity) {return "n_max exceeds kSwitchHistoryCapacity";}
  if (!(std::isfinite(p.escalation_s) && p.escalation_s > 0.0)) {
    return "escalation_s must be finite and > 0";
  }
  return nullptr;
}

DecisionCore::DecisionCore(const Parameters & parameters) noexcept
: p_(parameters), valid_(validate(parameters) == nullptr) {}

std::uint32_t DecisionCore::unsafeCauses(const Inputs & in, bool time_valid) const noexcept
{
  std::uint32_t causes = 0U;
  // NaN compares false with every threshold; it is mapped to an invalid input instead of being
  // silently interpreted as "no conflict".
  if (std::isnan(in.t_daa_s) || std::isnan(in.t_gf_s) || in.input_invalid || !time_valid) {
    causes |= cause::kInput;
  }
  if (in.t_daa_s <= p_.tau_daa_s) {causes |= cause::kDaa;}
  if (in.t_gf_s <= p_.tau_gf_s) {causes |= cause::kGeofence;}
  if (in.monitor_violation) {causes |= cause::kMonitor;}
  return causes;
}

bool DecisionCore::clearCondition(const Inputs & in, bool time_valid) const noexcept
{
  return time_valid && !in.input_invalid && !in.monitor_violation &&
         in.t_daa_s > p_.tau_daa_s + p_.h_daa_s && in.t_gf_s > p_.tau_gf_s + p_.h_gf_s;
}

Recovery DecisionCore::select(const Inputs & in, std::uint32_t causes) const noexcept
{
  Recovery r = Recovery::kNone;
  if ((causes & (cause::kInput | cause::kGeofence | cause::kDaa)) != 0U) {
    r = Recovery::kHold;
  }
  if ((causes & cause::kMonitor) != 0U) {
    const Recovery action = in.monitor_action == Recovery::kNone ? Recovery::kHold :
      in.monitor_action;
    r = maxRank(r, action);
  }
  if (p_.escalation_enabled && causes != 0U && !std::isnan(unsafe_since_s_) &&
    in.t_s - unsafe_since_s_ > p_.escalation_s)
  {
    r = Recovery::kLand;
  }
  return r;
}

std::uint16_t DecisionCore::switchesInWindow(double t_s) const noexcept
{
  std::uint16_t n = 0U;
  for (std::size_t i = 0; i < switch_count_; ++i) {
    const std::size_t idx = (switch_head_ + kSwitchHistoryCapacity - 1U - i) %
      kSwitchHistoryCapacity;
    if (switch_times_[idx] > t_s - p_.window_s) {
      ++n;
    }
  }
  return n;
}

void DecisionCore::recordSwitch(double t_s) noexcept
{
  switch_times_[switch_head_] = t_s;
  switch_head_ = (switch_head_ + 1U) % kSwitchHistoryCapacity;
  if (switch_count_ < kSwitchHistoryCapacity) {
    ++switch_count_;
  }
}

Output DecisionCore::step(const Inputs & in) noexcept
{
  const bool time_valid = std::isfinite(in.t_s) && in.t_s > t_prev_s_;
  const std::uint32_t causes = unsafeCauses(in, time_valid);
  const bool unsafe = causes != 0U;
  const bool clear = clearCondition(in, time_valid);

  // Continuous-duration bookkeeping for Cdur(k) and for the persistence escalation.
  if (clear) {
    if (std::isnan(clear_since_s_)) {clear_since_s_ = in.t_s;}
  } else {
    clear_since_s_ = std::numeric_limits<double>::quiet_NaN();
  }
  if (unsafe) {
    if (std::isnan(unsafe_since_s_)) {unsafe_since_s_ = in.t_s;}
  } else {
    unsafe_since_s_ = std::numeric_limits<double>::quiet_NaN();
  }
  if (time_valid) {
    t_prev_s_ = in.t_s;
  }

  const double clear_duration = clear ? in.t_s - clear_since_s_ : 0.0;
  const std::uint16_t switches = switchesInWindow(in.t_s);
  const Recovery selected = unsafe ? select(in, causes) : Recovery::kNone;
  const bool escalated_by_persistence = p_.escalation_enabled && unsafe &&
    in.t_s - unsafe_since_s_ > p_.escalation_s;

  Output out;
  out.unsafe_causes = causes;
  out.clear = clear;
  out.clear_duration_s = clear_duration;

  const State from = state_;
  const Recovery rf_from = recovery_;
  std::uint8_t id = transition::kNone;
  std::uint32_t transition_cause = 0U;

  if (!in.in_charge) {
    // T1: human or PX4 authority; the arbiter stops commanding (P-6). The switch history is *not*
    // cleared: it is the anti-chattering budget of P-4, and clearing it would let any agent able to
    // select modes (a pilot, or an LLM with a mode tool) reset N_max by leaving and re-entering the
    // owned mode (review 2026-09-11 §4 "Latch bypass"). Entries decay with the window W.
    if (state_ != State::kInactive) {
      id = transition::kT1;
      transition_cause = cause::kNotInCharge;
    }
    state_ = State::kInactive;
    recovery_ = Recovery::kNone;
  } else {
    switch (state_) {
      case State::kInactive:
        if (in.owned_mode_active) {
          if (unsafe) {
            id = transition::kT2b;
            state_ = State::kRf;
            recovery_ = selected;
            transition_cause = causes;
            t_switch_s_ = in.t_s;
            recordSwitch(in.t_s);
            out.command = commandFor(selected);
          } else {
            id = transition::kT2;
            state_ = State::kCf;
          }
        }
        break;

      case State::kCf:
        if (unsafe) {
          id = transition::kT3;
          state_ = State::kRf;
          recovery_ = selected;
          transition_cause = causes;
          t_switch_s_ = in.t_s;
          recordSwitch(in.t_s);
          out.command = commandFor(selected);
        }
        break;

      case State::kRf:
        if (switches >= p_.n_max) {
          id = transition::kT4;
          state_ = State::kLatched;
          transition_cause = cause::kLatch;
        } else if (recovery_ == Recovery::kHold && clear && !in.cf_intent_unsafe &&
          clear_duration >= p_.dwell_s - kTimeEpsilonS &&
          in.t_s - t_switch_s_ >= p_.dwell_s - kTimeEpsilonS && p_.return_enabled)
        {
          id = transition::kT5;
          state_ = State::kCf;
          recovery_ = Recovery::kNone;
          transition_cause = cause::kReturn;
          out.command = Command::kOwnedMode;
        } else if (unsafe && rank(selected) > rank(recovery_)) {
          id = transition::kT6;
          recovery_ = selected;
          transition_cause = causes | (escalated_by_persistence ? cause::kEscalation : 0U);
          out.command = commandFor(selected);
        }
        break;

      case State::kLatched:
        if (unsafe && rank(selected) > rank(recovery_)) {
          id = transition::kT7;
          recovery_ = selected;
          transition_cause = causes | (escalated_by_persistence ? cause::kEscalation : 0U);
          out.command = commandFor(selected);
        }
        break;
    }
  }

  out.state = state_;
  out.recovery = recovery_;
  out.switches_in_window = switchesInWindow(in.t_s);
  if (id != transition::kNone) {
    out.transition = Transition{id, from, state_, rf_from, recovery_, transition_cause};
  }
  return out;
}

Output DecisionCore::latchOnActuationFailure(double t_s) noexcept
{
  Output out;
  out.state = state_;
  out.recovery = recovery_;
  out.switches_in_window = switchesInWindow(t_s);
  if (state_ == State::kRf) {
    const State from = state_;
    state_ = State::kLatched;
    out.state = state_;
    out.transition = Transition{transition::kActuationLatch, from, state_, recovery_, recovery_,
      cause::kActuation};
  }
  return out;
}

}  // namespace guara_rta
