# SPDX-License-Identifier: Apache-2.0
#
# guara-core: host-free switching kernel (ADR 0014 / M18).
# No ROS, no ament, no PX4, no Eigen. C++17, no heap after init.
cmake_minimum_required(VERSION 3.16)
project(guara_core VERSION 0.17.0 LANGUAGES C CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)

option(GUARA_CORE_SANITIZE "Instrument the kernel with ASan and UBSan (AC-62)" OFF)
if(GUARA_CORE_SANITIZE)
  if(NOT CMAKE_CXX_COMPILER_ID MATCHES "Clang|GNU")
    message(FATAL_ERROR "GUARA_CORE_SANITIZE requires GCC or Clang")
  endif()
  add_compile_options(
    -fsanitize=address,undefined
    -fno-omit-frame-pointer
    -fno-sanitize-recover=all)
  add_link_options(-fsanitize=address,undefined)
endif()

# Separate from sanitizers: gcov and ASan do not mix. AC-62 coverage is measured,
# not gated; the pass threshold is PARAMETER TBD.
option(GUARA_CORE_COVERAGE "Instrument the kernel with gcov (AC-62 measurement)" OFF)
if(GUARA_CORE_COVERAGE)
  if(GUARA_CORE_SANITIZE)
    message(FATAL_ERROR "GUARA_CORE_COVERAGE cannot be combined with GUARA_CORE_SANITIZE")
  endif()
  if(NOT CMAKE_CXX_COMPILER_ID STREQUAL "GNU")
    message(FATAL_ERROR "GUARA_CORE_COVERAGE requires GCC")
  endif()
  add_compile_options(--coverage -O0 -g)
  add_link_options(--coverage)
endif()

if(NOT CMAKE_SOURCE_DIR STREQUAL CMAKE_CURRENT_SOURCE_DIR)
  set(GUARA_CORE_STANDALONE OFF)
else()
  set(GUARA_CORE_STANDALONE ON)
endif()

if(GUARA_CORE_STANDALONE)
  if(MSVC)
    add_compile_options(/W4 /WX)
  else()
    add_compile_options(-Wall -Wextra -Wpedantic -Werror)
  endif()
endif()

set(GUARA_CORE_SOURCES
  src/types.cpp
  src/decision_core.cpp
  src/param_digest.cpp
  src/abi.cpp
  src/gateway_abi.cpp
  src/monitor_abi.cpp
  src/geofence_predictor.cpp
  src/geofence_abi.cpp
)

add_library(guara_core ${GUARA_CORE_SOURCES})
add_library(guara::core ALIAS guara_core)
target_include_directories(guara_core
  PUBLIC
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
    $<INSTALL_INTERFACE:include>
)
set_target_properties(guara_core PROPERTIES
  C_VISIBILITY_PRESET hidden
  CXX_VISIBILITY_PRESET hidden
  VISIBILITY_INLINES_HIDDEN ON
  POSITION_INDEPENDENT_CODE ON
  EXPORT_NAME core
)

