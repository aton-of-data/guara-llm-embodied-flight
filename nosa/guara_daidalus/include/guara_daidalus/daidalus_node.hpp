// SPDX-License-Identifier: Apache-2.0
#ifndef GUARA_DAIDALUS_DAIDALUS_NODE_HPP_
#define GUARA_DAIDALUS_DAIDALUS_NODE_HPP_

#include "guara_daidalus/convert.hpp"
#include "guara_daidalus/evaluate.hpp"

#include <cstddef>
#include <cstdint>

#include <guara_msgs/msg/daa_status.hpp>
#include <px4_msgs/msg/transponder_report.hpp>
#include <px4_msgs/msg/vehicle_global_position.hpp>
#include <px4_msgs/msg/vehicle_local_position.hpp>
#include <rclcpp/rclcpp.hpp>

namespace guara_daidalus
{

class DaidalusNode : public rclcpp::Node
{
public:
  DaidalusNode();

private:
  void onGlobal(const px4_msgs::msg::VehicleGlobalPosition & msg);
  void onLocal(const px4_msgs::msg::VehicleLocalPosition & msg);
  void onTraffic(const px4_msgs::msg::TransponderReport & msg);
  void publishStatus();

  Evaluator evaluator_;
  OwnshipSi own_{};
  TrafficSi traffic_[kMaxTraffic]{};
  std::uint64_t traffic_stamp_us_[kMaxTraffic]{};
  std::size_t traffic_count_{0};
  bool have_global_{false};
  bool have_local_{false};
  px4_msgs::msg::VehicleGlobalPosition last_global_{};
  px4_msgs::msg::VehicleLocalPosition last_local_{};

  rclcpp::Subscription<px4_msgs::msg::VehicleGlobalPosition>::SharedPtr global_sub_;
  rclcpp::Subscription<px4_msgs::msg::VehicleLocalPosition>::SharedPtr local_sub_;
  rclcpp::Subscription<px4_msgs::msg::TransponderReport>::SharedPtr traffic_sub_;
  rclcpp::Publisher<guara_msgs::msg::DaaStatus>::SharedPtr status_pub_;
  rclcpp::TimerBase::SharedPtr timer_;
};

}  // namespace guara_daidalus

#endif  // GUARA_DAIDALUS_DAIDALUS_NODE_HPP_
