# ADR 0011 — F´ as the second RTA host, after PX4

- Status: Accepted (2026-09-11); implementation M13–M15 (`docs/PLAN-M8-M16.md`)
- Related: ADR 0001 (arbiter as ModeExecutor), ADR 0002 (monitors on companion first),
  ADR 0006 (Apache-2.0), SPEC §7.7 and §7.9; `docs/research/SPACE-AUTONOMY.md` §2, §4

## Context

SPEC §7.7 concedes the weakest point of the current architecture: the arbiter runs on a
companion computer, outside the FMU, with latencies that are measured rather than bounded.
ADR 0002 accepted that deliberately as a phase-1 decision and named "monitors inside the
FMU" as phase 2. Putting the decision core inside PX4 means writing an uORB module inside a
BSD-licensed autopilot with no autocoding and no component model — a large, project-specific
piece of work that produces no reusable artifact.

F´ `v4.3.0` is pinned in `third_party/VERSIONS.md` and was read for
`docs/research/SPACE-AUTONOMY.md`. Three properties make it the cheaper second host:

- Ogma already has an F´ backend (`ogma-core/src/Command/FPrimeApp.hs`), so the
  monitor-generation chain does not change.
- F´ supplies, as framework services, the platform-side failure detection that Guará had to
  infer from PX4 behaviour: `Svc::Health` pings active components, tracks timeout cycles,
  raises FATAL, and strokes a hardware watchdog only while every reply is inside its limit.
- F´ supplies a validated on-board sequencer (`Svc::FpySequencer`) that loads and *validates*
  a compiled sequence before running it — the trusted deterministic disposer that ADR 0010
  rule 6 requires, already written and already unit-tested upstream.

F´ also has flight heritage (ISS-RapidScat, ASTERIA, Ingenuity), which is the property that
changes how the architectural claim reads to a reviewer.

## Decision

1. **F´ becomes the second host of the same architecture, not a fork of it.** The
   `DecisionCore` switching logic of SPEC §3 is the shared artifact: it is already
   allocation-free, fixed-period and free of ROS 2 types (`decision_core.hpp`,
   `types.hpp`). The port is a new *adapter* layer, not a new decision core, and any
   behavioural difference between the two hosts is a defect.
2. **The port is ordered strictly after the PX4 results.** No F´ work starts before M7
   (latency) and P4 (batch benchmark) are complete. The PX4 thread is what the preprint
   depends on; the F´ thread is what the architecture claim depends on.
3. **The shared core is extracted first, and the extraction is verified by re-running the
   existing PX4 tests unchanged.** If `guara_rta`'s own ACs (AC-4, AC-5, AC-6, AC-12,
   AC-13) do not pass against the extracted core with no edits to the test files, the
   extraction is wrong.
4. **The F´ recovery function is a first-class deliverable with its own requirements.** F´
   ships no safe mode (`docs/research/SPACE-AUTONOMY.md` §2.2, verified by grep over the
   pinned clone). On PX4 the recovery function was free and assured; on F´ it is new
   safety-critical code. It gets FRETish requirements, its own milestone and its own
   acceptance criteria, and the project states plainly that it has no heritage.
5. **Platform-side failure detection is used, not re-implemented.** The arbiter registers
   with `Svc::Health` so that a hung decision core is detected by the framework
   (the F´ analogue of FM-4/FM-5), and the heartbeat logic of SPEC §5 is kept only where
   `Svc::Health` does not already cover the case.
6. **Ogma's F´ backend is extended upstream rather than worked around.** The generated
   monitor currently emits only events and is hardcoded into `module Ref`
   (`docs/research/SPACE-AUTONOMY.md` §4.2). A verdict output port and a configurable
   module name are contributed upstream as the F´ sibling of contribution C2; the F´
   arbiter consumes generated monitors, never hand-written copies of them.
7. **License posture is unchanged.** F´ is Apache-2.0, the same as Guará (ADR 0006) and
   Ogma, so no isolation of the kind ADR 0003 imposes on DAIDALUS is required. DAIDALUS
   stays out of the F´ thread entirely: there is no DAA channel in the space domain
   (ADR 0012).

## Consequences

- (+) SPEC §7.7 stops being a permanent limitation and becomes a phase: the same core runs
  in a flight software framework with rate groups, health monitoring and a watchdog.
- (+) The architecture claim is demonstrated on two unrelated platforms with two different
  recovery functions, which is a much stronger statement than one platform with one.
- (+) Two small, self-contained upstream contributions to `nasa/ogma` instead of one.
- (−) The recovery function must be written and has no heritage (risk RS-1). This is the
  cost of the decision and is stated wherever the F´ thread is claimed.
- (−) `Svc::FpySequencer` is marked pre-release upstream (risk RS-2), so the intent→sequence
  compiler is kept independent of it and a hand-rolled executor must remain possible.
- (−) Scope risk against the 12-week plan (risk RS-3), bounded by decision 2.
