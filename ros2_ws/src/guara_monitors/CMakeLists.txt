# SPDX-License-Identifier: Apache-2.0
cmake_minimum_required(VERSION 3.8)
project(guara_monitors)

if(NOT CMAKE_CXX_STANDARD)
  set(CMAKE_CXX_STANDARD 17)
  set(CMAKE_CXX_STANDARD_REQUIRED ON)
endif()
if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic -Werror)
endif()

find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(px4_msgs REQUIRED)
find_package(px4_ros2_cpp REQUIRED)
find_package(guara_msgs REQUIRED)

set(GENERATED_DIR ${CMAKE_CURRENT_SOURCE_DIR}/generated)
if(EXISTS ${GENERATED_DIR}/copilot.c)
  add_library(guara_copilot_c STATIC ${GENERATED_DIR}/copilot.c)
  set_target_properties(guara_copilot_c PROPERTIES C_STANDARD 99)
  target_include_directories(guara_copilot_c PUBLIC ${GENERATED_DIR})
  # Copilot C99 is generated; do not fail the package on its unused includes.
  target_compile_options(guara_copilot_c PRIVATE -Wno-unused-parameter)

  add_executable(guara_monitors_node src/monitor_node.cpp)
  target_include_directories(guara_monitors_node PRIVATE ${GENERATED_DIR})
  target_link_libraries(guara_monitors_node
    guara_copilot_c
    px4_ros2_cpp::px4_ros2_cpp
    rclcpp::rclcpp)
  ament_target_dependencies(guara_monitors_node px4_msgs guara_msgs)
  install(TARGETS guara_monitors_node DESTINATION lib/${PROJECT_NAME})
endif()

if(BUILD_TESTING)
  find_package(ament_cmake_gtest REQUIRED)
  ament_add_gtest(qos_profile test/test_qos_profile.cpp)
  target_compile_definitions(qos_profile PRIVATE
    GUARA_MONITORS_TEMPLATE="${CMAKE_CURRENT_SOURCE_DIR}/template/copilot/src/copilot_monitor.cpp")
  if(TARGET guara_copilot_c)
    ament_add_gtest(copilot_alt test/test_copilot_alt.cpp)
    target_link_libraries(copilot_alt guara_copilot_c)
  endif()
endif()

ament_package()
