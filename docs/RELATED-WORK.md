# Related work and the open threads Guará answers

Where Guará sits relative to the projects and papers it builds on, and what it contributes
back to each. Split out of the README, which links here from §2.

---

Guará is deliberately *downstream* of existing projects. Each row is a thread left open in
another repository or paper, and what Guará contributes to it.

## 2.1 Upstream tools Guará extends

| Repository | What it gives | Open thread | Guará's answer |
|---|---|---|---|
| [nasa/ogma](https://github.com/nasa/ogma) `v1.15.0` | FRETish → Copilot → C99 monitor generation, ROS 2 backend | No PX4 variable database or example | `guara_monitors` carries a `px4_msgs` variable DB, a customised ROS template and a generated monitor over `/fmu/out/*`; upstreaming is contribution **C2** |
| [Copilot-Language/copilot](https://github.com/Copilot-Language/copilot) `v4.8.1` | Constant-time, allocation-free monitor C99; CopilotVerifier proofs | Verifier toolchain unavailable on this host (risk R-11) | Monitors are generated and unit-tested today; proof generation is the RQ4 deliverable |
| [NASA-SW-VnV/fret](https://github.com/NASA-SW-VnV/fret) `v3.1.0` | FRETish → pmLTL, export to Ogma | Export path never exercised for PX4 properties | `REQ-ALT-01` runs the flow end to end into a flying monitor (M2) |
| [nasa/daidalus](https://github.com/nasa/daidalus) `v2.0.3a` | DO-365 well-clear, time to violation, maneuver bands | NOSA licence blocks mixing with permissive stacks; DO-365B thresholds are sized for large aircraft | `nosa/guara_daidalus` is a licence-isolated ROS 2 node ([ADR 0003](adr/0003-daidalus-nosa-isolation.md)); small-UAS thresholds remain open risk R-5 |
| [nasa/icarous](https://github.com/nasa/icarous) | The architectural precedent: DAIDALUS + PolyCARP as cFS apps | Dormant since 2022, cFS-bound, external autopilot | Same roles, rebuilt on PX4 + ROS 2 with the autopilot itself as the recovery function |
| [PX4/PX4-Autopilot](https://github.com/PX4/PX4-Autopilot) `v1.17.0` | Internal modes as a recovery function; external-mode interface | [PR #20707](https://github.com/PX4/PX4-Autopilot/pull/20707) suggests extending fallback beyond arming-check timeouts | Guará is a semantic fallback layered on the existing interface, leaving PX4 failsafes untouched and authoritative |
| [Auterion/px4-ros2-interface-lib](https://github.com/Auterion/px4-ros2-interface-lib) `release/1.17` | `ModeExecutorBase`, owned modes, `scheduleMode` | Executor-death timing in flight documented only partially | Failure modes FM-1…FM-5 are measured in SITL and recorded in [`docs/SPEC.md` §5](SPEC.md) |

## 2.2 Natural-language drone control: what everyone leaves to the prompt

Prior art for talking to a drone is real and growing. What is missing is uniform.

| Work | Approach | Stated safety basis |
|---|---|---|
| ChatGPT for Robotics / PromptCraft ([arXiv 2306.17582](https://ar5iv.labs.arxiv.org/html/2306.17582)) | LLM writes code over an AirSim function library | Human reviews the code |
| TypeFly ([arXiv 2312.14950](https://arxiv.org/abs/2312.14950)) | LLM emits MiniSpec, a token-efficient DSL | The DSL restricts the action set |
| Taking Flight with Dialogue ([arXiv 2506.07509](https://arxiv.org/abs/2506.07509)) | PX4 + ROS 2 + local Ollama, sim and real quadcopter | Not specified |
| EchoPilot ([PX4 forum](https://discuss.px4.io/t/echopilot-langgraph-mcp-server-for-natural-language-px4-control/46998)) | Voice → LangGraph → MCP → MAVSDK → PX4 | Telemetry verification; author asks the community for safety ideas |
| [MAVLinkMCP](https://github.com/ion-g-ion/MAVLinkMCP), [ardupilot-mcp](https://github.com/rmeadomavic/ardupilot-mcp) | MCP servers exposing MAVLink to agents | SITL-first, human in the loop |
| Universal LLM–Drone C2 ([arXiv 2601.15486](https://arxiv.org/html/2601.15486v2)) | MCP + MAVSDK, many models, caged sub-250 g drone | Human override; non-determinism acknowledged |
| AerialClaw ([arXiv 2606.12142](https://arxiv.org/abs/2606.12142)) | Brain–skill–runtime agent framework on PX4 SITL | "Safety-oriented runtime validation", unspecified |

The shared pattern is **safety = prompt engineering + tool restriction + human override**.
None of the surveyed work places a formally specified, latency-measured runtime-assurance
boundary between the model and the autopilot. That boundary is what this repository is.

The adversarial side of the same literature is why the boundary must be independent of the
model: [RoboPAIR](https://arxiv.org/abs/2410.13691) reports a 100% jailbreak rate against three
LLM-controlled robots, and [DolphinAttack](https://arxiv.org/pdf/1708.09537) shows voice itself
is an attack surface. Guardrail-style answers ([RoboGuard](https://arxiv.org/abs/2503.07885),
[SafePlan](https://arxiv.org/abs/2503.06892), [Safety Chip](https://arxiv.org/pdf/2309.09919))
constrain the *planner*; Guará constrains the *aircraft*, which is the only layer a jailbreak
cannot talk its way past.

## 2.3 The same chain, in orbit

The requirements half of the chain — FRET → Ogma → Copilot — already targets cFS and F´, the
flight software of spacecraft and small satellites, as first-class backends. Three facts,
re-derived from the pinned clones and recorded in [`GROUNDING.md`](../GROUNDING.md) Addendum D,
decide the shape of the space thread:

- **F´ detects, but does not recover.** `Svc::Health` pings components, tracks timeouts, raises
  FATAL and strokes a watchdog (D.2) — and a grep for `safe.?mode` over `Svc/` and `Fw/` returns
  nothing (D.5). On PX4 the recovery function was free; on F´ it is the most safety-critical
  code the project would have to write.
- **The trusted disposer already exists.** `Svc::FpySequencer` validates a compiled sequence
  before running it (D.3) — exactly the artifact [ADR 0010](adr/0010-untrusted-complex-function-contract.md)
  rule 6 demands between a model and an actuator. It is pre-release upstream (D.4), so nothing
  here depends on it irreversibly.
- **Ogma's F´ monitors cannot trigger anything.** The generated component emits events only,
  into a hardcoded `module Ref`, with no verdict output port (D.8). That is the same gap G3
  identifies for PX4, restated in the space domain — and two small upstream contributions.

So the space thread is a *rewrite* of the signals, not a port: `T_gf`'s braking model assumes a
vehicle that can stop, and `T_daa` is an air-traffic construct
([ADR 0012](adr/0012-space-domain-rta-mapping.md),
[`docs/research/SPACE-AUTONOMY.md`](research/SPACE-AUTONOMY.md)). What transfers is the
architecture: predicted time to violation, threshold with hysteresis, asymmetric switch, gate on
the untrusted function. Analytic keep-out tests live in `space/keepout.py` and pass AC-47
([`docs/milestones/M13c.md`](milestones/M13c.md)). **No F´ deployment has run.** Everything
*measured* in this repository is PX4 multicopter in SITL.
