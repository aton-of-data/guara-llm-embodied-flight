// SPDX-License-Identifier: Apache-2.0
//
// GeofenceChannel: adapter between vehicle_local_position_v1 and the geofence predictor (ADR 0004).
// The fence polygon is configured in geographic coordinates and projected into the local NED frame
// with the estimator reference point carried by each sample; a change of the reference point triggers
// reprojection. A sample without a valid global reference (xy_global false) or without valid position
// and velocity is reported as an invalid geofence input.
#pragma once

#include <array>
#include <cstdint>
#include <limits>
#include <stdexcept>
#include <string>
#include <vector>

#include <px4_msgs/msg/vehicle_local_position.hpp>
#include <rclcpp/rclcpp.hpp>

#include "guara_geofence/predictor.hpp"

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
    const guara_geofence::Prediction p = guara_geofence::predict(fence_, params_, s);
    out.t_gf_s = p.t_gf_s;
    out.inside = p.inside;
    out.valid = true;
    return out;
  }

private:
  bool enabled_{false};
  bool projected_{false};
  std::size_t n_{0};
  std::array<guara_geofence::Vec2, guara_geofence::kMaxVertices> lat_lon_{};  // x = lat, y = lon
  guara_geofence::Fence fence_{};
  guara_geofence::PredictorParameters params_{};
  std::uint64_t ref_timestamp_{0};
  double ref_lat_{0.0};
  double ref_lon_{0.0};
};

}  // namespace guara_rta
