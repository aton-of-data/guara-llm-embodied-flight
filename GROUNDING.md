# GROUNDING.md — P0

Facts verified in the source code cloned under `third_party/` (commits in
`third_party/VERSIONS.md`). No answer comes from memory.

Evidence abbreviations (`repo@commit:file:line`):

| Alias | Repository@commit |
|---|---|
| `PX4@d6f12ad` | PX4-Autopilot v1.17.0 |
| `msgs@86d8239` | px4_msgs release/1.17 |
| `lib@4a3370f` | px4-ros2-interface-lib release/1.17 |
| `ogma@69485b3` | ogma v1.15.0 |
| `daa@0647596` | daidalus DAIDALUSv2.0.3a |
| `cop@365fb21` | copilot v4.8.1 |
| `fret@58db455` | fret v3.1.0 |

Short paths: `lib/…` = `px4_ros2_cpp/…`; `cmd/…` = `src/modules/commander/…`;
`dds/…` = `src/modules/uxrce_dds_client/…`.

Confidence: **HIGH** = read directly in code; **MEDIUM** = inferred by
combining read excerpts, not executed; **UNKNOWN** = no evidence.

---

## R0 — Version preconditions

| # | answer | evidence | confidence |
|---|---|---|---|
| R0.1 | Messages in `px4_msgs@86d8239` are identical to PX4 v1.17.0 (0 differing files). | command in `third_party/VERSIONS.md`; `PX4@d6f12ad:msg/versioned/` | HIGH |
| R0.2 | PX4 v1.17.0 docs declare ROS 2 **Humble** (Ubuntu 22.04) as the supported and recommended platform. | `PX4@d6f12ad:docs/en/ros2/user_guide.md:53` | HIGH |
| R0.3 | Interface-lib CI builds against Humble; Debian packages are built for Humble and Jazzy. | `lib@4a3370f:.github/workflows/build_and_test.yml:22,33`; `lib@4a3370f:.github/workflows/build-publish-debian-packages.yml:23,25` | HIGH |
| R0.4 | The Ogma ROS template Dockerfile uses `osrf/space-ros:jazzy-2026.04.0` (Jazzy), diverging from R0.2. | `ogma@69485b3:ogma-core/templates/ros/Dockerfile:1,21` | HIGH |

---

## Q1 — ModeExecutor activating internal modes (Hold, RTL, Land)

| # | answer | evidence | confidence |
|---|---|---|---|
| 1.1 | Generic API: `void scheduleMode(ModeBase::ModeID mode_id, const CompletedCallback& on_completed, bool forced=false)`. Shortcuts: `takeoff(cb, alt, heading)`, `land(cb)`, `rtl(cb)`. `CompletedCallback = std::function<void(Result)>`. | `lib@4a3370f:lib/include/px4_ros2/components/mode_executor.hpp:34,102-108` | HIGH |
| 1.2 | Exposed internal mode IDs: `kModeIDLand` (`NAVIGATION_STATE_AUTO_LAND`=18), `kModeIDRtl` (`AUTO_RTL`=5), `kModeIDLoiter` (`AUTO_LOITER`=4), `kModeIDDescend`, `kModeIDPosctl`, `kModeIDTakeoff`, `kModeIDPrecisionLand`. **There is no `kModeIDHold`**; "Hold" corresponds to `AUTO_LOITER` (PX4 itself uses `AUTO_LOITER` when it "switches to Hold"). | `lib@4a3370f:lib/include/px4_ros2/components/mode.hpp:73-89`; `msgs@86d8239:msg/VehicleStatus.msg:40,41,54`; `PX4@d6f12ad:cmd/ModeManagement.cpp:358-361` | HIGH |
| 1.3 | Implementation: `scheduleMode` sends `VEHICLE_CMD_SET_NAV_STATE` with `param1=mode_id` via `sendCommandSync` (blocks until ACK); cancels any previous schedule; if disarmed and `forced=false`, returns `Result::Rejected` without sending. The callback fires when the mode publishes `ModeCompleted` or when the executor is deactivated. | `lib@4a3370f:lib/src/components/mode_executor.cpp:225-261` | HIGH |
| 1.4 | Executor commands go out on topic `fmu/in/vehicle_command_mode_executor`, distinct from `fmu/in/vehicle_command`. | `lib@4a3370f:lib/src/components/mode_executor.cpp:48`; `PX4@d6f12ad:dds/dds_topics.yaml:176-177` | HIGH |
| 1.5 | Call sequence: (a) subclass `ModeExecutorBase` with its own `ModeBase` ("owned mode"); (b) `doRegister()` of executor and mode at startup (blocking) — `NodeWithModeExecutor` does this; (c) PX4 calls `onActivate()` when the executor becomes "in charge"; (d) inside the state machine, `rtl(cb)` / `land(cb)` / `scheduleMode(kModeIDLoiter, cb)`; (e) `onDeactivate(reason)` when it loses control. Real example: takeoff → `scheduleMode(ownedMode().id())` → `rtl` → `waitUntilDisarmed`. | `lib@4a3370f:lib/include/px4_ros2/components/mode_executor.hpp:59-78`; `lib@4a3370f:lib/include/px4_ros2/components/node_with_mode.hpp:117-120`; `lib@4a3370f:examples/cpp/modes/mode_with_executor/include/mode.hpp:75-120` | HIGH |
| 1.6 | **"In charge" condition**: `VehicleStatus.executor_in_charge == id()` and (armed or `ActivateAlways` or `ActivateImmediately` the first time). PX4 only puts the executor in charge when the user enters the **owned mode**; if the user (RC/GCS) switches to a mode not owned by the executor, control returns to the autopilot (`AUTOPILOT_EXECUTOR_ID`) and the executor receives `onDeactivate(Other)`; on failsafe it receives `onDeactivate(FailsafeActivated)`. | `lib@4a3370f:lib/src/components/mode_executor.cpp:369-385`; `PX4@d6f12ad:cmd/ModeManagement.cpp:415-434`; `msgs@86d8239:msg/VehicleStatus.msg:69` | HIGH |
| 1.7 | Consequence for the arbiter: modes scheduled by the executor (Hold/RTL/Land) **keep** the executor in charge; the arbiter only arbitrates while the owned mode (complex function) or a mode it scheduled is active. | `lib@4a3370f:lib/src/components/mode_executor.cpp:256-260,387-396` | MEDIUM |
| 1.8 | `deferFailsafesSync(enabled, timeout_s)` defers most failsafes while the executor is in charge (0 = system default, −1 = no timeout); FMU default = 30 s. It does not defer attitude limits nor "mode cannot run". `onFailsafeDeferred()` is called when the FMU wanted to enter failsafe. | `lib@4a3370f:lib/include/px4_ros2/components/mode_executor.hpp:80-84,127-139`; `PX4@d6f12ad:cmd/failsafe/framework.h:50` | HIGH |

