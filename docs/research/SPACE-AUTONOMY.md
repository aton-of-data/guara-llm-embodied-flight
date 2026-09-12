# F´ and satellite autonomy — where a Guará-class RTA fits

Status: research draft (2026-09-11). Not a SPEC. Nothing here is a Guará result;
external numbers and claims are attributed and carry a verification status.
Facts marked **[SRC]** were read in the pinned clone under `third_party/`
(`third_party/VERSIONS.md`); facts marked **[WEB]** come from a primary or
publisher page; **[REVIEW]** needs normative or legal interpretation;
**[UNKNOWN]** has no evidence yet.

Companion documents: `docs/research/LLM-EMBODIMENT.md` (the air/agriculture
thread), `docs/SPEC.md` (the PX4 RTA), `docs/PLAN-M8-M16.md` (the executable
plan that follows from this investigation).

---

## 1. Why a second platform at all

Guará's claim is architectural, not platform-specific: *an untrusted complex
function is bounded by a formally specified, measured runtime-assurance
boundary, and the recovery function is the platform's own assured mode.* On PX4
that boundary is a `ModeExecutor` and the recovery function is Hold/RTL/Land
(ADR 0001).

Three independent reasons to instantiate the same architecture on F´:

1. **The generator already targets it.** Ogma ships four backends — cFS, ROS 2,
   F´ and standalone — and no PX4 backend **[SRC]**
   `ogma@69485b3:ogma-core/src/Command/{CFSApp,ROSApp,FPrimeApp,Standalone}.hs`.
   Guará's upstream contribution C2 adds PX4. The F´ backend exists but is
   incomplete in ways that matter for RTA (§4.2), which is a second, smaller
   upstream opening in the same repository.
2. **It answers the strongest reviewer objection.** SPEC §7.7: the arbiter runs
   on a companion computer, outside the autopilot, with measured rather than
   bounded latency. F´ is a flight software framework with real heritage
   **[WEB]** (ISS-RapidScat 2014, ASTERIA 2017, Ingenuity 2021 — JPL/NASA), so
   the *same decision core* can be placed inside the flight application instead
   of beside it. That converts "not high-assurance" (PROPOSAL §9) from a
   permanent limitation into a phase.
3. **It is where the LLM-embodiment argument is unavoidable.** In the air the
   operator can take the stick; in orbit a one-way light time of seconds to tens
   of minutes means nobody can. Every LLM-for-spacecraft paper found (§3) ends
   at "human in the loop" or "prompt engineering", which is precisely the
   mitigation that orbit removes. An RTA boundary is not an improvement there,
   it is the only remaining option.

---

## 2. What F´ actually gives us, read in the pinned clone

F´ `v4.3.0`, commit `7d8f579`, 2026-08-19, Apache-2.0 **[SRC]**
(`third_party/fprime/LICENSE.txt`). Apache-2.0 means F´ imposes no isolation
requirement of the kind ADR 0003 imposes on DAIDALUS.

### 2.1 Components relevant to an F3269 mapping

| F´ element | What it is **[SRC]** | RTA role it can fill |
|---|---|---|
| `Svc::Health` | Pings each active component on a table; tracks timeout cycles; issues a **FATAL** event on no reply; strokes a watchdog port only while all replies are inside their limit (`Svc/Health/docs/sdd.md`, HTH-001..007) | The F´ analogue of the PX4 arming-check timeout chain (FM-1/FM-4/FM-5). A hung arbiter is *detectable by the platform*, which PX4 only achieves indirectly |
| `Svc::FatalHandler`, `Svc::AssertFatalAdapter` | FATAL routing and assert adaptation | Where a failed decision core must land |
| `Svc::WatchDog`, `Svc::LinuxTimer`, `Svc::ActiveRateGroup`, `Svc::RateGroupDriver` | Deterministic rate groups driven by a timer, plus hardware watchdog stroking | The fixed-period `T_s` tick of `DecisionCore` maps onto a rate group instead of a ROS 2 timer — a stronger statement about periodicity than SPEC §3.2 can make today |
| `Svc::FpySequencer` | Loads, validates and runs **one** compiled Fpy sequence at a time; state machine IDLE → VALIDATING → RUNNING with breakpoints, `WAIT_REL`/`WAIT_ABS`, `GOTO`, `EXIT`, `EXIT_WITH_ERROR`, telemetry and parameter access, subroutines; runs binaries produced by `fprime-fpyc` in `fprime-gds`. Marked "currently in development, use at own risk" (`Svc/FpySequencer/docs/sdd.md`, FPY-SEQ-001..021) | **The trusted deterministic disposer of ADR 0010 rule 6, already written.** An LLM must never emit commands; it may emit an intent that a compiler turns into a *validated* sequence. F´ already has the validated-sequence half |
| `Svc::CmdDispatcher`, `Svc::CmdSplitter`, `Svc::Seq`, `Svc::SeqDispatcher` | Command dispatch and sequencing plumbing | The choke point where an arbiter can gate commands, the analogue of `GuaraCfGateway` |
| `Svc::PrmDb` | Parameter database | `config/rta_params.yaml` equivalent, with uplinkable parameters |
| `Fpp` / FPP modelling + autocoding | Components, ports and topologies are modelled and autocoded | Makes the arbiter's interface a model artifact, reviewable like the FRETish requirements are |

