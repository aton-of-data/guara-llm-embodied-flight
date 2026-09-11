// SPDX-License-Identifier: Apache-2.0
#include "guara_daidalus/convert.hpp"

#include <cmath>

namespace guara_daidalus
{

bool trafficFromReport(const px4_msgs::msg::TransponderReport & report, TrafficSi * out)
{
  using TR = px4_msgs::msg::TransponderReport;
  const std::uint16_t need = TR::PX4_ADSB_FLAGS_VALID_COORDS | TR::PX4_ADSB_FLAGS_VALID_ALTITUDE |
    TR::PX4_ADSB_FLAGS_VALID_HEADING | TR::PX4_ADSB_FLAGS_VALID_VELOCITY;
  if ((report.flags & need) != need || out == nullptr) {
    return false;
  }
  if (!std::isfinite(report.lat) || !std::isfinite(report.lon) || !std::isfinite(report.altitude)) {
    return false;
  }
  out->icao = report.icao_address;
  out->lat_deg = report.lat;
  out->lon_deg = report.lon;
  out->alt_m_amsl = static_cast<double>(report.altitude);
  out->track_rad = static_cast<double>(report.heading);
  out->gs_mps = static_cast<double>(report.hor_velocity);
  out->vs_mps_up = static_cast<double>(report.ver_velocity);
  return true;
}

void ownshipFromPx4(
  const px4_msgs::msg::VehicleGlobalPosition & global,
  const px4_msgs::msg::VehicleLocalPosition & local,
  OwnshipSi * out)
{
  if (out == nullptr) {
    return;
  }
  out->time_s = static_cast<double>(local.timestamp_sample) * 1e-6;
  out->lat_deg = global.lat;
  out->lon_deg = global.lon;
  out->alt_m_amsl = static_cast<double>(global.alt);
  out->gs_mps = std::hypot(static_cast<double>(local.vx), static_cast<double>(local.vy));
  out->vs_mps_up = -static_cast<double>(local.vz);
  if (out->gs_mps > 0.5) {
    out->track_rad = std::atan2(static_cast<double>(local.vy), static_cast<double>(local.vx));
  } else {
    out->track_rad = static_cast<double>(local.heading);
  }
  out->valid = global.lat_lon_valid && global.alt_valid && local.v_xy_valid && local.v_z_valid &&
    std::isfinite(out->lat_deg) && std::isfinite(out->lon_deg) && std::isfinite(out->alt_m_amsl);
}

}  // namespace guara_daidalus
