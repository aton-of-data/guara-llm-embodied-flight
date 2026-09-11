# SPDX-License-Identifier: Apache-2.0
# Velocity setpoint proposed by the untrusted Complex Function (CF). It reaches PX4 only through the
# owned mode GuaraCfGateway, which forwards it exclusively while the arbiter state is CF
# (SPEC §2 Input Manager; ADR 0001 rule 4; ADR 0005 item 7).

# Generation time of the setpoint on the CF clock. Setpoints stamped before the most recent
# RF -> CF return instant are discarded by the gateway.
builtin_interfaces/Time stamp

# Commanded velocity in the local NED frame [m/s].
float32[3] velocity_ned_m_s

# Commanded yaw in the NED frame [rad]; NaN leaves yaw uncontrolled.
float32 yaw_ned_rad