if(GUARA_CORE_STANDALONE)
  include(CTest)
  add_executable(test_abi_storage test/test_abi_storage.c)
  target_link_libraries(test_abi_storage PRIVATE guara_core)
  add_test(NAME abi_storage COMMAND test_abi_storage)

  add_executable(test_abi_step test/test_abi_step.c)
  target_link_libraries(test_abi_step PRIVATE guara_core)
  add_test(NAME abi_step COMMAND test_abi_step)

  add_executable(test_abi_digest test/test_abi_digest.c)
  target_link_libraries(test_abi_digest PRIVATE guara_core)
  add_test(NAME abi_digest COMMAND test_abi_digest)

  add_executable(test_conformance test/test_conformance.c)
  target_link_libraries(test_conformance PRIVATE guara_core)
  file(TO_CMAKE_PATH "${CMAKE_CURRENT_SOURCE_DIR}/conformance/vectors" _guara_vectors_dir)
  target_compile_definitions(test_conformance PRIVATE
    "GUARA_VECTORS_DIR=\"${_guara_vectors_dir}\"")
  add_test(NAME conformance_spec_s3 COMMAND test_conformance)

  add_executable(test_core_params_vectors test/test_core_params_vectors.c)
  target_link_libraries(test_core_params_vectors PRIVATE guara_core)
  target_compile_definitions(test_core_params_vectors PRIVATE
    "GUARA_VECTORS_DIR=\"${_guara_vectors_dir}\"")
  add_test(NAME conformance_core_params COMMAND test_core_params_vectors)

  add_executable(test_gateway_vectors test/test_gateway_vectors.c)
  target_link_libraries(test_gateway_vectors PRIVATE guara_core)
  target_compile_definitions(test_gateway_vectors PRIVATE
    "GUARA_VECTORS_DIR=\"${_guara_vectors_dir}\"")
  add_test(NAME conformance_adr0010_gateway COMMAND test_gateway_vectors)

  add_executable(test_abi_monitor test/test_abi_monitor.c)
  target_link_libraries(test_abi_monitor PRIVATE guara_core)
  add_test(NAME abi_monitor COMMAND test_abi_monitor)

  add_executable(test_abi_geofence test/test_abi_geofence.c)
  target_link_libraries(test_abi_geofence PRIVATE  guara_core)
  add_test(NAME abi_geofence COMMAND test_abi_geofence)

  add_executable(test_geofence_vectors test/test_geofence_vectors.c)
  target_link_libraries(test_geofence_vectors PRIVATE guara_core)
  target_compile_definitions(test_geofence_vectors PRIVATE
    "GUARA_VECTORS_DIR=\"${_guara_vectors_dir}\"")
  add_test(NAME conformance_geofence COMMAND test_geofence_vectors)

  add_executable(test_monitor_vectors test/test_monitor_vectors.c)
  target_link_libraries(test_monitor_vectors PRIVATE guara_core)
  target_compile_definitions(test_monitor_vectors PRIVATE
    "GUARA_VECTORS_DIR=\"${_guara_vectors_dir}\"")
  add_test(NAME conformance_monitor_table COMMAND test_monitor_vectors)

  # gcov's runtime writes .gcda files (and may allocate); those probes are
  # for the unsanitized, uninstrumented kernel only.
  if(CMAKE_CXX_COMPILER_ID STREQUAL "GNU" AND NOT GUARA_CORE_SANITIZE
      AND NOT GUARA_CORE_COVERAGE)
    add_executable(test_abi_no_alloc test/test_abi_no_alloc.c test/malloc_trap.c)
    target_link_libraries(test_abi_no_alloc PRIVATE guara_core)
    target_link_options(test_abi_no_alloc PRIVATE
      -Wl,--wrap=malloc -Wl,--wrap=free -Wl,--wrap=calloc -Wl,--wrap=realloc)
    add_test(NAME abi_no_alloc COMMAND test_abi_no_alloc)

    add_executable(test_abi_freestanding test/test_abi_freestanding.c test/malloc_trap.c
      test/write_trap.c)
    target_link_libraries(test_abi_freestanding PRIVATE guara_core)
    target_link_options(test_abi_freestanding PRIVATE
      -Wl,--wrap=malloc -Wl,--wrap=free -Wl,--wrap=calloc -Wl,--wrap=realloc
      -Wl,--wrap=write)
    add_test(NAME abi_freestanding COMMAND test_abi_freestanding)
  endif()

  add_library(guara_cabi SHARED ${GUARA_CORE_SOURCES})
  target_include_directories(guara_cabi PUBLIC
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
    $<INSTALL_INTERFACE:include>)
  target_compile_definitions(guara_cabi PRIVATE GUARA_BUILD_SHARED)
  set_target_properties(guara_cabi PROPERTIES
    OUTPUT_NAME guara_cabi
    C_VISIBILITY_PRESET hidden
    CXX_VISIBILITY_PRESET hidden
    VISIBILITY_INLINES_HIDDEN ON
    POSITION_INDEPENDENT_CODE ON)

  include(GNUInstallDirs)
  include(CMakePackageConfigHelpers)
  install(TARGETS guara_core EXPORT guara_coreTargets
    ARCHIVE DESTINATION ${CMAKE_INSTALL_LIBDIR}
    LIBRARY DESTINATION ${CMAKE_INSTALL_LIBDIR}
    RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR})
  install(TARGETS guara_cabi
    ARCHIVE DESTINATION ${CMAKE_INSTALL_LIBDIR}
    LIBRARY DESTINATION ${CMAKE_INSTALL_LIBDIR}
    RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR})
  install(DIRECTORY include/ DESTINATION ${CMAKE_INSTALL_INCLUDEDIR})
  install(EXPORT guara_coreTargets
    FILE guara_coreTargets.cmake
    NAMESPACE guara::
    DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/guara_core)
  configure_package_config_file(
    cmake/guara_coreConfig.cmake.in
    "${CMAKE_CURRENT_BINARY_DIR}/guara_coreConfig.cmake"
    INSTALL_DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/guara_core)
  write_basic_package_version_file(
    "${CMAKE_CURRENT_BINARY_DIR}/guara_coreConfigVersion.cmake"
    VERSION ${PROJECT_VERSION}
    COMPATIBILITY SameMajorVersion)
  install(FILES
    "${CMAKE_CURRENT_BINARY_DIR}/guara_coreConfig.cmake"
    "${CMAKE_CURRENT_BINARY_DIR}/guara_coreConfigVersion.cmake"
    DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/guara_core)
endif()
