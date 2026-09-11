// SPDX-License-Identifier: Apache-2.0
//
// DecisionCore: the Switching Logic of the Guará Runtime Assurance architecture (SPEC §3).
//
// The core is a pure, synchronous state machine evaluated once per tick of period T_s. It has no
// dependency on ROS, performs no dynamic memory allocation after construction and executes a
// bounded number of operations per tick (the only loop iterates over a fixed-capacity history of
// switch instants). These properties are the subject of AC-4, AC-5 and AC-6.
#pragma once

#include <array>
#include <cstddef>
#include <cstdint>
#include <limits>

#include "guara_rta/types.hpp"

namespace guara_rta
{

// Parameters of SPEC §3.2. All values are hypotheses to be measured (SPEC R-12); defaults equal the
// initial values tabulated there.
struct Parameters
{
  double tau_daa_s{30.0};      // DAA trigger threshold
  double tau_gf_s{1.0};        // geofence trigger threshold
  double h_daa_s{5.0};         // additive DAA hysteresis on return
  double h_gf_s{1.0};          // additive geofence hysteresis on return
  double dwell_s{5.0};         // T_d: minimum dwell in RF and minimum continuous clear time
  std::uint16_t n_max{3};      // N_max: CF->RF switches in window W that latch the recovery
  double window_s{120.0};      // W
  bool return_enabled{true};   // enables T5 (ADR 0005 item 6)
  bool escalation_enabled{false};  // persistence escalation (ADR 0005 item 5)
  double escalation_s{30.0};   // T_esc
};

// Capacity of the switch-instant history. N_max must not exceed it.
inline constexpr std::size_t kSwitchHistoryCapacity = 32;

// Returns nullptr if the parameters are admissible, otherwise a static description of the first
// violated constraint.
const char * validate(const Parameters & p) noexcept;

// Signals of SPEC §3.1 sampled at tick k.
struct Inputs
{
  double t_s{0.0};                  // t_k, monotonic
  bool in_charge{false};            // IC(k)
  bool owned_mode_active{false};    // the owned (CF gateway) mode is the active PX4 mode
  double t_daa_s{std::numeric_limits<double>::infinity()};  // T_daa(k); +inf = no conflict
  double t_gf_s{std::numeric_limits<double>::infinity()};   // T_gf(k); +inf = no violation
  bool monitor_violation{false};    // M(k)
  Recovery monitor_action{Recovery::kHold};  // highest-rank action among violating monitors
  bool input_invalid{false};        // V(k)
};

struct Transition
{
  std::uint8_t id{transition::kNone};
  State from{State::kInactive};
  State to{State::kInactive};
  Recovery rf_from{Recovery::kNone};
  Recovery rf_to{Recovery::kNone};
  std::uint32_t cause{0};
};

struct Output
{
  State state{State::kInactive};
  Recovery recovery{Recovery::kNone};
  Command command{Command::kNone};  // mode request issued at this tick, if any
  Transition transition{};          // id == transition::kNone if the state did not change
  std::uint32_t unsafe_causes{0};   // causes of U(k); zero iff U(k) is false
  bool clear{false};                // C(k)
  double clear_duration_s{0.0};     // Cdur(k)
  std::uint16_t switches_in_window{0};  // S(k)
};

class DecisionCore
{
public:
  // Precondition: validate(parameters) == nullptr. Violations are reported by valid().
  explicit DecisionCore(const Parameters & parameters) noexcept;

  // Evaluates the transition table of SPEC §3.5 for tick k. Inputs with a non-finite or
  // non-increasing t_s, and NaN time signals, are treated as invalid inputs (cause::kInput).
  Output step(const Inputs & in) noexcept;

  // Forces a latched recovery, used when the actuator exhausts its retry budget (SPEC FM-7).
  // Has no effect unless the state is RF or LATCHED.
  Output latchOnActuationFailure(double t_s) noexcept;

  State state() const noexcept {return state_;}
  Recovery recovery() const noexcept {return recovery_;}
  const Parameters & parameters() const noexcept {return p_;}
  bool valid() const noexcept {return valid_;}

private:
  friend struct DecisionCoreTestPeer;

  std::uint32_t unsafeCauses(const Inputs & in, bool time_valid) const noexcept;
  bool clearCondition(const Inputs & in, bool time_valid) const noexcept;
  Recovery select(const Inputs & in, std::uint32_t causes) const noexcept;
  std::uint16_t switchesInWindow(double t_s) const noexcept;
  void recordSwitch(double t_s) noexcept;

  Parameters p_;
  bool valid_{false};

  State state_{State::kInactive};
  Recovery recovery_{Recovery::kNone};
  double t_switch_s_{-std::numeric_limits<double>::infinity()};
  double t_prev_s_{-std::numeric_limits<double>::infinity()};
  double clear_since_s_{std::numeric_limits<double>::quiet_NaN()};
  double unsafe_since_s_{std::numeric_limits<double>::quiet_NaN()};

  std::array<double, kSwitchHistoryCapacity> switch_times_{};
  std::size_t switch_head_{0};
  std::size_t switch_count_{0};
};

}  // namespace guara_rta
