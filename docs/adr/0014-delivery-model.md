# ADR 0014 — how Guará is delivered: a safety kernel, a conformance kit, two host packages

- Status: Proposed (2026-09-13); implementation M17–M20 (`docs/PLAN-M17-M28.md`)
- Related: ADR 0001 (arbiter as ModeExecutor), ADR 0003 (NOSA isolation), ADR 0006
  (Apache-2.0), ADR 0010 (untrusted CF contract), ADR 0011 (F´ as second host);
  `docs/SPEC.md` §2, §3

## Context

Everything the project has produced so far is delivered as *a repository you clone*: one
container image built locally, one ROS 2 workspace built from source, and evidence
directories. That is the right shape for a research artifact and the wrong shape for the
next goal, which is an LLM-bounded flight on real hardware — air and space — reproducible
by someone who is not the author.

Before choosing a packaging, the delivery models actually used by comparable systems were
surveyed. The question is not "library or not"; it is *which artifact a third party
installs, and what they are entitled to conclude from having installed it*.

| # | Model | Exemplars | What ships | Fit for Guará |
|---|---|---|---|---|
| D1 | Module inside the autopilot / FSW | PX4 modules, ArduPilot scripting, cFS apps | a merged upstream module | **No** for air: PX4 *is* the recovery function; an arbiter inside it shares the failure domain it is supposed to bound (SPEC §7.7, ADR 0002). Partial for space, where the host is F´ and D5 applies |
| D2 | ROS 2 package set, binary-released | Nav2, MoveIt, `robot_localization` (bloom → `ros-humble-*`) | apt packages + source | **Yes, air.** The companion-computer world installs this way. Constraint: Humble is EOL 2027-05 |
| D3 | Vendor companion-OS app, containerised | Auterion SDK / AuterionOS app store, ModalAI VOXL, NVIDIA Isaac ROS | an OCI image for a specific board | **Yes, as a variant.** This is where flying hardware actually is; it is also how a project gets captured by one vendor |
| D4 | Embeddable library with a stable ABI | MAVSDK, DAIDALUS | source + CMake package + bindings | **Yes, as the kernel — not as the product.** An ABI alone does not put anything on a vehicle |
| D5 | F´ library / package | `fprime-community` libraries (`library.cmake`), fppm | a git repo an integrator adds to a deployment | **Yes, space.** The direct consequence of ADR 0011 |
| D6 | Reference implementation + conformance kit | FACE conformance, MISRA/AUTOSAR test suites | a spec, golden vectors, a runner, a report | **Yes — the differentiator.** ASTM F3269 is an architectural practice with no public reference implementation and no conformance vectors. Nobody has shipped this |
| D7 | Certification data package / supplier item | DO-178C reusable components, DO-330 tool qualification kits | source plus plans, traceability and verification evidence | **Not now.** Needs a DAL, an applicant and an audit. But the *shape* of the evidence must be chosen now, or it gets retrofitted at ten times the cost |
| D8 | Research artifact | the current repository | preprint + repo + evidence | **Keep.** It is the credibility base; it must stop being the ceiling |
| D9 | Open core with a commercial kit | common in avionics tooling | Apache core, paid assurance kit | Permitted by ADR 0006, deliberately not designed for now |

Two observations decided this ADR.

First, **no single model fits, and the models are not alternatives — they nest.** D4 is the
input to D2 and D5; D2 and D5 are the input to D3; D6 is what makes any of them mean
something; D7 is D6 grown up.

Second, **the artifact that distinguishes Guará is not the code.** A switching core is a few
hundred lines that a competent engineer reproduces in a week. What is expensive, and what
does not exist publicly for F3269, is *the evidence that a given implementation on a given
host behaves like the specified one*, and the boundary contract that keeps an untrusted
complex function — an LLM — outside it (ADR 0010). Delivery must make those two things
installable, not just readable.

## Decision

