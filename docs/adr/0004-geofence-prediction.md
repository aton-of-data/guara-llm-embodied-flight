# ADR 0004 — Geofence prediction strategy

- Status: Proposed (P1, 2026-09-11)
- Related: SPEC §3.1 (`T_gf`), §3.3 (O-1); AC-8, AC-9, AC-22

## Context

- No geofence topic is exposed by the default bridge [G 3.4].
- PX4 has an internal geofence with `GF_ACTION` (default Hold) and `GF_PREDICT`
  marked experimental with a "flyaways" warning [G A.11].
- `vehicle_local_position_v1` provides NED position/velocity/acceleration,
  validity flags, reset counters and `eph/evh` [G A.8], at up to 50 Hz [G 3.1].
- Engineering requirements: allocation-free, bounded-time computation (CLAUDE.md).

## Options

A. Use PX4 `GF_PREDICT` as Safety Monitor.
B. Expose `geofence_result` via custom `dds_topics.yaml` and react to violation.
C. Own predictor on the companion: time until crossing the boundary, with a braking model.
D. Full reachable set (reachability).

## Decision

**C**, with PX4's internal geofence kept active as an independent layer
(`GF_ACTION` ≠ 0, without `GF_PREDICT`).

Definition (v1):

1. Inclusion geofence = simple polygon (convex or concave) in local NED,
   up to `N_max_vert` = 64 vertices [HYPOTHESIS], plus altitude ceiling and floor.
   Stored in a fixed-size array; loaded at initialization.
   lat/lon → NED conversion uses `ref_lat/ref_lon`; an increment of
   `xy_reset_counter` or a reference change invalidates the input (`V(k)=1`) until reprojection.
2. Stopping distance (horizontal): `d_stop(v) = |v|²/(2·a_brake) + e_pos`,
   with `a_brake` [HYPOTHESIS, measured in M4] and `e_pos = k_σ·eph` [HYPOTHESIS `k_σ`=2].
   Latency does **not** enter here; it is covered by the threshold (SPEC O-1: `τ_gf ≥ δ_lat`).
3. `D` = distance along `v̂` to the first edge crossing from
   `p` (ray-segment intersection over all edges, O(N), allocation-free).
   `T_gf = max(0, (D − d_stop)/|v|)`: remaining time until the last instant at which
   starting to brake still avoids the violation. Vertical analog with `vz`, ceiling/floor
   and `a_brake,z`; `T_gf` = minimum of both.
   If already outside the geofence: `T_gf = 0`. If `|v| < v_min` and inside: `T_gf = +∞`.
4. Wind: not modeled in v1 beyond what is already in estimated `v`; scenarios
   with gusts (P4) measure the effect. `τ_rec,gf` and `a_brake` are measured in SITL.
5. Maximum horizon `T_hor` = 30 s [HYPOTHESIS]; beyond it `+∞`.

## Rationale

- A (`GF_PREDICT`) is explicitly experimental in code [G A.11] and lives
  inside the FMU, out of reach of Guará's Switching Logic.
- B only reports a violation that already happened (or the experimental predictor's), with no time margin.
- D is stronger but expensive and hard to bound in time; left as future work.

## Consequences

- (+) Continuous `T_gf`, comparable to threshold `τ_gf`, analytically testable (AC-8).
- (+) Two independent layers (Guará + PX4 geofence).
- (−) The constant-velocity model underestimates risk in turns or under gusts.
- (−) Duplicated polygon (Guará and PX4) may diverge; the scenario must load both
  from the same file and `config.yaml` records the hash.
