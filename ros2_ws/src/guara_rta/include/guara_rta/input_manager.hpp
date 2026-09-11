// SPDX-License-Identifier: Apache-2.0
//
// InputManager: computes the invalid-input signal V(k) of SPEC §3.1 from the reception instants and
// validity flags of the mandatory input channels. Ages are measured on the arbiter monotonic clock
// from message reception; transport delay upstream of reception (stages L0-L1 of SPEC §4.1) is part
// of the latency budget, not of the age.
#pragma once

#include <array>
#include <cstdint>
#include <limits>

namespace guara_rta
{

enum class Channel : std::uint8_t
{
  kLocalPosition = 0,   // /fmu/out/vehicle_local_position_v1
  kVehicleStatus = 1,   // /fmu/out/vehicle_status_v1
  kMonitor = 2,         // /guara/monitors/verdict
  kDaa = 3,             // /guara/daa/status
  kGeofence = 4,        // geofence predictor output (derived from kLocalPosition)
  kCount = 5,
};

struct ChannelConfig
{
  bool required{false};
  double max_age_s{std::numeric_limits<double>::infinity()};  // A_i
};

class InputManager
{
public:
  using Config = std::array<ChannelConfig, static_cast<std::size_t>(Channel::kCount)>;

  explicit InputManager(const Config & config) noexcept
  : config_(config) {}

  // Records a reception. `valid` carries the semantic validity of the sample (e.g. xy_valid).
  void onReceive(Channel channel, double t_recv_s, bool valid) noexcept
  {
    auto & s = state_[index(channel)];
    s.t_recv_s = t_recv_s;
    s.valid = valid;
    s.received = true;
  }

  // Bit i set  <=>  channel i is required and is missing, stale (age > A_i) or invalid at t_s.
  std::uint32_t invalidMask(double t_s) const noexcept
  {
    std::uint32_t mask = 0U;
    for (std::size_t i = 0; i < config_.size(); ++i) {
      if (!config_[i].required) {
        continue;
      }
      const auto & s = state_[i];
      if (!s.received || !s.valid || t_s - s.t_recv_s > config_[i].max_age_s) {
        mask |= 1U << i;
      }
    }
    return mask;
  }

  double lastReception(Channel channel) const noexcept {return state_[index(channel)].t_recv_s;}

  const Config & config() const noexcept {return config_;}

private:
  struct ChannelState
  {
    double t_recv_s{-std::numeric_limits<double>::infinity()};
    bool valid{false};
    bool received{false};
  };

  static std::size_t index(Channel c) noexcept {return static_cast<std::size_t>(c);}

  Config config_;
  std::array<ChannelState, static_cast<std::size_t>(Channel::kCount)> state_{};
};

}  // namespace guara_rta
