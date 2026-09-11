# SPDX-License-Identifier: Apache-2.0
cmake_minimum_required(VERSION 3.8)
project(guara_msgs)

find_package(ament_cmake REQUIRED)
find_package(builtin_interfaces REQUIRED)
find_package(rosidl_default_generators REQUIRED)

rosidl_generate_interfaces(${PROJECT_NAME}
  "msg/CfSetpoint.msg"
  "msg/DaaStatus.msg"
  "msg/MonitorVerdict.msg"
  "msg/RtaEvent.msg"
  "msg/RtaState.msg"
  DEPENDENCIES builtin_interfaces
)

ament_export_dependencies(rosidl_default_runtime)
ament_package()
