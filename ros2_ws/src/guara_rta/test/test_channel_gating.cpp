// SPDX-License-Identifier: Apache-2.0
//
// Channel gating and the flight safety profile (review 2026-09-11 H-3, H-5). Before this change a
// channel only entered V(k) when it was marked "required", and the shipped configuration left the
// DAA, monitor and geofence channels out of V(k) while still consuming their values: a dead DAIDALUS
// node or a geofence sample without a global reference was indistinguishable from "no conflict".
// An *enabled* channel is now a channel the arbiter depends on, and an enabled channel that is
// missing, stale or invalid sets V(k).
#include <gtest/gtest.h>

#include "guara_rta/input_manager.hpp"
#include "guara_rta/safety_profile.hpp"

namespace
{

using guara_rta::Channel;
using guara_rta::ChannelConfig;
using guara_rta::InputManager;
using guara_rta::SafetyProfile;

InputManager::Config config()
{
  InputManager::Config c{};
  c[static_cast<std::size_t>(Channel::kLocalPosition)] = ChannelConfig{true, 0.2};
  c[static_cast<std::size_t>(Channel::kVehicleStatus)] = ChannelConfig{true, 1.0};
  c[static_cast<std::size_t>(Channel::kMonitor)] = ChannelConfig{true, 0.5};
  c[static_cast<std::size_t>(Channel::kDaa)] = ChannelConfig{true, 1.0};
  c[static_cast<std::size_t>(Channel::kGeofence)] = ChannelConfig{true, 0.2};
  return c;
}

constexpr std::uint32_t bit(Channel c) {return 1U << static_cast<unsigned>(c);}

// H-3: an enabled DAA channel that stops publishing sets V(k); it no longer reads as "no conflict".
TEST(ChannelGating, EnabledDaaChannelFailsClosed)
{
  InputManager m(config());
  m.onReceive(Channel::kLocalPosition, 1.0, true);
  m.onReceive(Channel::kVehicleStatus, 1.0, true);
  m.onReceive(Channel::kMonitor, 1.0, true);
  m.onReceive(Channel::kGeofence, 1.0, true);
  m.onReceive(Channel::kDaa, 1.0, true);
  EXPECT_EQ(0U, m.invalidMask(1.0));
  EXPECT_EQ(bit(Channel::kDaa), m.invalidMask(2.5) & bit(Channel::kDaa));
}

// H-5: a geofence sample reported invalid (xy_global false, failed projection) sets V(k).
TEST(ChannelGating, InvalidGeofenceSampleFailsClosed)
{
  InputManager m(config());
  m.onReceive(Channel::kGeofence, 1.0, false);
  EXPECT_EQ(bit(Channel::kGeofence), m.invalidMask(1.0) & bit(Channel::kGeofence));
}

// A disabled channel stays out of V(k): that is the documented way of flying without DAIDALUS.
TEST(ChannelGating, DisabledChannelIsIgnored)
{
  InputManager::Config c = config();
  c[static_cast<std::size_t>(Channel::kDaa)].enabled = false;
  InputManager m(c);
  m.onReceive(Channel::kLocalPosition, 1.0, true);
  m.onReceive(Channel::kVehicleStatus, 1.0, true);
  m.onReceive(Channel::kMonitor, 1.0, true);
  m.onReceive(Channel::kGeofence, 1.0, true);
  EXPECT_EQ(0U, m.invalidMask(1.0));
}

// The flight profile refuses a configuration that silently omits a protection channel.
TEST(SafetyProfileValidation, FlightProfileRejectsDisabledProtections)
{
  InputManager::Config c = config();
  c[static_cast<std::size_t>(Channel::kMonitor)].enabled = false;
  EXPECT_NE(nullptr, guara_rta::validateProfile(SafetyProfile::kFlight, c, 1, 0U));
  EXPECT_EQ(nullptr, guara_rta::validateProfile(SafetyProfile::kFlight, config(), 1, 0U));
}

// An omission has to be declared explicitly; then it is accepted and recorded.
TEST(SafetyProfileValidation, DeclaredOmissionIsAccepted)
{
  InputManager::Config c = config();
  c[static_cast<std::size_t>(Channel::kDaa)].enabled = false;
  EXPECT_NE(nullptr, guara_rta::validateProfile(SafetyProfile::kFlight, c, 1, 0U));
  EXPECT_EQ(nullptr, guara_rta::validateProfile(SafetyProfile::kFlight, c, 1,
    guara_rta::omission::kDaa));
}

// The flight profile requires at least one expected monitor: an enabled monitor channel with an
// empty expected list cannot detect a monitor that never starts.
TEST(SafetyProfileValidation, FlightProfileRequiresAnExpectedMonitor)
{
  EXPECT_NE(nullptr, guara_rta::validateProfile(SafetyProfile::kFlight, config(), 0, 0U));
}

// Every enabled channel needs a finite freshness bound, in both profiles.
TEST(SafetyProfileValidation, EnabledChannelNeedsFiniteMaxAge)
{
  InputManager::Config c = config();
  c[static_cast<std::size_t>(Channel::kLocalPosition)].max_age_s =
    std::numeric_limits<double>::infinity();
  EXPECT_NE(nullptr, guara_rta::validateProfile(SafetyProfile::kSitl, c, 1, 0xFFFFFFFFU));
}

// The SITL profile is permissive by design, but it is never the default of a flight build: the
// parser only accepts the two documented names.
TEST(SafetyProfileValidation, ProfileNamesAreClosedSet)
{
  SafetyProfile p{};
  EXPECT_EQ(nullptr, guara_rta::parseProfile("flight", &p));
  EXPECT_EQ(SafetyProfile::kFlight, p);
  EXPECT_EQ(nullptr, guara_rta::parseProfile("sitl", &p));
  EXPECT_EQ(SafetyProfile::kSitl, p);
  EXPECT_NE(nullptr, guara_rta::parseProfile("permissive", &p));
}

}  // namespace
