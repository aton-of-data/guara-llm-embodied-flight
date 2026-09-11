# Guará

Runtime Assurance (ASTM F3269-aligned architecture) for PX4 multicopters via ROS 2 Humble.

An untrusted complex function commands the vehicle; the arbiter switches to PX4 internal
modes (Hold / RTL / Land) when monitors predict a geofence violation, loss of well-clear,
a Copilot requirement violation, or stale/invalid inputs.

This is not certification. What the system does and does not guarantee is in
[`docs/SPEC.md`](docs/SPEC.md) §6–§7.

## Status

Milestone M1 (headless PX4 SITL) is complete: [`docs/milestones/M1.md`](docs/milestones/M1.md).
Acceptance-criterion tracker: [`docs/milestones/STATUS.md`](docs/milestones/STATUS.md).

| Piece | Location |
|---|---|
| Switching logic | `ros2_ws/src/guara_rta` (`DecisionCore`, ModeExecutor node) |
| Geofence predictor | `ros2_ws/src/guara_geofence` |
| Copilot monitors | `ros2_ws/src/guara_monitors` (Ogma template + generated C) |
| DAA (NOSA) | `nosa/guara_daidalus` (not on the default colcon path) |
| Messages | `ros2_ws/src/guara_msgs` |
| Parameters | `config/rta_params.yaml` |
| Pinned APIs | `third_party/VERSIONS.md` |

## Quick start

```bash
# Clone pinned third-party sources (once)
./scripts/fetch_third_party.sh

# Dev image: ROS 2 Humble + PX4 v1.17.0 SIH SITL + Micro XRCE-DDS Agent
./scripts/dev.sh colcon build --symlink-install
./scripts/dev.sh colcon test --packages-select guara_rta guara_geofence guara_monitors
./scripts/sitl_run.sh --scenario hover --seed 42 --headless

# NOSA-isolated DAIDALUS node (ADR 0003); omitted from the default colcon path
./scripts/daa.sh build
./scripts/daa.sh test

# Formal-methods image: FRET sources + Ogma + Copilot (generation only)
./scripts/fm.sh ros2_ws/src/guara_monitors/scripts/generate.sh
```

Commands run inside Docker with the repository mounted at `/work`. Images:
`guara-dev:m1` (`docker/Dockerfile`) and `guara-fm:m2` (`docker/Dockerfile.fm`).

## Layout

```
config/          RTA parameters copied into every run's config.yaml
docker/          development and formal-methods images
docs/            SPEC, ADRs, milestone reports, research notes
nosa/            NOSA-licensed packages only (DAIDALUS; ADR 0003)
ros2_ws/         Guará ROS 2 packages
scenarios/       headless SITL scenarios
scripts/         container wrappers, run contract, AC checkers
third_party/     pinned clones (not versioned; see VERSIONS.md)
```

## License

Apache-2.0. DAIDALUS and FRET stay under NOSA and must not leak outside `nosa/`
and generation-time tooling (ADR 0003, ADR 0006).
