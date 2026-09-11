# SPDX-License-Identifier: Apache-2.0
# Ogma ROS application template for Guará monitors (ADR 0002 rule 1).
#
# Copied from ogma@69485b3442d76c48faaee30b37f9cbee212ceca6
# `ogma-core/templates/ros/` and patched so subscriptions use `rclcpp::SensorDataQoS()`
# (BEST_EFFORT) instead of depth-10 RELIABLE, which is incompatible with PX4
# `/fmu/out` publishers [G 4.5, 3.6].
#
# Generate with `./scripts/fm.sh ros2_ws/src/guara_monitors/scripts/generate.sh`.
# The Copilot C99 outputs are committed under `../generated/`. The ROS node that
# publishes `guara_msgs/MonitorVerdict` is hand-written (`../src/monitor_node.cpp`);
# Ogma's generated `copilot` package is a scratch artifact under `.ogma_out/`.
