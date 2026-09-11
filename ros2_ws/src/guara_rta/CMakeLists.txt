# SPDX-License-Identifier: Apache-2.0
cmake_minimum_required(VERSION 3.8)
project(guara_rta)

if(NOT CMAKE_CXX_STANDARD)
  set(CMAKE_CXX_STANDARD 17)
  set(CMAKE_CXX_STANDARD_REQUIRED ON)
endif()
if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic -Werror)
endif()

find_package(ament_cmake REQUIRED)

# ROS-independent switching logic (SPEC §3). Linked by the arbiter node and by the unit tests.
add_library(guara_rta_core
  src/types.cpp
  src/decision_core.cpp
)
target_include_directories(guara_rta_core PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include>
)

install(DIRECTORY include/ DESTINATION include)
install(TARGETS guara_rta_core EXPORT export_guara_rta
  ARCHIVE DESTINATION lib LIBRARY DESTINATION lib RUNTIME DESTINATION bin)

# Arbiter process: ModeExecutor + owned CF gateway (SPEC §2, ADR 0001).
option(GUARA_SIM_FAULT_INJECTION "Enable SITL-only fault injection parameters (FM-4/FM-5)" OFF)
find_package(eigen3_cmake_module REQUIRED)
find_package(Eigen3 REQUIRED)
find_package(rclcpp REQUIRED)
find_package(px4_msgs REQUIRED)
find_package(px4_ros2_cpp REQUIRED)
find_package(guara_msgs REQUIRED)
find_package(guara_geofence REQUIRED)

add_executable(guara_rta_node src/arbiter_node.cpp)
target_include_directories(guara_rta_node PRIVATE
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>)
# Plain (non-keyword) target_link_libraries so ament_target_dependencies can
# append Humble rosidl import libraries without mixing signature styles.
target_link_libraries(guara_rta_node
  guara_rta_core
  guara_geofence::guara_geofence
  Eigen3::Eigen
  px4_ros2_cpp::px4_ros2_cpp
  rclcpp::rclcpp
)
# Humble rosidl packages expose includes/libs via ament_target_dependencies.
ament_target_dependencies(guara_rta_node guara_msgs px4_msgs)
if(GUARA_SIM_FAULT_INJECTION)
  target_compile_definitions(guara_rta_node PRIVATE GUARA_SIM_FAULT_INJECTION)
endif()

install(TARGETS guara_rta_node DESTINATION lib/${PROJECT_NAME})
install(DIRECTORY config DESTINATION share/${PROJECT_NAME})

if(BUILD_TESTING)
  find_package(ament_cmake_gtest REQUIRED)
  # Test names are the ctest selectors used by the acceptance criteria of SPEC §6.
  ament_add_gtest(decision_core_truth_table test/test_decision_core_truth_table.cpp)
  target_link_libraries(decision_core_truth_table guara_rta_core)
  ament_add_gtest(decision_core_no_alloc test/test_decision_core_no_alloc.cpp)
  target_link_libraries(decision_core_no_alloc guara_rta_core)
  ament_add_gtest(decision_core_timing test/test_decision_core_timing.cpp TIMEOUT 300)
  target_link_libraries(decision_core_timing guara_rta_core)
  target_compile_options(decision_core_timing PRIVATE -O2)
  ament_add_gtest(hysteresis_dwell test/test_hysteresis_dwell.cpp)
  target_link_libraries(hysteresis_dwell guara_rta_core)
  ament_add_gtest(latch_policy test/test_latch_policy.cpp TIMEOUT 300)
  target_link_libraries(latch_policy guara_rta_core)
  ament_add_gtest(gateway_blocks_cf test/test_gateway_blocks_cf.cpp)
  target_link_libraries(gateway_blocks_cf guara_rta_core)
endif()

ament_export_include_directories(include)
ament_export_targets(export_guara_rta HAS_LIBRARY_TARGET)
ament_package()
