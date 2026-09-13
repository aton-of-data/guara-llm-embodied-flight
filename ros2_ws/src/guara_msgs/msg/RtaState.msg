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

# --- added by the review remediation of 2026-09-11 ---
uint32 invalid_mask         # InputManager channel bits that set V(k) at this tick
uint8 nav_state             # vehicle_status.nav_state observed by the arbiter
uint8 safety_profile        # 0 = sitl, 1 = flight (guara_rta::SafetyProfile)
uint32 accepted_omissions   # declared protection omissions (1 = daa, 2 = monitors, 4 = geofence)
bool actuation_failed       # a mode request was not accepted, or was accepted without effect
bool cf_intent_unsafe       # the CF's proposed setpoint would violate the fence (shadow check)
float64 cf_intent_t_gf_s    # T_gf predicted on the CF's proposed velocity
uint32 cf_rejected_stamp    # CF setpoints rejected for an implausible stamp
uint32 cf_rejected_non_finite
uint32 cf_rejected_guard    # CF setpoints blocked by the shadow guard
uint32 cf_clamped           # CF setpoints clamped to the gateway envelope

# --- G-K8: the running core names itself on every snapshot ---
string core_version         # GUARA_CORE_VERSION of the linked kernel
string abi_version          # GUARA_ABI_VERSION (provisional until three ports pass the kit)
uint8[8] param_digest       # FNV-1a-64 of the canonical core parameter fields