1. **The unit of delivery is a versioned safety kernel plus the proof that a port behaves
   like it.** Concretely: `guara-core` (D4) and `guara-ctk` (D6) are released together, and
   no host package is released whose conformance report is absent or failing.

2. **Five artifacts, one source tree.**

   | Artifact | Model | Contents | Consumer |
   |---|---|---|---|
   | `guara-core` | D4 | host-free C++17 switching core + a C ABI, no allocation, no I/O, no clock | any host |
   | `guara-ctk` | D6 | golden input→decision vectors, a portable runner, a signed report format | any implementer, including third parties |
   | `guara-ros` | D2 | `guara_rta`, `guara_msgs`, `guara_geofence`, the PX4 adapter, binary-released | air companion computers |
   | `guara-fprime` | D5 | an F´ library (`library.cmake`, fppm manifest) with the arbiter component and the safe mode | satellite integrators |
   | `guara-companion` | D3 | a multi-arch OCI image: `guara-ros` + CLI + preflight, arm64 first | flight hardware, generic board as reference, vendor boards as variants |

   Plus `guara` on PyPI — the mission/space compilers, the CTK runner and the `guara` CLI —
   which is the tier-0 install the README's 60-second path already promises.

3. **The C ABI is provisional until three independent ports pass the CTK** (ROS 2, F´, and a
   deliberately independent reimplementation). Freezing an interface before it has been
   implemented twice by someone other than its author is how interfaces become wrong forever.

4. **Conformance is necessary and never sufficient.** The CTK report states, in its own text,
   that passing it demonstrates behavioural equivalence to the reference decision core on the
   published vectors and *nothing about the safety of the system that contains it*. No
   artifact Guará publishes — package metadata included — uses the word "safe" of itself
   (SPEC §7, `docs/PLAN-M8-M16.md` §5).

5. **The evidence bundle is a first-class delivered artifact, not a by-product.** Every
   release carries an SBOM, a provenance attestation, and the conformance report; every
   hardware run carries a bundle that `guara verify` checks offline. This is D7's shape
   adopted early at D8's cost.

6. **The licence boundary survives packaging.** No published artifact embeds NOSA code
   (ADR 0003): DAIDALUS stays in `nosa/` and is delivered, if at all, as a separate
   source-only package the integrator builds. The release job refuses to publish otherwise
   — the rule already enforced for `guara-fm` in `.github/workflows/publish-dev-image.yml`.

7. **The generic target is the reference; vendor boards are variants.** `guara-companion`
   builds for a documented generic arm64 board first (M22). A vendor image may follow; it
   never becomes the only tested path.

## Consequences

- The extraction promised by M13 stops being an F´ prerequisite and becomes the project's
  main product surface: it is re-scoped as M18 and ordered *before* the F´ deployment.
- Two release trains appear where there was one repository: a source tree that must stay
  reproducible, and published binaries that must stay signed, dated and revocable.
- Humble's EOL (2027-05) becomes a scheduled item rather than an ambient risk (AC-71).
- The project acquires users who never read the SPEC. Everything they can install must
  therefore carry, in the artifact itself, the limits the SPEC states (decision 4).
- The single-maintainer constraint gets worse, not better. Rule H in `docs/PLAN-M17-M28.md`
  exists to stop a flight-test programme and a release programme running at once.

## Alternatives rejected

- **Ship only the repository (status quo).** Cheapest, and it makes the hardware goal
  unreachable by anyone but the author; it also leaves F3269 without the reference
  implementation the field lacks.
- **Ship only an SDK (D4).** An ABI with no conformance kit and no host packages is a header
  file with ambitions; it neither reaches hardware nor supports a claim.
- **Ship a vendor app first (D3).** Fastest route to a flying demo, and it couples the
  architecture claim to one company's board and one company's OS.
- **Pursue a DO-178C data package now (D7).** No applicant, no DAL, no funding; it would
  consume the project and produce evidence for a system that does not yet fly.