---

## Q2 — External executor / mode that stops responding

| # | answer | evidence | confidence |
|---|---|---|---|
| 2.1 | Liveness mechanism: commander publishes `ArmingCheckRequest` every `UPDATE_INTERVAL = 300 ms`; reply expected within `REQUEST_TIMEOUT = 50 ms`. Constants are **compiled** (`static constexpr`), not parameters. | `PX4@d6f12ad:cmd/HealthAndArmingChecks/checks/externalChecks.hpp:69-71`; `PX4@d6f12ad:cmd/HealthAndArmingChecks/checks/externalChecks.cpp:286-305` | HIGH |
| 2.2 | Registration is marked **unresponsive** when `++num_no_response > NUM_NO_REPLY_UNTIL_UNRESPONSIVE (3)`; right after registering the limit is `NUM_NO_REPLY_UNTIL_UNRESPONSIVE_INIT (10)`. A reply resets the counter. | `PX4@d6f12ad:cmd/HealthAndArmingChecks/checks/externalChecks.hpp:72-75`; `…/externalChecks.cpp:237-238,256-278` | HIGH |
| 2.3 | Derived detection time: ~4 cycles × 300 ms ≈ 1.2 s (+ up to 50 ms) after the last reply. **HYPOTHESIS to measure** — not measured. | derived from 2.1 + 2.2 | MEDIUM |
| 2.4 | Effect with vehicle armed in the external mode: the mode's `mode_req_other` bit is set → `modeCanRun()` false → `checkModeFallback` returns `Action::RTL`, marked `cannotBeDeferred()` and `allowUserTakeover(Always)` (hence **no** `COM_FAIL_ACT_T` delay). If RTL cannot run either, the framework falls through to the next fallbacks (Land/Descend…). Event: "Mode is unresponsive". | `…/externalChecks.cpp:130-135,207-214`; `PX4@d6f12ad:cmd/HealthAndArmingChecks/checks/modeCheck.cpp:184-186`; `PX4@d6f12ad:cmd/failsafe/framework.cpp:699-716`; `PX4@d6f12ad:cmd/failsafe/failsafe.cpp:638-641,698-702`; `PX4@d6f12ad:cmd/failsafe/framework.cpp:350-360` | MEDIUM (chain read; not exercised in SITL) |
| 2.5 | If the mode replaces an internal mode (`replaces_nav_state`) and is unresponsive, PX4 uses the internal mode ("External mode is unresponsive, falling back to internal"). | `PX4@d6f12ad:cmd/ModeManagement.cpp:437-461` | HIGH |
| 2.6 | The timeout tracks the **mode's arming-check registration**, not the executor itself. If the arbiter dies while an **internal** mode it scheduled (e.g. Hold) is active, no code read forces exit from that internal mode. | `…/externalChecks.cpp:130-135` (only acts with `nav_mode_id != -1`) | MEDIUM |
| 2.7 | **With vehicle armed** (default `COM_MODE_ARM_CHK=0`): new registrations are rejected ("Not accepting registration requests while armed") and removals/unregistrations are only processed while disarmed. ⇒ an arbiter that restarts in flight **cannot re-register**. | `PX4@d6f12ad:cmd/ModeManagement.cpp:372-388,389-408`; `PX4@d6f12ad:cmd/commander_params.c:1039-1048` | HIGH |
| 2.8 | Explicit unregister of the active mode (disarmed) → switch to Hold (`AUTO_LOITER`). On `onDisarm`, unresponsive mode → Hold. | `PX4@d6f12ad:cmd/ModeManagement.cpp:358-361,485-489` | HIGH |
| 2.9 | Related parameters: `COM_FAIL_ACT_T` (default 5 s, delay in Hold before failsafe for actions with takeover `Auto`); `COM_OF_LOSS_T` (default 1 s, only for nav_state `OFFBOARD`, not external modes); `COM_MODE_ARM_CHK` (default 0). | `PX4@d6f12ad:cmd/commander_params.c:298-311,340`; `PX4@d6f12ad:cmd/HealthAndArmingChecks/checks/offboardCheck.cpp:38-66`; `PX4@d6f12ad:cmd/failsafe/failsafe.cpp:665` | HIGH |
| 2.10 | There is no setpoint watchdog for external modes equivalent to `COM_OF_LOSS_T`: a process whose setpoint thread hangs while arming-check callbacks stay alive (multi-threaded) would not be detected by 2.1–2.4. | absence verified in `offboardCheck.cpp` (only `OFFBOARD`) and `externalChecks.cpp` | MEDIUM |

---

## Q3 — Default `/fmu/out/*` topics and traffic

