// SPDX-License-Identifier: Apache-2.0
#ifndef GUARA_DAIDALUS_CONVERT_HPP_
#define GUARA_DAIDALUS_CONVERT_HPP_

#include "guara_daidalus/evaluate.hpp"

#include <px4_msgs/msg/transponder_report.hpp>
#include <px4_msgs/msg/vehicle_global_position.hpp>
#include <px4_msgs/msg/vehicle_local_position.hpp>

namespace guara_daidalus
{

// Returns false if the report lacks coordinates, altitude, heading or velocity.
bool trafficFromReport(const px4_msgs::msg::TransponderReport & report, TrafficSi * out);

void ownshipFromPx4(
  const px4_msgs::msg::VehicleGlobalPosition & global,
  const px4_msgs::msg::VehicleLocalPosition & local,
  OwnshipSi * out);

}  // namespace guara_daidalus

#endif  // GUARA_DAIDALUS_CONVERT_HPP_
