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

add_library(guara_core
  src/types.cpp
  src/decision_core.cpp
  src/abi.cpp
)
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

  if(CMAKE_CXX_COMPILER_ID STREQUAL "GNU" AND NOT GUARA_CORE_SANITIZE)
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

  install(TARGETS guara_core EXPORT guara_coreTargets
    ARCHIVE DESTINATION lib LIBRARY DESTINATION lib RUNTIME DESTINATION bin)
  install(DIRECTORY include/ DESTINATION include)
  install(EXPORT guara_coreTargets
    FILE guara_coreConfig.cmake
    NAMESPACE guara::
    DESTINATION lib/cmake/guara_core)
endif()
