// SPDX-License-Identifier: Apache-2.0
//
// AC-3b: the owned Ogma template must subscribe with PX4-compatible QoS (BEST_EFFORT /
// SensorDataQoS) rather than the stock Ogma depth-10 RELIABLE profile [G 4.5, 3.6].
#include <fstream>
#include <sstream>
#include <string>

#include <gtest/gtest.h>

TEST(QosProfile, TemplateUsesSensorDataQos)
{
  std::ifstream in(GUARA_MONITORS_TEMPLATE);
  ASSERT_TRUE(in) << "missing template " << GUARA_MONITORS_TEMPLATE;
  std::ostringstream buf;
  buf << in.rdbuf();
  const std::string src = buf.str();
  EXPECT_NE(src.find("rclcpp::SensorDataQoS()"), std::string::npos)
    << "template must construct SensorDataQoS for PX4 /fmu/out subscriptions";
  EXPECT_EQ(src.find("\"{{varDeclId}}\", 10,"), std::string::npos)
    << "stock Ogma RELIABLE depth-10 subscription must not remain in the template";
}

int main(int argc, char ** argv)
{
  ::testing::InitGoogleTest(&argc, argv);
  return RUN_ALL_TESTS();
}
