# SPDX-License-Identifier: Apache-2.0
# Out-of-tree consumer (AC-57): finds the installed guara_core package.
cmake_minimum_required(VERSION 3.16)
# The installed archive is C++. The consumer source is C.
project(guara_core_consumer LANGUAGES C CXX)
find_package(guara_core REQUIRED)
add_executable(guara_core_consumer main.c)
target_link_libraries(guara_core_consumer PRIVATE guara::core)
