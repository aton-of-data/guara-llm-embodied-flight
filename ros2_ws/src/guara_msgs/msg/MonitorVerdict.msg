# SPDX-License-Identifier: Apache-2.0
# Verdict of one runtime monitor at one evaluation step (SPEC §3.1 signal M(k); ADR 0002 rules 2-3).

uint8 CLASS_LOG=0       # recorded only; never enters M(k)
uint8 CLASS_SWITCH=1    # a violation sets M(k) = 1

uint8 ACTION_HOLD=0     # recovery requested on violation (SPEC §3.5 select(k)); ranked HOLD < RTL < LAND
uint8 ACTION_RTL=1
uint8 ACTION_LAND=2

# Reception time, on the monitor clock, of the most recent input sample used by this evaluation.
# Used to measure stage L2 of the latency budget (SPEC §4.1).
builtin_interfaces/Time stamp

# Requirement identifier (e.g. REQ-ALT-01), as declared in the requirement catalogue.
string monitor_id

uint8 monitor_class
uint8 action

# True if the monitored property is violated at this step.
bool violated

# True if every input of the monitor has been received at least once; a monitor that has not yet
# observed all of its inputs reports violated = false and inputs_complete = false.
bool inputs_complete

# Monotonic evaluation counter of the monitor process.
uint64 step

# Monitor processing duration (SPEC §4.1 L2): time from input reception to verdict publish, seconds.
float64 processing_s
