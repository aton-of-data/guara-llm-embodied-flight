# SPDX-License-Identifier: Apache-2.0
# State transition of the Guará decision core (SPEC §3.5). All times are seconds on the monotonic
# (steady) clock of the arbiter process unless stated otherwise; NaN marks an unavailable time.

uint8 STATE_INACTIVE=0
uint8 STATE_CF=1
uint8 STATE_RF=2
uint8 STATE_LATCHED=3

uint8 RF_NONE=0
uint8 RF_HOLD=1
uint8 RF_RTL=2
uint8 RF_LAND=3

# Cause bits (SPEC §3.4 predicate U and transition labels).
uint32 CAUSE_DAA=1          # T_daa <= tau_daa
uint32 CAUSE_GEOFENCE=2     # T_gf <= tau_gf
uint32 CAUSE_MONITOR=4      # M(k)
uint32 CAUSE_INPUT=8        # V(k)
uint32 CAUSE_LATCH=16       # S(k) >= N_max
uint32 CAUSE_RETURN=32      # T5 return to CF
uint32 CAUSE_NOT_IN_CHARGE=64
uint32 CAUSE_ESCALATION=128
uint32 CAUSE_ACTUATION=256  # recovery command not acknowledged within the retry budget (FM-7)

uint64 tick
uint8 transition            # 1..7 for T1..T7 (2b encoded as 8), 9 for the FM-7 actuation latch
uint8 state_from
uint8 state_to
uint8 rf_from
uint8 rf_to
uint32 cause_mask

float64 t_decide_s          # tick instant t_k (arbiter steady clock)
float64 t_input_recv_s      # reception instant of the most recent input that made U true (steady)
float64 t_input_stamp_s     # PX4 timestamp_sample [s] of the last local_position
float64 t_px4_timestamp_s   # PX4 timestamp [s] of the last local_position
float64 t_ros_recv_s        # ROS clock at last local_position callback
float64 t_cmd_pub_s         # VehicleCommand publish (steady clock)
float64 t_cmd_pub_ros_s     # VehicleCommand publish (ROS clock)
float64 t_ack_s             # last SET_NAV_STATE ACK (steady clock)
float64 l0_s                # timestamp - timestamp_sample (PX4 clock, SPEC L0)
float64 clock_err_s         # ROS recv - PX4 timestamp (AC-19)
float64 l2_s                # last monitor processing_s (SPEC L2)
float64 l3_s                # arbiter ROS recv - verdict stamp (SPEC L3)
float64 t_daa_s             # T_daa(k)
float64 t_gf_s              # T_gf(k)
string monitor_id           # first switch-class monitor reporting a violation, if any
