// SPDX-License-Identifier: Apache-2.0
//
// ActuatorLogic: publication and acknowledgement policy for mode requests (SPEC FM-7). A request is
// published immediately, re-published every retry period until an accepting acknowledgement for the
// same nav_state arrives, and declared failed after N_retry publications without acceptance. A newer
// request supersedes the pending one. The logic never blocks: acknowledgements are delivered
// asynchronously by a subscription, in contrast with ModeExecutorBase::sendCommandSync [G A.1].
#pragma once

#include <cstdint>
#include <limits>

#include "guara_rta/types.hpp"

namespace guara_rta
{

struct ActuatorParameters
{
  double retry_period_s{0.3};  // matches the acknowledgement wait of sendCommandSync [G A.1]
  std::uint16_t n_retry{3};    // SPEC FM-7 N_retry [HYPOTHESIS]
};

enum class ActuatorAction : std::uint8_t
{
  kIdle = 0,
  kPublish = 1,   // publish the pending request now
  kFailed = 2,    // retry budget exhausted without acceptance (reported once)
};

class ActuatorLogic
{
public:
  explicit ActuatorLogic(const ActuatorParameters & p) noexcept
  : p_(p) {}

  void request(Command command, double t_s) noexcept
  {
    if (command == Command::kNone) {
      return;
    }
    pending_ = command;
    publications_ = 0U;
    t_last_pub_s_ = -std::numeric_limits<double>::infinity();
    t_request_s_ = t_s;
    failed_reported_ = false;
  }

  void cancel() noexcept {pending_ = Command::kNone;}

  ActuatorAction tick(double t_s) noexcept
  {
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
  // it is retried within the budget.
  void onAck(Command command, bool accepted, double t_s) noexcept
  {
    if (command == pending_ && accepted) {
      pending_ = Command::kNone;
      t_last_ack_s_ = t_s;
    }
  }

  Command pending() const noexcept {return pending_;}
  double lastPublication() const noexcept {return t_last_pub_s_;}
  double lastAck() const noexcept {return t_last_ack_s_;}
  double requestTime() const noexcept {return t_request_s_;}

private:
  ActuatorParameters p_;
  Command pending_{Command::kNone};
  std::uint16_t publications_{0U};
  double t_last_pub_s_{-std::numeric_limits<double>::infinity()};
  double t_last_ack_s_{std::numeric_limits<double>::quiet_NaN()};
  double t_request_s_{std::numeric_limits<double>::quiet_NaN()};
  bool failed_reported_{false};
};

}  // namespace guara_rta
