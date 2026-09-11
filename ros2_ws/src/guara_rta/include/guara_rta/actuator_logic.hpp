// SPDX-License-Identifier: Apache-2.0
//
// ActuatorLogic: publication, acknowledgement and effect-confirmation policy for mode requests
// (SPEC FM-7). A request is published immediately, re-published every retry period until an
// accepting acknowledgement arrives, and declared failed after N_retry publications without
// acceptance. A newer request supersedes the pending one. The logic never blocks: acknowledgements
// are delivered asynchronously by a subscription, in contrast with ModeExecutorBase::sendCommandSync
// [G A.1].
//
// An acknowledgement only states that PX4 accepted the command, not that the vehicle is flying the
// requested mode (review 2026-09-11 §4 "Mode effect not confirmed"). The request therefore also
// carries the nav_state it must produce; if vehicle_status does not report that nav_state within
// confirm_timeout_s of the acceptance, the request is declared failed and the caller latches
// (SPEC FM-7). This closes the case where another authority, or a PX4 failsafe, silently replaces
// the recovery mode the arbiter believes is active.
#pragma once

#include <cstdint>
#include <limits>

#include "guara_rta/types.hpp"

namespace guara_rta
{

struct ActuatorParameters
{
  double retry_period_s{0.3};   // matches the acknowledgement wait of sendCommandSync [G A.1]
  std::uint16_t n_retry{3};     // SPEC FM-7 N_retry [HYPOTHESIS]
  double confirm_timeout_s{1.0};  // [HYPOTHESIS] time allowed between acceptance and effect
};

enum class ActuatorAction : std::uint8_t
{
  kIdle = 0,
  kPublish = 1,   // publish the pending request now
  kFailed = 2,    // retry budget exhausted, or accepted without effect (reported once)
};

inline constexpr std::uint8_t kNavStateUnknown = 255;

class ActuatorLogic
{
public:
  explicit ActuatorLogic(const ActuatorParameters & p) noexcept
  : p_(p) {}

  // `expected_nav_state` is the vehicle_status nav_state the request must produce;
  // kNavStateUnknown disables the effect confirmation for this request.
  void request(Command command, std::uint8_t expected_nav_state, double t_s) noexcept
  {
    if (command == Command::kNone) {
      return;
    }
    pending_ = command;
    expected_nav_state_ = expected_nav_state;
    publications_ = 0U;
    t_last_pub_s_ = -std::numeric_limits<double>::infinity();
    t_request_s_ = t_s;
    failed_reported_ = false;
    awaiting_confirmation_ = false;
    t_accepted_s_ = std::numeric_limits<double>::quiet_NaN();
  }

  void cancel() noexcept
  {
    pending_ = Command::kNone;
    awaiting_confirmation_ = false;
  }

  ActuatorAction tick(double t_s) noexcept
  {
    if (awaiting_confirmation_) {
      if (t_s - t_accepted_s_ <= p_.confirm_timeout_s) {
        return ActuatorAction::kIdle;
      }
      awaiting_confirmation_ = false;
      if (!failed_reported_) {
        failed_reported_ = true;
        return ActuatorAction::kFailed;
      }
      return ActuatorAction::kIdle;
    }
    if (pending_ == Command::kNone) {
      return ActuatorAction::kIdle;
    }
    if (t_s - t_last_pub_s_ < p_.retry_period_s) {
      return ActuatorAction::kIdle;
    }
    if (publications_ >= p_.n_retry) {
      pending_ = Command::kNone;
      if (!failed_reported_) {
        failed_reported_ = true;
        return ActuatorAction::kFailed;
      }
      return ActuatorAction::kIdle;
    }
    ++publications_;
    t_last_pub_s_ = t_s;
    return ActuatorAction::kPublish;
  }

  // `accepted` is true for VEHICLE_CMD_RESULT_ACCEPTED. A rejection keeps the request pending so that
  // it is retried within the budget. An acceptance starts the effect-confirmation window.
  void onAck(Command command, bool accepted, double t_s) noexcept
  {
    if (command != pending_ || !accepted) {
      return;
    }
    pending_ = Command::kNone;
    t_last_ack_s_ = t_s;
    if (expected_nav_state_ == kNavStateUnknown) {
      return;
    }
    awaiting_confirmation_ = true;
    t_accepted_s_ = t_s;
  }

  // Effect observed on vehicle_status.
  void onNavState(std::uint8_t nav_state, double t_s) noexcept
  {
    nav_state_ = nav_state;
    if (awaiting_confirmation_ && nav_state == expected_nav_state_) {
      awaiting_confirmation_ = false;
      t_confirmed_s_ = t_s;
    }
  }

  Command pending() const noexcept {return pending_;}
  bool awaitingConfirmation() const noexcept {return awaiting_confirmation_;}
  std::uint8_t navState() const noexcept {return nav_state_;}
  std::uint8_t expectedNavState() const noexcept {return expected_nav_state_;}
  double lastPublication() const noexcept {return t_last_pub_s_;}
  double lastAck() const noexcept {return t_last_ack_s_;}
  double lastConfirmation() const noexcept {return t_confirmed_s_;}
  double requestTime() const noexcept {return t_request_s_;}

private:
  ActuatorParameters p_;
  Command pending_{Command::kNone};
  std::uint8_t expected_nav_state_{kNavStateUnknown};
  std::uint8_t nav_state_{kNavStateUnknown};
  std::uint16_t publications_{0U};
  bool awaiting_confirmation_{false};
  double t_last_pub_s_{-std::numeric_limits<double>::infinity()};
  double t_last_ack_s_{std::numeric_limits<double>::quiet_NaN()};
  double t_accepted_s_{std::numeric_limits<double>::quiet_NaN()};
  double t_confirmed_s_{std::numeric_limits<double>::quiet_NaN()};
  double t_request_s_{std::numeric_limits<double>::quiet_NaN()};
  bool failed_reported_{false};
};

}  // namespace guara_rta