### 2.2 What F´ does **not** give us

- **There is no safe mode.** `grep -ril "safe.?mode" Svc Fw` over the pinned
  clone returns nothing **[SRC]**. F´ has FATAL, Health, and a watchdog; it has
  no component that means "stop doing the mission and hold the vehicle in a
  survivable configuration". On PX4 the recovery function was *free* — Hold,
  RTL and Land are assured, pre-existing, pilot-familiar modes (ADR 0001). On
  F´ the recovery function has to be **written**, and it becomes the most
  safety-critical new code in the project.
- **There is no dynamics model and no notion of a keep-out volume.** The
  geofence predictor (ADR 0004) and DAIDALUS (ADR 0003) have no F´ counterpart;
  the constraints of the space domain are different objects entirely (§5).
- **`FpySequencer` is explicitly pre-release** and depends on IEEE-754 floats
  and two's-complement integers on the target **[SRC]**. Anything built on it
  inherits that status.
- **No operating-system-level isolation claim.** F´ runs on Linux, VxWorks,
  bare metal via `Os/`; the assurance argument is per-deployment, not inherited.

### 2.3 The consequence for the architecture

On PX4, Guará's contribution is the *switching logic*, because the recovery
function was already assured. On F´, the same project has to supply **both**
halves — arbiter and recovery mode — and the recovery mode is the part a
reviewer will attack. This is the single largest scope difference between the
air and space threads, and the plan (`docs/PLAN-M8-M16.md`) treats the F´
recovery-mode component as its own milestone with its own acceptance criteria
rather than as an afterthought of the port.

---

## 3. Prior art: LLMs commanding spacecraft

