# ADR 0006 — Project license: Apache-2.0

- Status: Accepted (author decision, 2026-09-11) · Legal review of NOSA interplay: [REVIEW]
- Related: ADR 0003 item 7; PROPOSAL §3 (C2), §9; P7

## Context

The author asked for an open-source license on par with leading NASA projects. Evidence (2026-09-11):

| Project | License | Evidence |
|---|---|---|
| nasa/ogma | Apache-2.0 (moved from NOSA) | GitHub API `license.spdx_id`; `ogma@69485b3:ogma-core/CHANGELOG.md:93` (#293) |
| nasa/cFS | Apache-2.0 | GitHub API `license.spdx_id` |
| nasa/fprime | Apache-2.0 | GitHub API `license.spdx_id` |
| ROS 2 (`ros2/rclcpp`) | Apache-2.0 | GitHub API `license.spdx_id` |
| PX4-Autopilot, px4_msgs, px4-ros2-interface-lib, Copilot | BSD-3-Clause | `third_party/VERSIONS.md` |
| DAIDALUS, FRET | NOSA 1.3 | `third_party/VERSIONS.md`; [G A.12] |

Requirements: (1) upstream contribution to Ogma (P7) must be Apache-2.0 compatible; (2) linking with BSD-3
PX4 libraries; (3) explicit patent grant, relevant for a safety product adopted by companies;
(4) permissive, to maximize adoption by agricultural and industrial integrators.

## Options

A. Apache-2.0. B. BSD-3-Clause (PX4 style). C. MIT. D. NOSA 1.3. E. GPL-3.0 / LGPL.

## Decision

**A — Apache-2.0** for all Guará code, docs and configuration outside `nosa/`.

1. `LICENSE` = canonical Apache-2.0 text from apache.org; `NOTICE` lists copyright and third-party licenses.
2. Every new source file starts with `SPDX-License-Identifier: Apache-2.0`.
3. `nosa/` packages stay under NOSA 1.3 with their own `LICENSE` (ADR 0003); AC-11 enforces isolation.
4. Contributions are accepted under Apache-2.0 §5 (inbound = outbound); no CLA for now.

## Rationale

- Matches NASA's own modern open-source choice (Ogma moved from NOSA to Apache; cFS and F Prime are Apache-2.0)
  and ROS 2; makes P7 a same-license contribution.
- Patent grant and termination clause (Apache §3) give adopters more certainty than BSD/MIT.
- NOSA is agency-specific, rarely used outside NASA, and would complicate integration with ROS 2 / PX4 ecosystems.
- Copyleft (E) would deter integrators who ship closed airframes, reducing safety-layer adoption.

## Consequences

- (+) Same license as Ogma, cFS, F Prime and ROS 2; compatible with BSD-3 dependencies.
- (−) Apache-2.0 obligations (NOTICE, change statements) apply to redistributors.
- (−) Apache-2.0 is incompatible with GPL-2.0-only code; such dependencies are not allowed.
- Pending: human legal review of distributing containers that include NOSA-licensed DAIDALUS (SPEC R-9).