| # | answer | evidence | confidence |
|---|---|---|---|
| 3.1 | Default publications (27): `register_ext_component_reply`, `arming_check_request` (5 Hz), `mode_completed` (50), `battery_status` (1), `collision_constraints` (50), `estimator_status_flags` (5), `failsafe_flags` (5), `manual_control_setpoint` (25), `message_format_response`, `position_setpoint_triplet` (5), `sensor_combined`, `timesync_status` (10), `transponder_report`, `vehicle_land_detected` (5), `vehicle_attitude`, `vehicle_control_mode` (50), `vehicle_command_ack`, `vehicle_global_position` (50), `vehicle_gps_position` (50), `vehicle_local_position` (50), `vehicle_odometry`, `vehicle_status` (5), `airspeed_validated` (50), `vtol_vehicle_status`, `home_position` (5), `wind` (1), `gimbal_device_attitude_status` (20). No `rate_limit` = uORB publish rate. | `PX4@d6f12ad:dds/dds_topics.yaml:6-109` | HIGH |
| 3.2 | **`/fmu/out/transponder_report` is exposed by default** (`px4_msgs::msg::TransponderReport`: lat/lon in degrees, altitude AMSL m, heading rad, hor/ver velocity m/s, `tslc`, validity `flags`). | `PX4@d6f12ad:dds/dds_topics.yaml:53-54`; `msgs@86d8239:msg/TransponderReport.msg:1-25` | HIGH |
| 3.3 | Sources of `transponder_report` in PX4: MAVLink `ADSB_VEHICLE` (mavlink_receiver), Sagetech MXS driver and `navigator fake_traffic` (publishes 24 fake reports around the current position). There is **no** `/fmu/in/transponder_report`; injecting intruders via ROS 2 requires MAVLink `ADSB_VEHICLE`, `fake_traffic`, or adding the subscription to `dds_topics.yaml` (custom build). | `PX4@d6f12ad:src/modules/mavlink/mavlink_receiver.cpp:224`; `PX4@d6f12ad:src/modules/navigator/navigator_main.cpp:1258-1260,1331-1333,1688`; `PX4@d6f12ad:dds/dds_topics.yaml:112-225` | HIGH |
| 3.4 | No geofence topic (`geofence_result`, `geofence_status`) is exposed by default, although the messages exist. The geofence predictor must keep the polygon on the companion or customize `dds_topics.yaml`. | `grep -c geofence dds_topics.yaml` = 0; `PX4@d6f12ad:msg/GeofenceResult.msg`, `msg/GeofenceStatus.msg` | HIGH |
| 3.5 | Topic names get suffix `_v<N>` when `MESSAGE_VERSION != 0`: `vehicle_status` → `/fmu/out/vehicle_status_v1`, `vehicle_local_position` → `/fmu/out/vehicle_local_position_v1`; `vehicle_global_position`, `vehicle_attitude`, `vehicle_odometry` have no suffix (version 0). Interface-lib applies the same suffix (except with rmw_zenoh). | `PX4@d6f12ad:dds/utilities.hpp:26-41`; `msgs@86d8239:msg/VehicleStatus.msg:3`; `msgs@86d8239:msg/VehicleLocalPosition.msg:4`; `msgs@86d8239:msg/VehicleGlobalPosition.msg:8`; `lib@4a3370f:lib/include/px4_ros2/utils/message_version.hpp:54-62` | HIGH |
| 3.6 | PX4 publisher QoS: `BEST_EFFORT`, `TRANSIENT_LOCAL`, `KEEP_LAST`. ROS 2 subscribers **must** use compatible QoS (docs: `rmw_qos_profile_sensor_data`). | `PX4@d6f12ad:dds/utilities.hpp:78-83`; `PX4@d6f12ad:docs/en/ros2/user_guide.md:403-413` | HIGH |
| 3.7 | `vehicle_status` is limited to 5 Hz at the bridge: mode-change confirmation observed via `vehicle_status` has ≥ 200 ms granularity; `vehicle_command_ack` has no rate limit. Relevant for the latency budget. | `PX4@d6f12ad:dds/dds_topics.yaml:70-71,88-90` | HIGH |

---

## Q4 — Ogma variable DB for the `ros` backend

