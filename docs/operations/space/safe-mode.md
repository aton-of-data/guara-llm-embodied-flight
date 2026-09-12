# Space operation — enter safe mode

| | |
|---|---|
| Intent verb | `safe_mode` (stop class) |
| Domain / host | Space · F´ v4.3.0 |
| Role | **The recovery function of the space profile** — the F´ analogue of PX4's Hold/RTL/Land |
| Status | **specified only.** F´ ships no safe mode, and neither does this repository (GROUNDING D.5, risk RS-1) |
| Acceptance criteria | AC-42 (entry effects, bounded cycles), AC-43 (latched), AC-44 (idempotent) — M14 |

The single largest difference between the two domains, and the one a reviewer should attack
first.

## 1. Why this document exists before the code

On PX4 the recovery function was **free**: Hold, RTL and Land are assured, pre-existing,
pilot-familiar modes, and Guará's contribution is only the switching logic (ADR 0001). A grep
for `safe.?mode` over `Svc/` and `Fw/` in the pinned F´ clone returns nothing (GROUNDING D.5).
F´ gives FATAL, `Svc::Health` and a watchdog — detection, not recovery.

So on F´ the project has to supply **both halves**, and the recovery half is new
safety-critical code with no heritage. Claiming the F´ thread without saying that would be the
project's worst overclaim, which is why it is stated in ADR 0011, in ADR 0012, in
`SPACE-AUTONOMY.md` §2.2 and here.

## 2. What v1 safe mode is specified to do

On entry (ADR 0012 decision 2):

1. Stop the running sequence.
2. Command a declared survivable attitude — sun-pointing.
3. Shed the declared non-essential load set.
4. Hold, and wait for the ground.

Its properties become FRETish requirements and its monitors are Ogma-generated, like every
other requirement in the project: the recovery function is specified with the same machinery it
protects.

## 3. Latched by design

There is **no automatic return to the complex function in the space profile**. Release requires
an explicit ground command (ADR 0012 decision 3, AC-43). The reasons are operational, not
technical: nobody is watching inside the light-time delay, and safe mode is a declared state a
ground team is expected to clear deliberately.

The decision core already latches (P-4, AC-13). The space profile configures `T5` off; it does
not add logic. That is the claim AC-39/AC-40 protect — one core, two policies.

## 4. How it is reached

| Path | Trigger |
|---|---|
| Operator | The `safe_mode` verb, resolved by the stop grammar with no model request |
| Arbiter | Any space channel predicting violation inside its threshold: `attitude_keepout`, `power_margin`, `momentum`, `inputs_valid`, `requirements` |
| Platform | `Svc::Health` ping timeout → FATAL, the F´ analogue of FM-4/FM-5 (AC-41) |

## 5. What this operation must not claim

- **It does not exist.** No code, no test, no run. Every space claim in this repository inherits
  that, and no milestone may report otherwise (`PLAN-M8-M16.md` §5, thread B).
- A sun-pointing attitude is survivable for a *declared* vehicle model; it is not a universal
  safe attitude.
- Entry is specified as bounded in cycles (AC-42), which is a requirement, not a measurement.

## 6. Open items

- M14 in full: FRETish requirements, the component, AC-42/43/44.
- Whether safe-mode entry can itself violate a keep-out constraint — the simultaneous
  constraint-satisfaction problem of the attitude-manoeuvring RTA literature
  (`SPACE-AUTONOMY.md` §5). Until answered, the recovery manoeuvre is not proven safe.
