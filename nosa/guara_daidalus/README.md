# SPDX-License-Identifier: Apache-2.0
# guara_daidalus — NOSA-isolated DAIDALUS node (ADR 0003)

Copyright 2016–2021 United States Government as represented by the Administrator
of the National Aeronautics and Space Administration. No copyright is claimed
in the United States under Title 17, U.S. Code. All Other Rights Reserved.

This package **links** NASA DAIDALUS v2.0.3a (Detect and Avoid Alerting Logic
for Unmanned Systems). DAIDALUS is Subject Software under the NASA Open Source
Agreement v1.3 (`LICENSE` / `LICENSE.pdf`). Guará does not imply NASA
endorsement of this Larger Work (NOSA 3.E).

The public interface of this package is `guara_msgs/DaaStatus` on
`/guara/daa/status`. Apache-2.0 packages must not depend on this package or
include DAIDALUS headers (AC-11).

## Build

`nosa/` is not on the default colcon base-paths so the rest of Guará builds with
this package absent (ADR 0003). From the repository root:

```bash
./scripts/fetch_third_party.sh   # provides third_party/daidalus
./scripts/daa.sh build
./scripts/daa.sh test
```

## Configuration

`set_DO_365B()` (Phase I / II / Non-Cooperative, with SUM). DO-365B well-clear
thresholds are sized for larger UAS (SPEC R-5, [G 5.8]); they remain
[HYPOTHESIS] for small civil drones.

## Topics

| Direction | Topic | Type |
|---|---|---|
| in | `fmu/out/vehicle_global_position` | `px4_msgs/VehicleGlobalPosition` |
| in | `fmu/out/vehicle_local_position_v1` | `px4_msgs/VehicleLocalPosition` |
| in | `fmu/out/transponder_report` | `px4_msgs/TransponderReport` |
| out | `/guara/daa/status` | `guara_msgs/DaaStatus` |
