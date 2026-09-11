# ros2_ws/src

Guará ROS 2 packages:

| Package | Role |
|---|---|
| `guara_msgs` | Interface messages (`CfSetpoint`, `MonitorVerdict`, `DaaStatus`, `RtaEvent`, `RtaState`) |
| `guara_rta` | Decision core, input manager, CF gateway, ModeExecutor arbiter node |
| `guara_geofence` | Braking-aware time-to-violation predictor (ADR 0004) |
| `guara_monitors` | Ogma template, generated Copilot C99, verdict-publishing node |

PX4 dependencies build from `third_party/` via `ros2_ws/colcon_defaults.yaml`.
NOSA-licensed DAIDALUS code belongs in `nosa/` (ADR 0003), not here.