| # | answer | evidence | confidence |
|---|---|---|---|
| 4.1 | JSON format with three keys: `inputs` (name, C type, `active`, `connections[{scope:"ros/message", topic, field}]`), `topics` (`scope`, `topic`, ROS 2 message `type`) and `types` (`fromScope/fromType/fromField` → `toScope:"C"/toType` mapping). `field` extracts a field from a composite message. | `ogma@69485b3:ogma-cli/README.md:444-485`; `ogma@69485b3:ogma-core/CHANGELOG.md:29` (#499) | HIGH |
| 4.2 | **Real minimal example** (turtlesim, field `x` of `turtlesim::msg::Pose`): see block below. | `ogma@69485b3:ogma-cli/examples/ros2-turtlesim/vars-db-turtlesim.json:1-27` | HIGH |
| 4.3 | Real invocation: `ogma ros --project ogma-cli/examples/ros2-turtlesim/project.ogma`, or flags `--input-file`, `--input-format`, `--variable-file`, `--variable-db`, `--handlers-file`, `--template-dir`, `--template-vars`, `--target-dir`, `--testing-app`. **The README cites `--handlers`, but the code defines `--handlers-file`**. | `ogma@69485b3:ogma-cli/examples/ros2-turtlesim/README.md:59`; `ogma@69485b3:ogma-cli/src/CLI/CommandROSApp.hs:179-270`; `ogma@69485b3:ogma-cli/README.md:414,422` | HIGH |
| 4.4 | Generated template: `msg->{{varDeclMsgField}}` if `field` is present, else `msg->data`. | `ogma@69485b3:ogma-core/templates/ros/copilot/src/copilot_monitor.cpp:88-93` | HIGH |
| 4.5 | **QoS incompatibility**: the template subscribes with `create_subscription<T>(topic, 10, …)` (default QoS = RELIABLE). With PX4 BEST_EFFORT publishers (3.6), the subscription receives no data. ⇒ M2 needs its own `--template-dir` with best-effort QoS. | `ogma@69485b3:ogma-core/templates/ros/copilot/src/copilot_monitor.cpp:38-40`; `PX4@d6f12ad:dds/utilities.hpp:78-83` | HIGH (code); runtime effect MEDIUM |
| 4.6 | Documented limitation: the C code of the Copilot monitors is not generated by the `ros` command; it must be placed in `monitor.h` / `monitor.c`. | `ogma@69485b3:ogma-cli/README.md:556-560` | HIGH |
| 4.7 | Ogma accepts FRET component specifications (formats `fcs_smv`, `fcs_lustre`). Field-level match with FRET's export: see A.15. | `ogma@69485b3:ogma-core/data/formats/` | MEDIUM (formats and fields matched; FRET→Ogma flow not executed) |

Real example (`vars-db-turtlesim.json`, verbatim):

```json
{ "inputs":
     [ { "name": "input_signal"
       , "type": "float"
       , "active": true
       , "connections":
           [ { "scope": "ros/message"
             , "topic": "/turtle1/pose"
             , "field": "x"
             }
           ]
       }
     ]
, "topics":
     [ { "scope": "ros/message"
       , "topic": "/turtle1/pose"
       , "type":  "turtlesim::msg::Pose"
       }
     ]
, "types": [
       { "fromScope": "ros/message"
       , "fromType":  "turtlesim::msg::Pose"
       , "fromField": "x"
       , "toScope":   "C"
       , "toType":    "float"
       }
     ]
}
```

---

## Q5 — DAIDALUS v2 C++ API

| # | answer | evidence | confidence |
|---|---|---|---|
| 5.1 | Ownship: `void setOwnshipState(const std::string& id, const Position& pos, const Velocity& vel, double time)` (and overload without `time`). Must be called before intruders. | `daa@0647596:C++/include/Daidalus.h:201,209` | HIGH |
| 5.2 | Intruders: `int addTrafficState(const std::string& id, const Position& pos, const Velocity& vel[, double time])` → index (1..`lastTrafficIndex()`; 0 = ownship). | `daa@0647596:C++/include/Daidalus.h:222,232,275-279` | HIGH |
| 5.3 | Constructors: `Position::makeLatLonAlt(lat,"deg", lon,"deg", alt,"ft")` and `Velocity::makeTrkGsVs(trk,"deg", gs,"knot", vs,"fpm")` (units as strings). Wind: `setWindVelocityFrom(Velocity)`. | `daa@0647596:C++/include/Position.h:75,88`; `daa@0647596:C++/include/Velocity.h:244,260`; `daa@0647596:C++/include/Daidalus.h:317`; `daa@0647596:C++/examples/DaidalusExample.cpp:350-368` | HIGH |
| 5.4 | Time to violation: `double timeToCorrectiveVolume(int ac_idx)` (relative s; `+inf` = no conflict within lookahead; `NaN` = invalid index). Per level: `ConflictData violationOfAlertThresholds(int ac_idx, int alert_level)` → `conflict()`, `getTimeIn()`, `getTimeOut()`. Level: `alertLevel(ac_idx)`, `alertLevelAllTraffic()`. | `daa@0647596:C++/include/Daidalus.h:2502-2515,2526-2551`; `daa@0647596:C++/include/ConflictData.h:27`; `daa@0647596:C++/include/LossData.h:66`; `daa@0647596:C++/examples/DaidalusExample.cpp:55-66` | HIGH |
| 5.5 | Which function corresponds to "loss of well-clear" depends on the configured alerter/region (`corrective_region = MID` in DO-365B). Mapping "time to loss of DWC" to `timeToCorrectiveVolume` vs `violationOfAlertThresholds(idx, level)` is a SPEC decision. Code semantics now resolved in A.14. | `daa@0647596:Configurations/DO_365B_no_SUM.conf:72-80` | MEDIUM → see A.14 (HIGH) |
| 5.6 | Bands: `horizontalDirectionBandsLength()`, `horizontalDirectionIntervalAt(i[, unit])`, `horizontalDirectionRegionAt(i)`; also resolutions and `horizontalDirectionRecoveryInformation()`. Analogous families exist for horizontal speed, vertical speed and altitude. | `daa@0647596:C++/include/Daidalus.h:1898-1923`; `daa@0647596:C++/examples/DaidalusExample.cpp:107-131` | HIGH |
| 5.7 | DO-365B configuration: programmatic `set_DO_365B(bool type=true, bool sum=true)` (alerters Phase I, Phase II, Non-Cooperative) or file `loadFromFile("Configurations/DO_365B_SUM.conf")` / `DO_365B_no_SUM.conf`. | `daa@0647596:C++/include/Daidalus.h:142-153,1810`; `daa@0647596:Configurations/DO_365B_SUM.conf`; `daa@0647596:C++/examples/DaidalusExample.cpp:305-309,343` | HIGH |
| 5.8 | Values in the DO-365B file (repository configuration, not a regulatory claim): `lookahead_time = 180 s`, DWC Phase I `DTHR = 0.66 nmi`, `ZTHR = 700/450 ft`. Sized for larger aircraft; use with small drones requires a custom configuration — **HYPOTHESIS to validate**. | `daa@0647596:Configurations/DO_365B_no_SUM.conf:4`; `daa@0647596:Configurations/DO_365B_SUM.conf:85-99` | HIGH (values); MEDIUM (suitability) |
| 5.9 | C++ build: `Makefile` (no CMake in the repository) ⇒ the DAIDALUS ROS 2 package needs its own CMake. | `daa@0647596:C++/Makefile`; `find C++ -name CMakeLists.txt` empty | HIGH |
| 5.10 | License: NASA Open Source Agreement (`DAIDALUS2-NOSA.pdf`). Specific terms of the PDF were not read in this session. | `daa@0647596:README.md:66-69`; `daa@0647596:LICENSES/DAIDALUS2-NOSA.pdf` | HIGH (type); UNKNOWN (terms) → see A.12 |

---

## Q6 — CopilotVerifier

| # | answer | evidence | confidence |
|---|---|---|---|
| 6.1 | Yes: `copilot-verifier` version 4.8.1 is in the Copilot v4.8.1 monorepo and depends on `copilot-c99 >= 4.8.1 && < 4.9`. | `cop@365fb21:copilot-verifier/copilot-verifier.cabal:2-3,48` | HIGH |
| 6.2 | Invocation (Haskell): `Copilot.Verifier.verify :: CSettings -> [String] -> String -> Spec -> IO ()` (`verify csettings props prefix spec`) or `verifyWithOptions :: VerifierOptions -> …` (e.g. `sideCondVerifierOptions`). Generates C99, compiles to LLVM bitcode with `clang`, interprets with Crucible and sends VCs to SMT. | `cop@365fb21:copilot-verifier/src/Copilot/Verifier.hs:168-172,264-267`; `cop@365fb21:copilot-verifier/README.md:72-80,294` | HIGH |
| 6.3 | Prerequisites: GHC 9.4/9.6/9.8 (`base < 4.20`), Cabal ≥ 3.10, `clang` + `llvm-link` **LLVM ≤ 16**, `z3` (or cvc4/cvc5/yices). Deps: crucible 0.7, crucible-llvm 0.7, crux-llvm 0.9, what4 ≥1.6.1 <1.8. | `cop@365fb21:copilot-verifier/README.md:28-45`; `cop@365fb21:copilot-verifier/copilot-verifier.cabal:44-65` | HIGH |
| 6.4 | Scope: verifies the C generated by `copilot-c99` against the `Spec` semantics; does not cover the C++/ROS glue generated by Ogma. | `cop@365fb21:copilot-verifier/copilot-verifier.cabal:13-18` | HIGH |
| 6.5 | No Haskell tooling (ghc/cabal/stack), LLVM or z3 is installed on this machine; verifier not executed. | `which ghc cabal stack` → not found | HIGH |

---

## Addendum A — additional facts verified during P1 (2026-09-11)

Same rule as P0: cloned code only. These items support SPEC and ADR decisions.

| # | answer | evidence | confidence |
|---|---|---|---|
| A.1 | `sendCommandSync` (used by `scheduleMode`/`rtl`/`land`) **creates a subscription on every call** (dynamic allocation), busy-waits up to 3000 ms for discovery of the `vehicle_command_ack` publisher, then publishes the command up to 3 times waiting 300 ms for ACK. Worst-case blocking of the calling thread ≈ 3.9 s. The command is published **before** waiting for the ACK. | `lib@4a3370f:lib/src/components/mode_executor.cpp:141-222` | HIGH |
| A.2 | `source_component = COMPONENT_MODE_EXECUTOR_START + id()`; commander classifies commands with `source_component >= COMPONENT_MODE_EXECUTOR_START` as `ModeChangeSource::ModeExecutor`. | `lib@4a3370f:lib/src/components/mode_executor.cpp:141`; `PX4@d6f12ad:cmd/Commander.cpp:1561,1567-1574` | HIGH |
| A.3 | When switching to a nav_state with no associated executor, the executor in charge **only changes** if the source is `User` (RC/MAVLink); with source `ModeExecutor` it stays. | `PX4@d6f12ad:cmd/ModeManagement.cpp:415-434`; `PX4@d6f12ad:cmd/UserModeIntention.hpp:39-42` | HIGH |
| A.4 | `ModeBase` exposes `checkArmingAndRunConditions(reporter)` (called periodically, including while the mode is active), `onActivate/onDeactivate`, `setSetpointUpdateRate(hz)` and `updateSetpoint(dt_s)`. | `lib@4a3370f:lib/include/px4_ros2/components/mode.hpp:132-161` | HIGH |
| A.5 | The reply to `ArmingCheckRequest` is produced in the node's own subscription callback (best-effort QoS, depth 1), calling the mode's check callback; `reporter.armingCheckFailureExt(...)` sets `can_arm_and_run=false`. | `lib@4a3370f:lib/src/components/health_and_arming_checks.cpp:29-56`; `lib@4a3370f:lib/include/px4_ros2/components/health_and_arming_checks.hpp:30-37` | HIGH |
| A.6 | In PX4, `can_arm_and_run=false` from an external mode sets `mode_req_other` for that mode → same fallback chain as 2.4 (mode cannot run → RTL). Detection latency ≤ 1 request period (300 ms) + processing. | `PX4@d6f12ad:cmd/HealthAndArmingChecks/checks/externalChecks.cpp:157-159`; items 2.1 and 2.4 | MEDIUM (timing not measured) |
| A.7 | Trajectory setpoints: `px4_ros2::TrajectorySetpointType::update(velocity_ned, accel?, yaw?, yaw_rate?)`, `update(TrajectorySetpoint)`, `updatePosition(position_ned)`; `MulticopterGotoSetpointType` exists. | `lib@4a3370f:lib/include/px4_ros2/control/setpoint_types/experimental/trajectory.hpp:26-66`; `lib@4a3370f:lib/include/px4_ros2/control/setpoint_types/multicopter/goto.hpp:24,44` | HIGH |
| A.8 | `VehicleLocalPosition` (topic `_v1`): `timestamp`, `timestamp_sample` (µs), `x,y,z` NED (m), `vx,vy,vz` (m/s), `ax,ay,az`, flags `xy_valid`, `v_xy_valid`, `z_valid`, `v_z_valid`, reset counters, `ref_lat/ref_lon/ref_alt`, `eph/epv/evh/evv`, `dead_reckoning`. | `msgs@86d8239:msg/VehicleLocalPosition.msg:6-77` | HIGH |
| A.9 | In DDS serialization, fields `timestamp` and `timestamp_sample` get `+ time_offset` of the uXRCE session (sync with the agent); other time fields do not. | `PX4@d6f12ad:Tools/msg/templates/ucdr/msg.h.em:127-144`; `PX4@d6f12ad:dds/dds_topics.h.em:126,176` | HIGH (code); resulting reference clock in ROS 2: MEDIUM |
| A.10 | ULog logs by default `vehicle_status`, `vehicle_command`, `vehicle_local_position` and `transponder_report`. | `PX4@d6f12ad:src/modules/logger/logged_topics.cpp:132,138,145,150` | HIGH |
| A.11 | PX4 internal geofence: `GF_ACTION` (default 2 = Hold; 3 RTL; 4 Terminate; 5 Land), `GF_SOURCE`, `GF_MAX_HOR_DIST`/`GF_MAX_VER_DIST` (0 = disabled), `GF_PREDICT` (default 0, marked **[EXPERIMENTAL]** "may cause flyaways"). | `PX4@d6f12ad:src/modules/navigator/geofence_params.c:46-119` | HIGH |
| A.12 | DAIDALUS license = **NASA Open Source Agreement v1.3**. Obligations read: distribution under the agreement itself with a copy of the text (3.A.1); non-source distribution requires making source available (3.A.2); prominent NASA copyright notice (3.B); modifications described in a changelog file identifying the author (3.C); prohibition on implying NASA endorsement (3.E); "Larger Work" combining with software under another license is allowed, keeping the NOSA part under NOSA (3.I); including the software in a Larger Work is not, by itself, a Modification (1.F); US export control notice (3.J). Legal interpretation of compatibility with Apache-2.0/BSD is **not** in the text. | `daa@0647596:LICENSES/DAIDALUS2-NOSA.pdf` (pp. 1-5, clauses 1.E, 1.F, 3.A-3.J) | HIGH (text); UNKNOWN (legal interpretation) |
| A.13 | `TrajectorySetpoint` has no sender identity field (only `timestamp`, `position`, `velocity`, `acceleration`, `jerk`, `yaw`, `yawspeed`); `/fmu/in/trajectory_setpoint` is subscribed without origin authentication. Any ROS 2 node in the same domain can publish to it. | `msgs@86d8239:msg/TrajectorySetpoint.msg`; `PX4@d6f12ad:dds/dds_topics.yaml:158-159` | HIGH (format); MEDIUM (effect with external mode active not exercised) |

---

## Addendum B — facts verified while resolving P1 blockers (2026-09-11)

| # | answer | evidence | confidence |
|---|---|---|---|
| A.14 | `timeToCorrectiveVolume(i)` returns `violationOfCorrectiveThresholds(i).getTimeIn()` if `conflict()`, else `+inf`; `violationOfCorrectiveThresholds(i)` = `violationOfAlertThresholds(i, 0)`; level `0` is replaced by `correctiveAlertLevel(alerter_idx)` = **first** alert level (1-based) whose region equals `corrective_region`; detection runs that level's detector over `[0, lookahead_time]`. In `DO_365B_no_SUM.conf`, `corrective_region = MID` and alerter `DWC_Phase_I` level 2 is the first `MID` level, detector `det_2` = `WCV_TAUMOD` with `DTHR 0.66 nmi`, `ZTHR 450 ft`, `TTHR 35 s`. ⇒ `T_daa` via `timeToCorrectiveVolume` = time until entering the **corrective-level WCV volume of the intruder's alerter**, not the level-1 (700 ft) volume. | `daa@0647596:C++/src/Daidalus.cpp:3725-3751,3770-3772,3780-3791`; `daa@0647596:C++/src/DaidalusParameters.cpp:1856-1864`; `daa@0647596:C++/src/Alerter.cpp:434-441`; `daa@0647596:Configurations/DO_365B_no_SUM.conf:4,75-76,90-102` | HIGH |
| A.15 | FRET's CoPilot export template emits JSON `{"<componentName>": {"Internal_variables":[{name,type,assignmentLustre,assignmentCopilot}], "Other_variables":[{name,type}], "Requirements":[{CoCoSpecCode,fretish,name,PCTL,ptLTL}]}}`. Ogma `fcs_smv` reads `..Internal_variables[*]` (`.name`, `.assignmentCopilot`, `.type`), `..Other_variables[*]` (`.name`, `.type`), `..Requirements[*]` (`.name`, `.fretish`, `.ptLTL`) — keys match field by field. `ogma ros` defaults are `--input-format fcs` and `--prop-format smv` (i.e. `fcs_smv`). | `fret@58db455:fret-electron/support/CoPilotTemplates/Component.ejs:2`, `InternalVariables.ejs`, `OtherVariables.ejs`, `RequirementDefinitions.ejs:1-12`; `ogma@69485b3:ogma-core/data/formats/fcs_smv`; `ogma@69485b3:ogma-cli/src/CLI/CommandROSApp.hs:233-248` | HIGH (field match); MEDIUM (end-to-end flow not executed) |
| A.16 | `COM_MODE_ARM_CHK` description: "Allow external mode registration while armed. By default disabled for safety reasons." With it `0`, armed registration requests are answered with `success = false`. | `PX4@d6f12ad:cmd/commander_params.c:1039-1048`; `PX4@d6f12ad:cmd/ModeManagement.cpp:370-388` | HIGH |

---

## Addendum C — facts for M1 (headless SITL, 2026-09-11)

| # | answer | evidence | confidence |
|---|---|---|---|
| A.17 | SIH runs "as SITL" without a flight controller and without Gazebo: `make px4_sitl sihsim_quadx`. The make target runs the `px4` binary with env `PX4_SIM_MODEL=sihsim_<model>` `PX4_SIMULATOR=sihsim` in `SITL_WORKING_DIR`. Airframe `10040_sihsim_quadx` enables `SENS_EN_GPSSIM/BAROSIM/MAGSIM`. `PX4_SIM_SPEED_FACTOR` speeds up; `PX4_HOME_LAT/LON/ALT` set takeoff location. | `PX4@d6f12ad:src/modules/simulation/simulator_sih/CMakeLists.txt:51-107`; `PX4@d6f12ad:ROMFS/px4fmu_common/init.d-posix/airframes/10040_sihsim_quadx:10-18`; `PX4@d6f12ad:docs/en/sim_sih/index.md:184-261` | HIGH |
| A.18 | `px4 [-d] [-s <startup_file>] [-w <working_directory>] [<rootfs_directory>]`: `-d` = daemon, no pxh shell; default startup `etc/init.d-posix/rcS`; working dir is created/changed into and symlinks to the data path are created there. Clients: `px4-<module> [--instance N] <cmd>` (e.g. `px4-commander status`). Commander CLI has `check`, `arm [-f]`, `disarm [-f]`, `takeoff`, `land`, `mode`. | `PX4@d6f12ad:platforms/posix/src/px4/common/main.cpp:210-310,618-636`; `PX4@d6f12ad:cmd/Commander.cpp:296-349,3038-3063` | HIGH |
| A.19 | SITL `rcS` always starts `uxrce_dds_client start -t udp -p ${PX4_UXRCE_DDS_PORT:-8888}`, with `UXRCE_DDS_DOM_ID = ROS_DOMAIN_ID` (or 0), agent IP default 127.0.0.1. Docs: agent `Micro-XRCE-DDS-Agent` `v2.4.3`, run `MicroXRCEAgent udp4 -p 8888`. | `PX4@d6f12ad:ROMFS/px4fmu_common/init.d-posix/rcS:193,293-325`; `PX4@d6f12ad:docs/en/ros2/user_guide.md:144-168` | HIGH |
| A.20 | Simulated sensor noise uses libc `rand()`; `SensorBaroSim` calls `srand(1234)` once, and `SensorGpsSim` draws from the same global `rand()`. ⇒ PX4 sim noise has a **fixed, non-configurable seed**; Guará's `--seed` can only drive scenario-level randomness. Bit-exact run repeatability is additionally affected by thread scheduling: [UNKNOWN]. | `PX4@d6f12ad:src/modules/simulation/sensor_baro_sim/SensorBaroSim.cpp:44,58`; `PX4@d6f12ad:src/modules/simulation/sensor_gps_sim/SensorGpsSim.cpp:59-74` | HIGH (code); MEDIUM (effect) |
| A.22 | When `PX4_SIM_SPEED_FACTOR` is set, SITL `rcS` computes `COM_DL_LOSS_T`, `COM_RC_LOSS_T`, `COM_OF_LOSS_T`, `COM_OBC_LOSS_T` with `bc`. Without `bc` in the image, each `param set` fails ("not enough arguments") and the parameters silently stay at defaults. Observed in run `20260911T165444Z_hover_s42` (`px4.log`); fixed by installing `bc`. | `PX4@d6f12ad:ROMFS/px4fmu_common/init.d-posix/rcS:196-213` | HIGH (code + observed) |
| A.23 | Reference vehicle: PX4 docs state Pixhawk Standard autopilots "are used as the PX4 reference platform" and are "highly recommended"; the Holybro X500 V2 + Pixhawk 6C kit is "also known as the Holybro PX4 Dev Kit". Hardware airframe `4019_x500_v2` ("Holybro X500 V2"); simulation twin `4001_gz_x500` (`PX4_SIMULATOR=gz`, `PX4_SIM_MODEL=x500`) with variants `_depth`, `_vision`, `_mono_cam`, `_mono_cam_down`, `_lidar_2d`, `_lidar_down`, `_lidar_front`, `_gimbal`, `_flow`. Gazebo (gz) runs headless with `HEADLESS=1 make px4_sitl gz_x500`; it is the only supported Gazebo on Ubuntu 22.04+. | `PX4@d6f12ad:docs/en/getting_started/flight_controller_selection.md:15-16`; `PX4@d6f12ad:docs/en/frames_multicopter/holybro_x500v2_pixhawk6c.md:1-3`; `PX4@d6f12ad:ROMFS/px4fmu_common/init.d/airframes/4019_x500_v2:3`; `PX4@d6f12ad:ROMFS/px4fmu_common/init.d-posix/airframes/4001_gz_x500:1-12`; `PX4@d6f12ad:docs/en/sim_gazebo_gz/vehicles.md:16-55`; `PX4@d6f12ad:docs/en/sim_gazebo_gz/index.md:9,21,132-135` | HIGH |
| A.21 | Logger `SDLOG_MODE` default `0` = log "when armed until disarm" ⇒ a `.ulg` exists only if the vehicle armed. PX4 `Tools/setup/ubuntu.sh` supports Ubuntu 22.04/24.04 with `--no-nuttx` and `--no-sim-tools`; on Python < 3.11 it installs `requirements.txt` with `pip --user`. | `PX4@d6f12ad:src/modules/logger/module.yaml` (`SDLOG_MODE`); `PX4@d6f12ad:Tools/setup/ubuntu.sh:5-25,100-113` | HIGH |

---

## Addendum D — F´ and Ogma's F´ backend (space thread, 2026-09-12)

Facts behind ADR 0011, ADR 0012 and `docs/research/SPACE-AUTONOMY.md`. Re-derived from the
pinned clones `fprime@7d8f579` (v4.3.0) and `ogma@69485b3` (v1.15.0); no fact here is written
from memory of an API (CLAUDE.md).

| # | answer | evidence | confidence |
|---|---|---|---|
| D.1 | F´ v4.3.0 is Apache-2.0, so it raises no isolation requirement of the kind ADR 0003 imposes on DAIDALUS. | `fprime@7d8f579:LICENSE.txt:1-3` | HIGH |
| D.2 | `Svc::Health` pings each output port in a table (HTH-001), tracks timeout cycles per component (HTH-002), issues a **FATAL** event when a component fails to reply inside its timeout (HTH-003), and strokes a watchdog port only while all replies are inside their limit and the health checks pass (HTH-007). Monitoring can be enabled/disabled globally or per port and timeouts are commandable (HTH-004..006). ⇒ a hung arbiter is detectable by the platform, which PX4 achieves only indirectly (FM-4/FM-5). | `fprime@7d8f579:Svc/Health/docs/sdd.md:13-19,96-124` | HIGH |
| D.3 | `Svc::FpySequencer` loads and **validates** a compiled sequence before running it; the state machine is IDLE → VALIDATING → RUNNING, entered by `cmd_VALIDATE` / `cmd_RUN`. It is the trusted deterministic disposer ADR 0010 rule 6 requires, already written upstream. | `fprime@7d8f579:Svc/FpySequencer/docs/sdd.md:51-63,74-75,111-112` | HIGH |
| D.4 | `Svc::FpySequencer` is explicitly pre-release ("currently in development. Use at own risk") and depends on IEEE-754 `float`/`double` on the target (`SKIP_FLOAT_IEEE_754_COMPLIANCE=0`). ⇒ risk RS-2; the intent→sequence compiler is kept independent of it. | `fprime@7d8f579:Svc/FpySequencer/docs/sdd.md:3,12` | HIGH |
| D.5 | **F´ ships no safe mode.** `grep -ril "safe.\?mode" Svc Fw` over the pinned clone returns no file. ⇒ the space recovery function is new safety-critical code the project has to write (risk RS-1, ADR 0012 decision 2). | `fprime@7d8f579:Svc/`, `fprime@7d8f579:Fw/` (grep, empty result, 2026-09-12) | HIGH (absence of evidence over the pinned tree) |
| D.6 | Ogma has an F´ backend alongside cFS, ROS 2 and standalone, and **no PX4 backend** — the opening contribution C2 fills. | `ogma@69485b3:ogma-core/src/Command/FPrimeApp.hs:26`; `ogma@69485b3:ogma-core/src/Command/{CFSApp,ROSApp,Standalone}.hs` | HIGH |
| D.7 | Ogma's variable database ships `"inputs": []` and `"topics": []`; its only framework-scoped rows map `fprime/port` primitive types (`U8`…`I64`, floats) to C types. ⇒ Ogma can type an F´ port but knows no telemetry channel, for F´ or PX4. | `ogma@69485b3:ogma-core/data/variable-db.json:1-12` | HIGH |
| D.8 | The generated F´ monitor is a `queued component Copilot` emitted into `module Ref` (line 1), with one `async input port <var>In` per monitored variable and one **event** per violation. Its only outputs are `event port eventOut` and `text event port textEventOut`: there is **no output port carrying a verdict** another component could act on, and the module name is hardcoded. ⇒ the two upstream openings of P7b (AC-45, AC-46). | `ogma@69485b3:ogma-core/templates/fprime/Copilot.fpp:1,8,15,32,44,58-64` | HIGH |

F´ flight heritage (ISS-RapidScat, ASTERIA, Ingenuity) is a **[WEB]** claim sourced in
`docs/research/SPACE-AUTONOMY.md` §9, not a source-code fact, and is never used to support a
statement about Guará's own assurance.

---

## UNKNOWN / MEDIUM questions blocking P1 — status

None of the 6 questions ended UNKNOWN. Items below are MEDIUM or gaps that P1
treats as **hypotheses** or that need a new P0/SITL run.

| # | Item | Status | Resolution / next action |
|---|---|---|---|
| 1 | **Real detection time of dead executor** (2.3, 2.4) | OPEN — needs SITL | Chain read, not exercised. AC-15 (M3): `kill -9` in flight, extract `nav_state` transition time from ULog. Blocked by R-11 (Docker/disk). |
| 2 | **Arbiter dead while scheduled internal mode is active** (2.6) | OPEN — needs SITL | Inferred from absence of code. AC-15b (M3). Mitigation if confirmed: accept (Hold is a safe terminal state; PX4 failsafes remain active) and document in SPEC §7. |
| 3 | **Arbiter cannot re-register while armed** (2.7) | DECIDED | ADR 0001 rule 6: keep `COM_MODE_ARM_CHK=0` (PX4 itself labels enabling it unsafe, A.16); accept FM-3. Verified by AC-15c. |
| 4 | **"Loss of well-clear" semantics in DAIDALUS** (5.5) | CODE RESOLVED (A.14); parameters OPEN | Use `timeToCorrectiveVolume` = corrective-level WCV volume. DO-365B thresholds for small drones remain [HYPOTHESIS] (5.8); custom `.conf` with sourced thresholds in M5 ([PARAMETER TBD]). |
| 5 | **NOSA terms** (5.10) | TEXT RESOLVED (A.12) | Legal interpretation remains [REVIEW]. |
| 6 | **FRET → Ogma flow** (4.7) | FORMAT RESOLVED (A.15); execution OPEN | Keys match; run FRET export → `ogma ros` on one requirement at M2 start. |
| 7 | **Distro divergence** (R0.2 vs R0.4) | RESOLVED 2026-09-11 | User confirmed Humble; Ogma template (Jazzy) replaced by own template in M2. |
