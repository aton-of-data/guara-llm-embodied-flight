# ADR 0007 — Reference airframe: Holybro X500 V2 + Pixhawk Standard FC

- Status: Accepted (author decision, 2026-09-11)
- Related: SPEC §1; ADR 0009; M1 report; GROUNDING A.17, A.23

## Context

The author asked for the most recommended, most widely used PX4 airframe to maximize global impact.
Guará depends on PX4's external-mode interface (ADR 0001), so the vehicle must run PX4.

Verified facts [G A.23]:
- PX4 docs: Pixhawk Standard autopilots "are used as the PX4 reference platform", "supported and tested by the
  PX4 development team, and are highly recommended".
- PX4 docs call the Holybro X500 V2 + Pixhawk 6C kit "the Holybro PX4 Dev Kit".
- PX4 ships a hardware airframe `4019_x500_v2` and the same vehicle in simulation: `4001_gz_x500` plus sensor
  variants (depth, mono camera, down camera, lidar, gimbal, optical flow); Gazebo supports `HEADLESS=1`.
- SIH provides a generic `sihsim_quadx` (used in M1) without Gazebo.

External (vendor page): the kit ships with Pixhawk 6C, GPS, telemetry radio, and a companion-computer mount
(Raspberry Pi / Jetson) — [Holybro](https://holybro.com/products/px4-development-kit-x500-v2).
Secondary source: heavy-lift open agricultural sprayers are more often built on ArduPilot than PX4
([example](https://zbotic.in/octocopter-drone-build-heavy-lift-platform-for-industry/)) — unverified market share.

## Options

A. Holybro X500 V2 + Pixhawk 6C/6X (PX4 Dev Kit). B. Generic `sihsim_quadx` only. C. A heavy-lift agricultural
hexa/octa as reference. D. ModalAI Starling / PX4 Vision (integrated companion).

## Decision

**A**, as a three-tier vehicle strategy:

| Tier | Vehicle | Use | Status |
|---|---|---|---|
| T0 batch sim | `sihsim_quadx` (SIH, headless) | Fast CI and statistical batches (P4) | In use (M1) |
| T1 reference | `gz_x500` family in Gazebo (headless) ↔ Holybro X500 V2 + Pixhawk 6C/6X hardware | Fidelity runs, `a_brake`/`τ_rec` measurement, camera/payload scenarios, first real flights | Planned: image variant with Gazebo (M4) |
| T2 heavy-lift | PX4 multicopter hexa/octa with dispensing payload (airframe [PARAMETER TBD]) | Spraying/spreading capability packs (ADR 0009) | Phase 3; needs new P0 on PX4 payload/actuator outputs |

Rules:
1. All ACs that measure dynamics (`a_brake`, `τ_rec`, `δ_lat`) are reported per tier; T0 numbers never stand in for T1.
2. Nothing in `guara_rta` may depend on a specific airframe; vehicle specifics live in scenario/airframe config.
3. Airframe parameters used in any run are captured in `results/{run_id}/config.yaml`.

## Consequences

- (+) Same vehicle in sim and hardware, the PX4 team's reference, low cost, global availability → reproducible by others.
- (+) Camera/lidar Gazebo variants cover survey and inspection packs without custom models.
- (−) X500 V2 is a development-class quad; it cannot represent heavy agricultural sprayers (T2 open).
- (−) If heavy-lift agriculture is dominated by ArduPilot, global agricultural impact may later require an
  ArduPilot port of the arbiter interface; the RTA logic (`DecisionCore`, monitors) is kept autopilot-agnostic
  to allow it. [REVIEW market data]
- (−) Gazebo on the arm64 dev host is unverified; T1 image may need an x86-64 runner.
