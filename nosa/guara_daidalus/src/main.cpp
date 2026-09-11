// SPDX-License-Identifier: Apache-2.0
#include "guara_daidalus/daidalus_node.hpp"

#include <memory>

int main(int argc, char ** argv)
{
  rclcpp::init(argc, argv);
  rclcpp::spin(std::make_shared<guara_daidalus::DaidalusNode>());
  rclcpp::shutdown();
  return 0;
}
