# SPDX-License-Identifier: Apache-2.0
# Out-of-tree consumer (AC-57): finds guara_core via the build tree or install.
cmake_minimum_required(VERSION 3.16)
project(guara_core_consumer LANGUAGES C)
add_executable(guara_core_consumer main.c)
if(TARGET guara::core)
  target_link_libraries(guara_core_consumer PRIVATE guara::core)
else()
  find_package(guara_core REQUIRED)
  target_link_libraries(guara_core_consumer PRIVATE guara::guara_core)
endif()
