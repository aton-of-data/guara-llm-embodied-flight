// SPDX-License-Identifier: Apache-2.0
//
// Safety profile of an arbiter configuration (review 2026-09-11 H-3, H-4, H-5).
//
// The findings of the review were not only coding defects: the shipped configuration disabled the
// DAA, monitor and geofence contributions to V(k) while the code still consumed their values, and
// nothing in the system objected. A configuration is therefore validated against a declared profile
// before the node starts:
//
//   sitl    permissive, for bench and SITL scenarios that deliberately exercise one channel at a
//           time. Still rejects a configuration that is internally inconsistent.
//   flight  every protection channel enabled, at least one expected monitor, and every enabled
//           channel bounded in age. An omission has to be declared explicitly through
//           safety.accepted_omissions, which is copied into the run configuration and into the
//           RtaState telemetry, so flying without a protection is a recorded decision rather than a
//           default.
#pragma once

#include <cmath>
#include <cstdint>
#include <cstring>

#include "guara_rta/input_manager.hpp"

namespace guara_rta
{

enum class SafetyProfile : std::uint8_t
{
  kSitl = 0,
  kFlight = 1,
};

// Bit mask of protections a flight configuration is allowed to omit.
namespace omission
{
constexpr std::uint32_t kDaa = 1U << 0U;
constexpr std::uint32_t kMonitors = 1U << 1U;
constexpr std::uint32_t kGeofence = 1U << 2U;
}  // namespace omission

// Returns nullptr on success and sets *out; otherwise a static description of the error.
inline const char * parseProfile(const char * name, SafetyProfile * out) noexcept
{
  if (name == nullptr || out == nullptr) {
    return "safety.profile must be 'flight' or 'sitl'";
  }
  if (std::strcmp(name, "flight") == 0) {
    *out = SafetyProfile::kFlight;
    return nullptr;
  }
  if (std::strcmp(name, "sitl") == 0) {
    *out = SafetyProfile::kSitl;
    return nullptr;
  }
  return "safety.profile must be 'flight' or 'sitl'";
}

// Returns nullptr if `config` is admissible for `profile`, otherwise a static description of the
// first violated rule. `expected_monitors` is the number of monitor identifiers the arbiter waits
// for; `omissions` is the declared omission mask.
inline const char * validateProfile(SafetyProfile profile, const InputManager::Config & config,
  std::size_t expected_monitors, std::uint32_t omissions) noexcept
{
  const auto & local = config[static_cast<std::size_t>(Channel::kLocalPosition)];
  const auto & status = config[static_cast<std::size_t>(Channel::kVehicleStatus)];
  const auto & monitor = config[static_cast<std::size_t>(Channel::kMonitor)];
  const auto & daa = config[static_cast<std::size_t>(Channel::kDaa)];
  const auto & geofence = config[static_cast<std::size_t>(Channel::kGeofence)];

  for (const auto & c : config) {
    if (c.enabled && !(std::isfinite(c.max_age_s) && c.max_age_s > 0.0)) {
      return "every enabled input channel needs a finite, positive max_age_s";
    }
  }
  if (!local.enabled || !status.enabled) {
    return "inputs.local_position and inputs.vehicle_status must be enabled in every profile";
  }
  if (profile == SafetyProfile::kSitl) {
    return nullptr;
  }
  if (!monitor.enabled && (omissions & omission::kMonitors) == 0U) {
    return "flight profile: inputs.monitor.enabled is false and 'monitors' is not in "
           "safety.accepted_omissions";
  }
  if (monitor.enabled && expected_monitors == 0U) {
    return "flight profile: inputs.monitor.expected_ids is empty, so a monitor that never starts "
           "cannot be detected";
  }
  if (!daa.enabled && (omissions & omission::kDaa) == 0U) {
    return "flight profile: inputs.daa.enabled is false and 'daa' is not in "
           "safety.accepted_omissions";
  }
  if (!geofence.enabled && (omissions & omission::kGeofence) == 0U) {
    return "flight profile: inputs.geofence.enabled is false and 'geofence' is not in "
           "safety.accepted_omissions";
  }
  return nullptr;
}

// Parses one omission name into its bit; returns 0 for an unknown name.
inline std::uint32_t omissionBit(const char * name) noexcept
{
  if (name == nullptr) {
    return 0U;
  }
  if (std::strcmp(name, "daa") == 0) {return omission::kDaa;}
  if (std::strcmp(name, "monitors") == 0) {return omission::kMonitors;}
  if (std::strcmp(name, "geofence") == 0) {return omission::kGeofence;}
  return 0U;
}

}  // namespace guara_rta
