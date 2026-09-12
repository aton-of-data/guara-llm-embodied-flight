# Operations catalogue

Every flight operation Guará can be asked to perform, one document each, with the same
five questions answered in the same order: **who asks, what turns the words into motion,
what refuses it, what watches it in flight, and what evidence exists**.

This directory is the scope map of the project. If an operation is not listed here, it is
out of scope; if it is listed as *specified*, no run supports it yet.

---

## 1. Scopes

Guará is one architecture (ASTM F3269 roles, `docs/SPEC.md` §2) instantiated in two domains,
on two hosts, with two recovery functions. The threads are the ones in
[`docs/PLAN-M8-M16.md`](../PLAN-M8-M16.md).

| Scope | Domain | Host | Recovery function | Thread | Maturity |
|---|---|---|---|---|---|
| **Air** | Civil multirotor, VLOS, agriculture first | PX4 v1.17 + ROS 2 Humble, arbiter as `ModeExecutor` (ADR 0001) | PX4 internal modes Hold / RTL / Land — assured, pre-existing | A (M8–M12) | SITL research prototype, latency measured (§6 of the README) |
| **Space** | Small satellite, attitude-constrained operations | F´ v4.3.0, arbiter as an FPP component on a rate group (ADR 0011) | **Safe mode — does not exist in F´ and must be written** (ADR 0012 decision 2, risk RS-1) | B (M13–M15), C (M13c, M16) | Specified; analytic keep-out predictor and closed intent schema implemented |

The decision core is the shared artifact, not a fork: AC-39 and AC-40 require the two hosts to
produce identical decisions for identical input vectors. A behavioural difference between them
is a defect, not a variant.

## 2. The path every operation takes

No operation gets a shorter path to an actuator than this one (Rule T,
[`docs/PLAN-M8-M16.md`](../PLAN-M8-M16.md) §1):

```
utterance ──► stop grammar (exact match, no model)  ──────────────► platform mode
     │
     └─► model ──► Mission/Space Intent (closed schema, untrusted)
                        │
                        ▼
              deterministic compiler ──► plan or validated sequence (trusted)
                        │
                        ▼
              trusted executor ──► gateway ──► RTA switching core ──► platform
```

Three rules follow, and every operation document restates them in its own terms:

1. **The model never emits setpoints, commands, code or actuator names.** It emits an intent
   over a closed vocabulary (ADR 0010 rule 6, ADR 0013 decision 2).
2. **The stop class never passes through the model** (ADR 0008, AC-29).
3. **The compiler checks the plan; the RTA watches the flight.** Two independent layers
   (ADR 0004's "same file, hashed" rule applied to the whole pipeline).

## 3. Air operations (PX4 + ROS 2)

Capability class per ADR 0009: **S** sense · **D** dispense · **T** transport · **C** cooperate.
Only class S is loadable today; D, T and C refuse to load until their monitors exist (ADR 0009
decision 3).

| Operation | Intent verb | Class | Status | Document |
|---|---|---|---|---|
| Survey a field | `survey` | S | Compiled and flown as the CF in SITL (AC-24..AC-26, AC-31) | [air/survey.md](air/survey.md) |
| Inspect a point | `inspect_point` | S | Compiled; flown only through the same executor as `survey` | [air/inspect-point.md](air/inspect-point.md) |
| Return home | `return_home` | safety | Grammar implemented; mode mapping is M10 | [air/return-home.md](air/return-home.md) |
| Land now | `land_now` | safety | Grammar implemented; mode mapping is M10 | [air/land-now.md](air/land-now.md) |
| Abort | `abort` | safety | Grammar implemented; mode mapping is M10 | [air/abort.md](air/abort.md) |
| Status | `status` | read-only | Answer path specified (M10/M11) | [air/status.md](air/status.md) |

Dispense, transport and cooperate operations are deliberately absent: their documents are
written when their monitors are, not before.

## 4. Space operations (F´)

| Operation | Intent verb | Status | Document |
|---|---|---|---|
| Slew a boresight to a target | `slew` | Schema closed; analytic keep-out predictor (AC-47 PASS); no host, no dynamics | [space/slew.md](space/slew.md) |
| Hold a pointing attitude | `point_hold` | Schema closed; monitors specified | [space/point-hold.md](space/point-hold.md) |
| Enter safe mode | `safe_mode` | Specified only — the component does not exist in F´ or here (RS-1) | [space/safe-mode.md](space/safe-mode.md) |
| Abort the running sequence | `abort` | Specified; depends on `Svc::FpySequencer` (pre-release, RS-2) | [space/abort.md](space/abort.md) |
| Status | `status` | Specified | [space/status.md](space/status.md) |

There is **no detect-and-avoid operation in space**, and there will not be one from a DAIDALUS
port: conjunction assessment is a ground-based probabilistic process, not a reflex
(ADR 0012 decision 1, risk RS-5).

## 5. Status legend

| Label | Means |
|---|---|
| **flown** | Executed in SITL with a recorded run under `results/` and published evidence |
| **implemented** | Code exists and its unit ACs pass; no flight evidence |
| **specified** | Documented with acceptance criteria; no code |
| **gated** | Refused at load time until its monitors and preconditions exist (ADR 0009 decision 3) |

## 6. What no operation document may claim

Carried from `docs/SPEC.md` §7 and `docs/PLAN-M8-M16.md` §5, and repeated in each document:

- Nothing here is certification, or compliance with F3269, DO-365, RBAC 100, NPR 7150.2 or ECSS.
- SITL is not flight. No number in this directory is a claim about a real aircraft or spacecraft.
- The boundary bounds *physical* consequences covered by a monitor. A mission-level mistake
  inside the safe envelope — wrong field, wrong target, wrong photograph — is undetected.
