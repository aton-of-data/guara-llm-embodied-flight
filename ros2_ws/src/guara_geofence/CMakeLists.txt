# SPDX-License-Identifier: Apache-2.0
cmake_minimum_required(VERSION 3.8)
project(guara_geofence)

if(NOT CMAKE_CXX_STANDARD)
  set(CMAKE_CXX_STANDARD 17)
  set(CMAKE_CXX_STANDARD_REQUIRED ON)
endif()
if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic -Werror)
endif()

find_package(ament_cmake REQUIRED)

# Host-free predictor (ADR 0004) lives in core/. The include path
# guara_geofence/predictor.hpp is unchanged so the existing unit tests
# need no edits (AC-58).
set(GUARA_CORE_DIR "${CMAKE_CURRENT_SOURCE_DIR}/../../../core")
add_library(guara_geofence ${GUARA_CORE_DIR}/src/geofence_predictor.cpp)
target_include_directories(guara_geofence PUBLIC
  $<BUILD_INTERFACE:${GUARA_CORE_DIR}/include>
  $<INSTALL_INTERFACE:include>
)
set_target_properties(guara_geofence PROPERTIES POSITION_INDEPENDENT_CODE ON)

install(DIRECTORY "${GUARA_CORE_DIR}/include/guara_geofence" DESTINATION include)
install(TARGETS guara_geofence EXPORT export_guara_geofence
  ARCHIVE DESTINATION lib LIBRARY DESTINATION lib RUNTIME DESTINATION bin)

if(BUILD_TESTING)
  find_package(ament_cmake_gtest REQUIRED)
  ament_add_gtest(predictor_analytic test/test_predictor_analytic.cpp)
  target_link_libraries(predictor_analytic guara_geofence)
  # Review remediation of 2026-09-11 §4: heading-independent position uncertainty.
  ament_add_gtest(predictor_uncertainty test/test_predictor_uncertainty.cpp)
  target_link_libraries(predictor_uncertainty guara_geofence)
endif()

ament_export_include_directories(include)
ament_export_targets(export_guara_geofence HAS_LIBRARY_TARGET)
ament_package()
