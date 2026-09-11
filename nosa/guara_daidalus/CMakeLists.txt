# SPDX-License-Identifier: Apache-2.0
cmake_minimum_required(VERSION 3.8)
project(guara_daidalus)

if(NOT CMAKE_CXX_STANDARD)
  set(CMAKE_CXX_STANDARD 17)
  set(CMAKE_CXX_STANDARD_REQUIRED ON)
endif()

if(NOT DEFINED DAIDALUS_ROOT)
  get_filename_component(GUARA_ROOT "${CMAKE_CURRENT_SOURCE_DIR}/../.." ABSOLUTE)
  set(DAIDALUS_ROOT "${GUARA_ROOT}/third_party/daidalus")
endif()
set(DAIDALUS_CPP "${DAIDALUS_ROOT}/C++")
if(NOT EXISTS "${DAIDALUS_CPP}/include/Daidalus.h")
  message(FATAL_ERROR
    "DAIDALUS C++ headers not found at ${DAIDALUS_CPP}. Run scripts/fetch_third_party.sh")
endif()

file(GLOB DAIDALUS_SRC CONFIGURE_DEPENDS "${DAIDALUS_CPP}/src/*.cpp")
add_library(daidalus_core STATIC ${DAIDALUS_SRC})
target_include_directories(daidalus_core SYSTEM PUBLIC "${DAIDALUS_CPP}/include")
target_compile_options(daidalus_core PRIVATE -w)
set_target_properties(daidalus_core PROPERTIES POSITION_INDEPENDENT_CODE ON)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  set(GUARA_WARNINGS -Wall -Wextra -Wpedantic -Werror)
endif()

find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(px4_msgs REQUIRED)
find_package(px4_ros2_cpp REQUIRED)
find_package(guara_msgs REQUIRED)

add_library(guara_daidalus_eval src/evaluate.cpp src/convert.cpp)
target_include_directories(guara_daidalus_eval PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
)
target_compile_options(guara_daidalus_eval PRIVATE ${GUARA_WARNINGS})
target_link_libraries(guara_daidalus_eval daidalus_core)
ament_target_dependencies(guara_daidalus_eval px4_msgs)

add_library(guara_daidalus_node_lib src/daidalus_node.cpp)
target_include_directories(guara_daidalus_node_lib PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
)
target_compile_options(guara_daidalus_node_lib PRIVATE ${GUARA_WARNINGS})
target_link_libraries(guara_daidalus_node_lib
  guara_daidalus_eval
  px4_ros2_cpp::px4_ros2_cpp
  rclcpp::rclcpp
)
ament_target_dependencies(guara_daidalus_node_lib guara_msgs px4_msgs)

add_executable(daidalus_node src/main.cpp)
target_compile_options(daidalus_node PRIVATE ${GUARA_WARNINGS})
target_link_libraries(daidalus_node guara_daidalus_node_lib)
ament_target_dependencies(daidalus_node rclcpp)

install(TARGETS daidalus_node DESTINATION lib/${PROJECT_NAME})
install(FILES LICENSE LICENSE.pdf CHANGES.md README.md DESTINATION share/${PROJECT_NAME})

if(BUILD_TESTING)
  find_package(ament_cmake_gtest REQUIRED)
  ament_add_gtest(daa_equivalence test/test_daa_equivalence.cpp)
  target_compile_options(daa_equivalence PRIVATE ${GUARA_WARNINGS})
  target_link_libraries(daa_equivalence
    guara_daidalus_eval
    guara_daidalus_node_lib
    daidalus_core
    px4_ros2_cpp::px4_ros2_cpp
    rclcpp::rclcpp
  )
  ament_target_dependencies(daa_equivalence guara_msgs px4_msgs)
endif()

ament_package()
