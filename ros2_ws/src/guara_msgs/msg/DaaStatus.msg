# SPDX-License-Identifier: Apache-2.0
# Detect-and-avoid status computed by the NOSA-isolated guara_daidalus node (ADR 0003). This message
# is the only interface between DAIDALUS and the Apache-2.0 part of Guará.

# Reception time, on the DAA node clock, of the ownship sample used by this evaluation.
builtin_interfaces/Time stamp

# T_daa (SPEC §3.1): minimum over intruders of the time until the ownship enters the corrective-level
# well-clear volume, as returned by Daidalus::timeToCorrectiveVolume [G A.14]. +inf when no intruder is
# predicted to enter the volume within the configured lookahead time.
float64 time_to_corrective_volume_s

# Maximum DAIDALUS alert level over all intruders (0 = none).
int32 alert_level

# Number of intruders whose state was used in this evaluation.
uint16 num_intruders

# Identifier (ICAO address, decimal) of the intruder that attains time_to_corrective_volume_s; 0 if none.
uint32 critical_intruder_icao

# False if the ownship state was missing or invalid; the arbiter then treats DAA as an invalid input.
bool ownship_valid
