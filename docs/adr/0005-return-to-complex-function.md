# ADR 0005 — Return-to-complex-function policy

- Status: Proposed (P1, 2026-09-11)
- Related: SPEC §3.4-§3.5 (T3-T7, P-3, P-4); AC-12, AC-13

## Context

Returning to the CF after a recovery increases availability, but risks
chattering (repeated CF→RF→CF) and re-entering a still-dangerous situation.
Constraints:

- Returning to the CF means the executor schedules its own owned mode, which keeps
  the executor in charge [G 1.7, A.3].
- Any mode switch by the pilot/GCS removes the executor from charge [G 1.6].
- The `scheduleMode` callback fires when the mode publishes `ModeCompleted`
  or when the executor is deactivated [G 1.3]. Which internal modes publish
  `ModeCompleted` (Hold in particular) was not verified: [UNKNOWN];
  the policy does not depend on it.

## Options

A. Never return (RF is terminal).
B. Return as soon as `¬U`.
C. Return with hysteresis `h`, dwell `T_d` and a switch limit (`N_max` in `W`).
D. Return only with operator confirmation.

## Decision

**C** for RF = HOLD; **A** for RTL and LAND.

1. Return (T5) only from `RF(HOLD)`, when `C(k)` has been true
   continuously for `T_d` and `t_k − t_sw ≥ T_d`.
2. From `RF(RTL)` or `RF(LAND)` there is no automatic return: those actions indicate
   a severe cause (configured monitor or escalation).
3. `N_max` CF→RF switches within `W` ⇒ `LATCHED` (no return until `¬IC`).
4. Escalation (T6/T7) only increases `rank` (`HOLD < RTL < LAND`), never decreases it.
5. Persistence escalation: `RF(HOLD)` with `U` true for more than
   `T_esc` = 30 s [HYPOTHESIS] ⇒ `select` returns LAND. **Disabled
   by default** in v1 (`escalation_enabled=false`) until M6 measures its effect.
6. `return_enabled` is a scenario parameter; P4 compares policies A and C with the same seeds.
7. On return, the CF receives a resume event; the gateway only releases setpoints
   with a timestamp later than `t_return` (avoids accumulated stale setpoints).

## Consequences

- (+) Chattering bounded by construction (P-4), verifiable in unit tests (AC-13).
- (+) Distinguishes transient interruptions (passing traffic) from severe causes.
- (−) `T_d` and `h` increase time outside the CF; effect measured as mission completion rate (P4).
- (−) Re-entry after `T_d` may still meet risk the predictor does not model (SPEC §7).
- Parameters `h`, `T_d`, `N_max`, `W`, `T_esc`: all [HYPOTHESIS], tuned only with data from `results/`.
- Option D (operator confirmation) becomes relevant for the voice interface
  (`docs/research/LLM-EMBODIMENT.md`): a spoken "resume" is a user intent, not a safety signal,
  and must still satisfy T5.