| Work | What it does | Safety basis | Status |
|---|---|---|---|
| LLMSat (2024) | LLM as high-level goal-oriented spacecraft controller; systems-engineering design, simulated environment, open repository | Prompt design and human review | **[WEB]** [arXiv 2405.01392](https://arxiv.org/abs/2405.01392), [repo](https://github.com/DM1122/LLMSat) |
| LLMs as autonomous spacecraft operators in Kerbal Space Program (2025) | Pure-LLM agent for the KSP Differential Games challenge; prompt engineering, few-shot, fine-tuning | None beyond the simulator | **[WEB]** [arXiv 2505.19896](https://arxiv.org/pdf/2505.19896), [Acta Astronautica](https://www.sciencedirect.com/science/article/abs/pii/S0273117725006465) |
| GUIDE (CVPR 2026 AI4Space workshop) | Lightweight acting model in real time, offline reflection updating decisions; adversarial orbital interception in KSPDG | None stated | **[WEB]** [arXiv 2603.27306](https://arxiv.org/html/2603.27306) |
| AstroMind (2026) | Benchmark for spacecraft *behaviour reasoning*: inferring the intent of other, possibly non-cooperative, agents | Benchmark, not a control path | **[WEB]** [arXiv 2605.24573](https://arxiv.org/html/2605.24573v1) |

The pattern from `LLM-EMBODIMENT.md` §2 repeats exactly: the safety story is
prompt engineering, tool restriction, or a human. Two things change in orbit and
both cut the same way — the human is behind a light-time delay and a ground-station
pass, and the vehicle cannot be landed. So the mitigation everyone relies on is
the one mitigation that is unavailable.

**Positioning claim, still [REVIEW] until the systematic search in P6:** no work
was found that places an LLM-driven spacecraft agent behind a formally specified
runtime-assurance boundary implemented in a flight-heritage flight software
framework, with monitors generated from formal requirements and measured
switching latency.

### 3.1 The adjacent literature that already did the hard part

Spacecraft RTA exists, but as control theory in research code, not as flight
software:

- **Safety filtering / ASIF.** Active Set Invariance Filtering builds an RTA
  filter from control barrier functions, minimally deviating from the primary
  controller while enforcing constraints; it is system-agnostic and provably
  correct for its constraint class **[WEB]**
  ([arXiv 2110.03506](https://arxiv.org/pdf/2110.03506),
  [arXiv 2209.01120](https://arxiv.org/pdf/2209.01120)).
- **Spacecraft applications.** Docking, inspection, and simultaneous constraint
  satisfaction during attitude manoeuvring are all published with RTA
  formulations **[WEB]** ([arXiv 2402.14723](https://arxiv.org/abs/2402.14723),
  Run Time Assurance for Autonomous Spacecraft Inspection).
- **Open implementation.** `act3-ace/run-time-assurance` provides Explicit and
  Implicit Simplex and Explicit and Implicit ASIF as Python modules requiring
  the user's constraints and state-transition model **[WEB]**
  ([repo](https://github.com/act3-ace/run-time-assurance)).
- **Assurance-argument work.** Applying assurance arguments to RTA
  **[WEB]** ([arXiv 2303.15568](https://arxiv.org/pdf/2303.15568)); the Safe
  Trusted Autonomy for Responsible Space programme frames the problem area
  **[WEB]** ([arXiv 2501.05984](https://arxiv.org/html/2501.05984v1)).
- **RTA on a robotics middleware.** SOTER on ROS is the closest architectural
  cousin **[WEB]** ([arXiv 2008.09707](https://arxiv.org/pdf/2008.09707)).

**The gap this repository is positioned to close.** The control-theory side has
provably-correct filters with no flight software; the flight software side (F´)
has heritage, health monitoring and a validated sequencer with no safety filter
and no safe mode; the formal-methods side (FRET → Ogma → Copilot) has verified
monitors and an F´ backend that only raises events (§4.2). Nobody has connected
the three. Connecting them is a small amount of new code sitting on three
prestigious, actively maintained code bases — which is exactly the shape of
contribution PROPOSAL §8 argues for.

---

## 4. Ogma on F´: the concrete upstream openings

### 4.1 The variable database is empty

`ogma@69485b3:ogma-core/data/variable-db.json` contains `inputs: []`,
`topics: []`, and a `types` list whose only framework-scoped entries map
`fprime/port` F´ primitive types (`U8`…`I64`, floats) to C types **[SRC]**.

So Ogma can *type* an F´ port but ships no knowledge of any actual telemetry
channel or port to monitor — for F´ or for PX4. Guará's planned contribution C2
(a `px4_msgs` variable DB) has a sibling: **a variable DB for the F´ telemetry
channels of a reference deployment**, which is the same kind of data file, in
the same format, in the same repository.

### 4.2 The generated F´ monitor cannot trigger anything

`ogma-core/templates/fprime/Copilot.fpp` generates a `queued component Copilot`
inside `module Ref`, with one `async input port <var>In` per monitored variable
and one **event** per monitor violation **[SRC]**.

Two limitations follow directly from the template text:

1. **Events only.** A violation becomes an F´ event (and telemetry). There is no
   output port carrying a verdict that another component could act on. This is
   `PROPOSAL.md` G3/G4 restated in the space domain: the monitor warns, nothing
   switches. Guará's `MonitorVerdict` message (class, action, `inputs_complete`,
   timestamp) is exactly the missing artifact, and it is a small, reviewable
   addition: one port type plus template lines.
2. **Hardcoded namespace.** The component is emitted into `module Ref`, the F´
   reference deployment, so the generated code is not directly usable in a
   project topology without editing. A configurable module name is a
   self-contained upstream patch.

Both are candidate PRs of the same size and character as C2, and both are
prerequisites for the F´ arbiter to consume generated monitors instead of
hand-written ones. They belong to the same milestone as the port (P7b in the
plan).

---

## 5. The space domain does not reuse the air monitors

This is where an honest plan has to refuse the easy claim. `T_gf` and `T_daa`
are not portable; the *shape* of the signal is (time-to-violation of a
predicted constraint), the content is not.

| Air signal (SPEC §3.1) | Orbital analogue | Why it is not a port but a rewrite |
|---|---|---|
| `T_gf` — time to geofence violation from linear extrapolation plus a braking model (ADR 0004) | Time to violation of an **attitude keep-out cone** (sun/star-tracker/instrument boresight) or of a **position keep-out volume** (proximity operations) | There is no braking model: an orbiting body cannot stop. "Recovery" costs Δv or reaction-wheel momentum, and the recovery *itself* must respect the same constraints (the simultaneous-constraint problem of [arXiv 2402.14723]) |
| `T_daa` — time to loss of well-clear from DAIDALUS (DO-365) | Time to closest approach / probability of collision against a conjunction screening volume | DO-365 well-clear volumes are an air-traffic construct. Conjunction assessment is probabilistic, screened on ground with days of lead time, and the manoeuvre decision is an operational process, not a 30-second reflex **[REVIEW]** |
| `V(k)` — stale or invalid inputs | Same in kind, harsher in degree: eclipse, single-event upsets, sensor blinding, loss of attitude knowledge | The freshness logic and ADR 0010's trusted-time rule port almost unchanged. This is the one signal that transfers directly |
| `M(k)` — Copilot monitors of formal requirements | Same, with different requirements: power margin, battery depth of discharge, thermal limits, momentum saturation, downlink obligations, propellant budget | The toolchain ports (FRET → Ogma → Copilot → F´). Only the FRETish requirements change |
| Recovery function = Hold / RTL / Land | Recovery function = **safe mode**: point to sun, stop the mission sequence, shed loads, wait for ground | Does not exist in F´ (§2.2). Must be specified and written |

**Candidate first monitor set for the space thread** (each one a FRETish
requirement, all values **[PARAMETER TBD]**):

1. **Attitude keep-out.** The instrument boresight shall not come within
   `θ_min` of the sun vector; predicted violation time from current body rates.
2. **Power margin.** State of charge shall not be predicted to fall below
   `soc_min` before the next illuminated period, given the commanded load set.
3. **Momentum.** Reaction-wheel momentum shall not be predicted to saturate
   within the sequence's horizon.
4. **Sequencer liveness and authority.** No sequence shall command an actuator
   while the arbiter state is not `CF` — the direct analogue of the gateway, and
   the requirement that makes the LLM thread meaningful.

Monitor 1 is the natural first one: it is geometric, has an exact analytic
predictor testable the way AC-8 tests the geofence predictor, and it is a real
mission-loss mechanism (a pointing error that puts the sun in a star tracker or
an instrument aperture).

---

## 6. Where the simulation comes from

The air thread has PX4 SITL, which gives a real flight stack, a real controller
and a real log. The space thread needs the same standard of evidence — a
reproducible headless run, a seed, pinned commits, a log — and an F´ deployment
alone provides none of the physics.

| Option | What it is | Fit | Status |
|---|---|---|---|
| **Basilisk** | Astrodynamics simulation framework, C/C++ modules scripted from Python, faster-than-real-time and Monte-Carlo, with real-time/HIL options **[WEB]** ([docs](https://avslab.github.io/basilisk/)) | Best fit for attitude/power/momentum constraint monitors and for Monte-Carlo encounter batches, which is what RQ1/RQ2 need | Preferred candidate |
| **Basilisk ↔ ROS 2 bridge** | Published bidirectional bridge for real-time spacecraft control **[WEB]** ([arXiv 2512.09833](https://arxiv.org/html/2512.09833)) | Would let the *existing* ROS 2 arbiter be exercised against orbital dynamics before any F´ code exists — the cheapest possible first experiment | Evaluate first; a port of the decision core is not needed to get the first data point |
| **NOS3 / 42** | NASA Operational Simulator for Small Satellites; bundles the 42 attitude/orbit dynamics and visualisation tool, with cFS flight software and NOS Engine **[WEB]** ([manual](http://stf1.com/NOS3Website/docs/NOS3_CombinedDocumentation.pdf)) | Closest to an operational small-sat testbed, and cFS-oriented, which suits Ogma's cFS backend rather than its F´ one | Secondary |
| F´ `Ref` deployment alone | The reference topology, no dynamics | Useful only for interface and latency tests | Complementary |

Decision recorded in ADR 0012; the first experiment is deliberately the cheapest
one (Basilisk + the existing ROS 2 decision core), so that the expensive F´ port
is undertaken only after the constraint monitors have been shown to work against
real orbital dynamics.

---

## 7. Assurance context: F3269 does not obviously apply

SPEC §7.1 already says Guará is not certification. For the space thread the
framing has to change further:

- ASTM F3269 is an aviation standard for bounding unassured functions
  (PROPOSAL G5). Its applicability to a spacecraft is **[REVIEW]** and probably
  best treated as *architectural vocabulary* rather than a compliance target.
- The relevant regimes are NASA NPR 7150.2 software classes and ECSS for
  European missions **[REVIEW]**; neither has been read for this project.
- What does transfer, and is worth stating plainly, is the *evidence chain*
  PROPOSAL §5 already relies on: a correctness proof for the generated monitor
  C (CopilotVerifier), evidence of bounded time and memory, and evidence of
  absence of crashes — the justification NASA Langley used for flying Copilot
  monitors **[WEB]**.

So the space-thread claim is narrower and more defensible: *the same
architecture, the same monitor-generation chain, the same measured-latency
discipline, hosted in a flight software framework with heritage* — not
compliance with anything.

---

## 8. Risks specific to this thread

| # | Risk | Impact | Where resolved |
|---|---|---|---|
| RS-1 | The recovery function has to be written from scratch (§2.2); it is new safety-critical code with no heritage | The strongest reviewer objection moves from "arbiter is on a companion" to "your safe mode is unverified" | Own milestone, own ACs, FRETish requirements for the safe mode itself |
| RS-2 | `Svc::FpySequencer` is pre-release **[SRC]** | The trusted disposer is unstable ground | Pin the commit; keep the intent→sequence compiler independent of the sequencer so a hand-rolled executor can replace it |
| RS-3 | Effort duplication: two platforms, one 12-week plan already committed | Dilutes the PX4 results that the preprint depends on | The plan sequences space work strictly after M7/P4; the first space experiment reuses the ROS 2 core (§6) |
| RS-4 | Orbital constraint monitors need a dynamics model whose fidelity bounds every claim | Numbers that do not mean anything | Analytic test cases first (AC-8 pattern), Basilisk second, no claim without both |
| RS-5 | Conjunction assessment is an operational, ground-based, probabilistic process **[REVIEW]** | A "DAA for satellites" claim would be overreach | Do not claim it; scope the space thread to attitude/power/momentum and proximity keep-out |
| RS-6 | An LLM in a space thread invites the worst kind of demo (a chatbot "flying" a satellite) | Reputational, and contrary to ADR 0010 rule 6 | The LLM emits intent; the compiler emits a validated sequence; the sequencer executes it; the arbiter can stop it. Never a token stream near an actuator |

---

## 9. Sources

F´ and Ogma facts marked **[SRC]** are from the pinned clones listed in
`third_party/VERSIONS.md` (`fprime@7d8f579`, `ogma@69485b3`) at the paths quoted
inline.

- F´ framework and heritage: [fprime.jpl.nasa.gov](https://fprime.jpl.nasa.gov/),
  [NASA/JPL on Ingenuity's flight software](https://www.jpl.nasa.gov/news/meet-the-open-source-software-powering-nasas-ingenuity-mars-helicopter/),
  [NASA release](https://www.nasa.gov/missions/meet-the-open-source-software-powering-nasas-ingenuity-mars-helicopter/)
- RTA / safety filtering: [Run Time Assurance for Safety-Critical Systems (arXiv 2110.03506)](https://arxiv.org/pdf/2110.03506),
  [Universal framework for generalized RTA (arXiv 2209.01120)](https://arxiv.org/pdf/2209.01120),
  [RTA for simultaneous constraint satisfaction during attitude manoeuvring (arXiv 2402.14723)](https://arxiv.org/abs/2402.14723),
  [Assurance arguments for RTA (arXiv 2303.15568)](https://arxiv.org/pdf/2303.15568),
  [Safe Trusted Autonomy for Responsible Space (arXiv 2501.05984)](https://arxiv.org/html/2501.05984v1),
  [act3-ace/run-time-assurance](https://github.com/act3-ace/run-time-assurance),
  [SOTER on ROS (arXiv 2008.09707)](https://arxiv.org/pdf/2008.09707)
- LLM spacecraft agents: [LLMSat (arXiv 2405.01392)](https://arxiv.org/abs/2405.01392),
  [LLMSat repo](https://github.com/DM1122/LLMSat),
  [LLMs as autonomous spacecraft operators in KSP (arXiv 2505.19896)](https://arxiv.org/pdf/2505.19896),
  [GUIDE (arXiv 2603.27306)](https://arxiv.org/html/2603.27306),
  [AstroMind (arXiv 2605.24573)](https://arxiv.org/html/2605.24573v1)
- Simulators: [Basilisk](https://avslab.github.io/basilisk/),
  [Basilisk ↔ ROS 2 bridge (arXiv 2512.09833)](https://arxiv.org/html/2512.09833),
  [NOS3 user manual](http://stf1.com/NOS3Website/docs/NOS3_CombinedDocumentation.pdf)
