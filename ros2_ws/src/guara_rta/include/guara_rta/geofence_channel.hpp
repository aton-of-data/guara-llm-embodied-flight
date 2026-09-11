// SPDX-License-Identifier: Apache-2.0
//
// GeofenceChannel: adapter between vehicle_local_position_v1 and the geofence predictor (ADR 0004).
// The fence polygon is configured in geographic coordinates and projected into the local NED frame
// with the estimator reference point carried by each sample; a change of the reference point triggers
// reprojection. A sample without a valid global reference (xy_global false) or without valid position
// and velocity is reported as an invalid geofence input, which sets V(k) on the enabled geofence
// channel (review 2026-09-11 H-5) instead of reading as "no violation".
//
// The channel also answers the shadow question "would this proposed velocity violate the fence?"
// (review §4). The decision group writes the most recent vehicle state into a lock-free snapshot;
// the gateway callback, which runs in another callback group, reads it to filter CF setpoints before
// they reach PX4. The snapshot is a two-slot sequence buffer: single writer, wait-free reader, no
// allocation and no lock on either path.
#pragma once

#include <array>
#include <atomic>
#include <cstdint>
#include <limits>
#include <stdexcept>
#include <string>
#include <vector>

#include <px4_msgs/msg/vehicle_local_position.hpp>
#include <rclcpp/rclcpp.hpp>

#include "guara_geofence/predictor.hpp"
#include "guara_rta/gateway_logic.hpp"

namespace guara_rta
{

struct GeofenceSample
{
  double t_gf_s{std::numeric_limits<double>::infinity()};
  bool valid{false};
  bool inside{true};
};

class GeofenceChannel
{
public:
  void configure(rclcpp::Node & node)
  {
    enabled_ = node.declare_parameter("geofence.enabled", false);
    const auto flat = node.declare_parameter("geofence.polygon_lat_lon_deg", std::vector<double>{});
    fence_.alt_min_m = node.declare_parameter("geofence.alt_min_m", -1.0e9);
    fence_.alt_max_m = node.declare_parameter("geofence.alt_max_m", 1.0e9);
    params_.a_brake_h_m_s2 = node.declare_parameter("geofence.a_brake_h_m_s2", params_.a_brake_h_m_s2);
    params_.a_brake_v_m_s2 = node.declare_parameter("geofence.a_brake_v_m_s2", params_.a_brake_v_m_s2);
    params_.k_sigma = node.declare_parameter("geofence.k_sigma", params_.k_sigma);
    params_.v_min_m_s = node.declare_parameter("geofence.v_min_m_s", params_.v_min_m_s);
    params_.horizon_s = node.declare_parameter("geofence.horizon_s", params_.horizon_s);
    if (!enabled_) {
      return;
    }
    if (flat.size() % 2U != 0U || flat.size() / 2U < 3U || flat.size() / 2U > guara_geofence::kMaxVertices) {
      throw std::invalid_argument("geofence.polygon_lat_lon_deg must hold 3..64 (lat, lon) pairs");
    }
    n_ = flat.size() / 2U;
    for (std::size_t i = 0; i < n_; ++i) {
      lat_lon_[i] = {flat[2U * i], flat[2U * i + 1U]};
    }
    if (const char * err = guara_geofence::validate(params_)) {
      throw std::invalid_argument(std::string("geofence parameters: ") + err);
    }
  }

  bool enabled() const noexcept {return enabled_;}

  GeofenceSample update(const px4_msgs::msg::VehicleLocalPosition & msg, bool state_valid)
  {
    GeofenceSample out;
    if (!msg.xy_global || !state_valid) {
      invalidateSnapshot();
      return out;
    }
    if (!projected_ || msg.ref_timestamp != ref_timestamp_ || msg.ref_lat != ref_lat_ ||
      msg.ref_lon != ref_lon_)
    {
      std::array<guara_geofence::Vec2, guara_geofence::kMaxVertices> local{};
      for (std::size_t i = 0; i < n_; ++i) {
        local[i] = guara_geofence::projectToLocal(lat_lon_[i].x, lat_lon_[i].y, msg.ref_lat, msg.ref_lon);
      }
      if (fence_.polygon.set(local.data(), n_) != guara_geofence::PolygonError::kNone) {
        projected_ = false;
        invalidateSnapshot();
        return out;
      }
      ref_timestamp_ = msg.ref_timestamp;
      ref_lat_ = msg.ref_lat;
      ref_lon_ = msg.ref_lon;
      projected_ = true;
    }
    guara_geofence::VehicleState s;
    s.position = {msg.x, msg.y};
    s.altitude_m = -static_cast<double>(msg.z);
    s.velocity = {msg.vx, msg.vy};
    s.climb_rate_m_s = -static_cast<double>(msg.vz);
    s.eph_m = msg.eph;
    s.epv_m = msg.epv;
    publishSnapshot(s);
    const guara_geofence::Prediction p = guara_geofence::predict(fence_, params_, s);
    out.t_gf_s = p.t_gf_s;
    out.inside = p.inside;
    out.valid = true;
    return out;
  }

