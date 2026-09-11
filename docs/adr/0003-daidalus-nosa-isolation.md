# ADR 0003 — Isolation of the DAIDALUS NOSA license

- Status: Proposed (P1, 2026-09-11) · Legal interpretation: [REVIEW]
- Related: SPEC §2, §3.1 (`T_daa`); AC-10, AC-11

## Context

DAIDALUS v2.0.3a is distributed under the NASA Open Source Agreement v1.3 [G 5.10, A.12].
Obligations read in the text:

- redistribution under the NOSA itself, with a copy of the agreement (3.A.1);
- binary distribution requires making source available (3.A.2);
- prominent NASA copyright notice (3.B);
- modifications identified in a changelog file with author and date (3.C);
- do not imply NASA endorsement (3.E);
- a "Larger Work" with software under another license is allowed, keeping the
  NOSA part under NOSA (3.I); inclusion in a Larger Work is not, by itself, a Modification (1.F);
- US export control notice (3.J).

The text does **not** address compatibility with Apache-2.0 (Ogma) or BSD-3-Clause
(PX4, interface-lib, Copilot). The upstream contribution to Ogma (P7) requires that
nothing NOSA enters it. DAIDALUS C++ has no CMake [G 5.9].

## Options

A. Link DAIDALUS inside `guara_rta`.
B. Separate ROS 2 package, separate process, message-only communication.
C. Separate repository.

## Decision

**B**, prepared to become C without interface change:

1. Directory `nosa/guara_daidalus/` with `LICENSE` = NOSA 1.3 (copy of PDF/text),
   NASA copyright notice and `CHANGES.md` (clause 3.C) for any change
   to DAIDALUS sources.
2. DAIDALUS sources are **not** copied into the repository: the `guara_daidalus` CMake
   builds from `third_party/daidalus` at the pinned commit.
   If that changes, item 1 applies in full.
3. Public interface = `guara_msgs/DaaStatus` (Guará license). No package
   outside `nosa/` depends on `guara_daidalus` or includes DAIDALUS headers
   (AC-11, `scripts/check_license_isolation.py`).
4. The rest of Guará builds, tests and runs with `guara_daidalus` absent;
   then `DaaStatus` is not published and the DAA input is marked missing.
   If the scenario requires DAA, `V(k)=1` (SPEC §3.1); if not, the DAA channel is disabled in configuration.
5. Container images with DAIDALUS are labeled as containing NOSA software
   and ship the agreement text and the link to the source (3.A.2).
6. No project material implies NASA endorsement (3.E).
7. License of Guará's own code: **[PARAMETER TBD]** by the author
   (Apache-2.0 would ease P7).

## Consequences

- (+) The Ogma contribution (P7) and other packages stay NOSA-free.
- (+) A DAIDALUS crash does not bring down the arbiter; it becomes stale data (FM-6).
- (−) Extra latency `L3` on the DAA path.
- (−) Messages duplicate units/conventions; requires an equivalence test (AC-10).
- Pending: human legal review before publishing binaries or containers.
