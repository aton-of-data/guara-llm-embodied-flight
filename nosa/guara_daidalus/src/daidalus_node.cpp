// SPDX-License-Identifier: Apache-2.0
//
// PX4 SensorDataQoS subscriptions [G 3.6, 4.5]; publishes DaaStatus for the arbiter DAA channel.
#include "guara_daidalus/daidalus_node.hpp"

#include <chrono>

#include <px4_ros2/utils/message_version.hpp>

namespace guara_daidalus
{
namespace
{

constexpr double kTrafficMaxAgeS = 5.0;

builtin_interfaces::msg::Time stampFromUs(std::uint64_t timestamp_us)
{
  builtin_interfaces::msg::Time stamp;
  stamp.sec = static_cast<std::int32_t>(timestamp_us / 1000000ULL);
  stamp.nanosec = static_cast<std::uint32_t>((timestamp_us % 1000000ULL) * 1000ULL);
  return stamp;
}

}  // namespace

DaidalusNode::DaidalusNode()
: Node("guara_daidalus")
{
  const auto qos = rclcpp::SensorDataQoS();
  global_sub_ = create_subscription<px4_msgs::msg::VehicleGlobalPosition>(
    "fmu/out/vehicle_global_position" +
      px4_ros2::getMessageNameVersion<px4_msgs::msg::VehicleGlobalPosition>(),
    qos, [this](const px4_msgs::msg::VehicleGlobalPosition & msg) {onGlobal(msg);});
  local_sub_ = create_subscription<px4_msgs::msg::VehicleLocalPosition>(
    "fmu/out/vehicle_local_position" +
      px4_ros2::getMessageNameVersion<px4_msgs::msg::VehicleLocalPosition>(),
    qos, [this](const px4_msgs::msg::VehicleLocalPosition & msg) {onLocal(msg);});
  traffic_sub_ = create_subscription<px4_msgs::msg::TransponderReport>(
    "fmu/out/transponder_report" +
      px4_ros2::getMessageNameVersion<px4_msgs::msg::TransponderReport>(),
    qos, [this](const px4_msgs::msg::TransponderReport & msg) {onTraffic(msg);});
  status_pub_ = create_publisher<guara_msgs::msg::DaaStatus>(
    "/guara/daa/status", rclcpp::QoS(1).best_effort());
  timer_ = create_wall_timer(std::chrono::milliseconds(200), [this]() {publishStatus();});
}

void DaidalusNode::onGlobal(const px4_msgs::msg::VehicleGlobalPosition & msg)
{
  have_global_ = true;
  last_global_ = msg;
}

void DaidalusNode::onLocal(const px4_msgs::msg::VehicleLocalPosition & msg)
{
  have_local_ = true;
  last_local_ = msg;
}

void DaidalusNode::onTraffic(const px4_msgs::msg::TransponderReport & msg)
{
  TrafficSi sample{};
  if (!trafficFromReport(msg, &sample)) {
    return;
  }
  std::size_t slot = traffic_count_;
  for (std::size_t i = 0; i < traffic_count_; ++i) {
    if (traffic_[i].icao == sample.icao) {
      slot = i;
      break;
    }
  }
  if (slot == traffic_count_) {
    if (traffic_count_ >= kMaxTraffic) {
      return;
    }
    ++traffic_count_;
  }
  traffic_[slot] = sample;
  traffic_stamp_us_[slot] = msg.timestamp;
}

void DaidalusNode::publishStatus()
{
  guara_msgs::msg::DaaStatus msg;
  if (have_global_ && have_local_) {
    ownshipFromPx4(last_global_, last_local_, &own_);
  } else {
    own_.valid = false;
  }
  msg.stamp = stampFromUs(last_local_.timestamp_sample);

  const double now_s = static_cast<double>(last_local_.timestamp_sample) * 1e-6;
  TrafficSi live[kMaxTraffic];
  std::size_t n = 0;
  for (std::size_t i = 0; i < traffic_count_; ++i) {
    const double age = now_s - static_cast<double>(traffic_stamp_us_[i]) * 1e-6;
    if (age > kTrafficMaxAgeS) {
      continue;
    }
    live[n++] = traffic_[i];
  }

  const DaaEvaluation ev = evaluator_.evaluate(own_, live, n);
  msg.time_to_corrective_volume_s = ev.t_daa_s;
  msg.alert_level = ev.alert_level;
  msg.num_intruders = ev.num_intruders;
  msg.critical_intruder_icao = ev.critical_intruder_icao;
  msg.ownship_valid = ev.ownship_valid;
  status_pub_->publish(msg);
}

}  // namespace guara_daidalus