  // Predicted T_gf if the vehicle followed `velocity_ned_m_s` from the latest known position.
  // Returns +inf when no usable snapshot exists (the caller decides what that means).
  double predictWithVelocity(const std::array<float, 3> & velocity_ned_m_s, bool * have_state) const
  {
    guara_geofence::VehicleState s;
    const bool ok = readSnapshot(&s);
    if (have_state != nullptr) {
      *have_state = ok;
    }
    if (!ok) {
      return std::numeric_limits<double>::infinity();
    }
    s.velocity = {static_cast<double>(velocity_ned_m_s[0]), static_cast<double>(velocity_ned_m_s[1])};
    s.climb_rate_m_s = -static_cast<double>(velocity_ned_m_s[2]);
    return guara_geofence::predict(fence_, params_, s).t_gf_s;
  }

private:
  struct Snapshot
  {
    guara_geofence::VehicleState state{};
    bool valid{false};
  };

  void publishSnapshot(const guara_geofence::VehicleState & s) noexcept
  {
    const std::uint32_t c = snapshot_seq_.load(std::memory_order_relaxed);
    snapshot_[(c + 1U) & 1U] = Snapshot{s, true};
    snapshot_seq_.store(c + 1U, std::memory_order_release);
  }

  void invalidateSnapshot() noexcept
  {
    const std::uint32_t c = snapshot_seq_.load(std::memory_order_relaxed);
    snapshot_[(c + 1U) & 1U] = Snapshot{};
    snapshot_seq_.store(c + 1U, std::memory_order_release);
  }

  bool readSnapshot(guara_geofence::VehicleState * out) const noexcept
  {
    for (int attempt = 0; attempt < 2; ++attempt) {
      const std::uint32_t before = snapshot_seq_.load(std::memory_order_acquire);
      if (before == 0U) {
        return false;
      }
      const Snapshot s = snapshot_[before & 1U];
      if (snapshot_seq_.load(std::memory_order_acquire) == before) {
        if (!s.valid) {
          return false;
        }
        *out = s.state;
        return true;
      }
    }
    return false;
  }

  bool enabled_{false};
  bool projected_{false};
  std::size_t n_{0};
  std::array<guara_geofence::Vec2, guara_geofence::kMaxVertices> lat_lon_{};  // x = lat, y = lon
  guara_geofence::Fence fence_{};
  guara_geofence::PredictorParameters params_{};
  std::uint64_t ref_timestamp_{0};
  double ref_lat_{0.0};
  double ref_lon_{0.0};
  Snapshot snapshot_[2]{};
  std::atomic<std::uint32_t> snapshot_seq_{0};
};

// Shadow check installed in the gateway: a proposed CF velocity is admissible only if its predicted
// time to geofence violation stays above tau_gf + h_gf, the same margin the decision core requires
// before returning control to the CF (SPEC §3.5). The check runs in the setpoint callback, so it is
// allocation-free and bounded by the predictor cost.
class GeofenceSetpointGuard : public SetpointGuard
{
public:
  GeofenceSetpointGuard(const GeofenceChannel & channel, double margin_s) noexcept
  : channel_(channel), margin_s_(margin_s) {}

  bool admissible(const std::array<float, 3> & velocity_ned_m_s, double) const noexcept override
  {
    bool have_state = false;
    const double t_gf = channel_.predictWithVelocity(velocity_ned_m_s, &have_state);
    if (!have_state) {
      // No usable position: the geofence channel is invalid, the core is about to see V(k) and the
      // gateway must not forward CF motion in the meantime.
      return false;
    }
    return t_gf > margin_s_;
  }

private:
  const GeofenceChannel & channel_;
  double margin_s_;
};

}  // namespace guara_rta
