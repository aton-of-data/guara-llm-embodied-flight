# Space operation — abort the running sequence

| | |
|---|---|
| Intent verb | `abort` (stop class) |
| Domain / host | Space · F´ v4.3.0 |
| Status | **specified**; depends on `Svc::FpySequencer`, which is pre-release upstream (GROUNDING D.4, risk RS-2) |

Stop what the spacecraft is doing without necessarily declaring an emergency. The space
counterpart of the air `abort`, and the operation that makes the gate real.

## 1. Abort versus safe mode

| | `abort` | `safe_mode` |
|---|---|---|
| Effect | Stops the running sequence; the vehicle keeps its current attitude and load set | Stops the sequence **and** commands the survivable attitude and sheds loads |
| Arbiter state | Leaves the complex function without entering the recovery function | Enters the recovery function, latched |
| Released by | A new validated sequence | An explicit ground command only (AC-43) |
| Ordering | Lower authority | Higher authority; wins when both match the same utterance |

Keeping them distinct matters: an abort that silently entered safe mode would cost a ground
pass to clear, and a safe-mode request that only stopped the sequence would leave a spacecraft
in an unsurvivable attitude. Both errors are one-line mappings away in a naive implementation.

## 2. The gate this operation depends on

Requirement 4 of the candidate monitor set (`SPACE-AUTONOMY.md` §5):

> No sequence shall command an actuator while the arbiter state is not `CF`.

That is the direct analogue of `GuaraCfGateway` and the requirement that makes the LLM thread
meaningful in orbit: the model may produce an intent, the compiler may produce a validated
sequence, and the arbiter can still stop the sequence from reaching an actuator. Never a token
stream near an actuator (risk RS-6).

## 3. What the upstream sequencer already gives, and what it does not

Gives (GROUNDING D.3): a state machine IDLE → VALIDATING → RUNNING that **validates a compiled
sequence before running it**, with waits, branching, telemetry and parameter access — the
trusted deterministic disposer of ADR 0010 rule 6, already written and unit-tested upstream.

Does not give: any notion of an arbiter, a verdict or a gate. It is also explicitly pre-release
and depends on IEEE-754 floats on the target (GROUNDING D.4), so the intent → sequence compiler
is kept independent of it and a hand-rolled executor must remain possible (RS-2).

## 4. What this operation must not claim

- Nothing here runs. The sequencer is upstream code read in a pinned clone; the gate is a
  requirement, not a component.
- Stopping a sequence is not stopping the spacecraft: torques already commanded keep acting
  until the control loop is given something else to do. That is the difference this document
  exists to preserve.

## 5. Open items

- M13: the arbiter gate as an FPP-modelled component, with the truth-table test of AC-40.
- M16: the intent → validated sequence compiler, and AC-50 (zero adversarial utterances that
  pass both sequencer validation and the gate).
