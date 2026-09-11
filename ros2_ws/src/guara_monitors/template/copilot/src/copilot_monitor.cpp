// SPDX-License-Identifier: Apache-2.0
//
// Derived from the ROS application template of Ogma v1.15.0 (github.com/nasa/ogma,
// Apache-2.0; commit pinned in third_party/VERSIONS.md), adapted for Guara. Ogma is
// released by NASA; this derivative is not endorsed by NASA (see NOTICE).
#include <functional>
#include <memory>

#include "rclcpp/rclcpp.hpp"

#include "std_msgs/msg/bool.hpp"
#include "std_msgs/msg/empty.hpp"
#include "std_msgs/msg/u_int8.hpp"
#include "std_msgs/msg/u_int16.hpp"
#include "std_msgs/msg/u_int32.hpp"
#include "std_msgs/msg/u_int64.hpp"
#include "std_msgs/msg/int8.hpp"
#include "std_msgs/msg/int16.hpp"
#include "std_msgs/msg/int32.hpp"
#include "std_msgs/msg/int64.hpp"
#include "std_msgs/msg/float32.hpp"
#include "std_msgs/msg/float64.hpp"
#include <cstdint>
{{#impl_extra_header}}
{{{.}}}
{{/impl_extra_header}}
{{#copilot}}
#include "{{{copilot.specName}}}_types.h"
#include "{{{copilot.specName}}}.h"
#include "{{{copilot.specName}}}.c"
{{/copilot}}

using std::placeholders::_1;

{{#variables}}
{{varDeclType}} {{varDeclName}};
{{/variables}}

class CopilotRV : public rclcpp::Node {
  public:
    CopilotRV() : Node("copilotrv") {
      // PX4 /fmu/out publishers are BEST_EFFORT TRANSIENT_LOCAL [G 3.6]; the stock Ogma
      // template used depth 10 (RELIABLE) and received no samples [G 4.5].
      const rclcpp::QoS sensor_qos = rclcpp::SensorDataQoS();
      {{#variables}}
      {{varDeclName}}_subscription_ = this->create_subscription<{{varDeclMsgType}}>(
        "{{varDeclId}}", sensor_qos,
        std::bind(&CopilotRV::{{varDeclName}}_callback, this, _1));

      {{/variables}}
      {{#monitors}}
      {{#monitorMsgType}}
      {{monitorName}}_publisher_ = this->create_publisher<{{.}}>(
        "copilot/{{monitorName}}", 10);
      {{/monitorMsgType}}
      {{^monitorMsgType}}
      {{monitorName}}_publisher_ = this->create_publisher<std_msgs::msg::Empty>(
        "copilot/{{monitorName}}", 10);
      {{/monitorMsgType}}

      {{/monitors}}
    }

{{#monitors}}
    {{#monitorType}}
    // Report (publish) monitor violations.
    void {{monitorName}}({{.}} arg) {
      {{#monitorMsgType}}
      auto output = {{.}}();
      output.data = arg;
      {{/monitorMsgType}}
      {{^monitorMsgType}}
      auto output = std_msgs::msg::Empty();
      {{/monitorMsgType}}
      {{monitorName}}_publisher_->publish(output);
    }
    {{/monitorType}}
    {{^monitorType}}
    // Report (publish) monitor violations.
    void {{monitorName}}() {
      auto output = std_msgs::msg::Empty();
      {{monitorName}}_publisher_->publish(output);
    }
    {{/monitorType}}

{{/monitors}}
    // Needed so we can report messages to the log.
    static CopilotRV& getInstance() {
      static CopilotRV instance;
      return instance;
    }

  private:
    {{#variables}}
    void {{varDeclName}}_callback(const {{varDeclMsgType}}::SharedPtr msg) const {
      {{#varDeclMsgField}}
      {{varDeclName}} = msg->{{.}};
      {{/varDeclMsgField}}
      {{^varDeclMsgField}}
      {{varDeclName}} = msg->data;
      {{/varDeclMsgField}}
      step();
    }

    {{/variables}}
    {{#variables}}
    rclcpp::Subscription<{{varDeclMsgType}}>::SharedPtr {{varDeclName}}_subscription_;

    {{/variables}}
    {{#monitors}}
    {{#monitorMsgType}}
    rclcpp::Publisher<{{.}}>::SharedPtr {{monitorName}}_publisher_;
    {{/monitorMsgType}}
    {{^monitorMsgType}}
    rclcpp::Publisher<std_msgs::msg::Empty>::SharedPtr {{monitorName}}_publisher_;
    {{/monitorMsgType}}

    {{/monitors}}
};

{{#monitors}}
// Pass monitor violations to the actual class, which has ways to
// communicate with other applications.
{{#monitorType}}
void {{monitorName}}({{.}} arg) {
  CopilotRV::getInstance().{{monitorName}}(arg);
}
{{/monitorType}}
{{^monitorType}}
void {{monitorName}}() {
  CopilotRV::getInstance().{{monitorName}}();
}
{{/monitorType}}

{{/monitors}}
int main(int argc, char* argv[]) {
  rclcpp::init(argc, argv);
  rclcpp::spin(std::make_shared<CopilotRV>());
  rclcpp::shutdown();
  return 0;
}

