# SPDX-License-Identifier: Apache-2.0
# Periodic snapshot of the arbiter, published at a reduced rate for observation and logging.
# Constants follow guara_msgs/RtaEvent.

uint64 tick
float64 t_s                 # arbiter monotonic clock
uint8 state
uint8 rf
uint32 cause_mask           # causes true at this tick
float64 t_daa_s
float64 t_gf_s
float64 clear_duration_s    # Cdur(k)
uint16 switches_in_window   # S(k)
bool in_charge              # IC(k)
bool owned_mode_active
float64 max_tick_duration_s # maximum observed DecisionCore::step duration since start
float64 t_last_cmd_pub_s    # most recent recovery or return command publication
float64 t_last_ack_s        # most recent accepted acknowledgement
float64 l0_s                # last local_position timestamp - timestamp_sample [s]
float64 clock_err_s         # ROS recv - PX4 timestamp [s] (AC-19)
float64 t_px4_timestamp_s
float64 t_ros_recv_s
