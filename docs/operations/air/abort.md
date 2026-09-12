# Air operation — abort

| | |
|---|---|
| Intent verb | `abort` (stop class) |
| Capability class | Safety operation — available whenever the aircraft is flying, in every capability pack |
| Domain / host | Air · PX4 v1.17 + ROS 2 Humble |
| Target platform mode | **Hold** (ADR 0008: the stop grammar maps to a platform mode, never to a model) |
| Status | Grammar **implemented** and measured for model-independence (AC-29 PASS); the mode mapping and the physical button are M10 |
| Evidence | `docs/evidence/20260912T114925Z_cursor-stop-r3_cursor-agent/` |

Stop the mission and hold position. The most important operation in the catalogue, and the one
built to work when everything else does not.

## 1. What the operator asks for

> "Abort." · "Stop everything." · "Cancel the mission."
> "Aborta." · "Para tudo." · "Cancela a missão."

## 2. Words to motion — the short path

```
transcription ──► stop grammar (exact phrase match) ──► platform mode
```

There is no model in that line, by design (ADR 0013 decision 6):

- The grammar runs **before** any model request. AC-29 measures exactly this: over the stop
  corpus at `R = 3`, 24 of 24 cases resolved by the grammar and **zero** API requests were made.
- A model that is slow, unreachable, wrong or jailbroken cannot delay or suppress the stop,
  because it is never asked.
- The grammar is deliberately over-triggering (`mission/compiler/stop_grammar.py`): phrase-level
  patterns, `abort` outranking `land_now` outranking `return_home`, so "land now, no, abort"
  aborts. A false stop costs a flight; a missed stop can cost an aircraft. The evaluation
  reports how many utterances were resolved this way instead of hiding them — including the
  adversarial case that merely *mentions* disabling the abort keyword and is stopped anyway.

## 3. Independence, stated precisely

| Failure | Does abort still work? |
|---|---|
| Model unreachable, slow or wrong | Yes — never consulted |
| Mission compiler rejects everything | Yes — different path |
| Guará arbiter dead | The pilot's RC and GCS mode changes are unaffected; Guará drops to `INACTIVE` on any pilot mode change (principle 7) |
| ASR mis-transcribes | **No.** The grammar sees what the ASR produced. This is why the physical button (M10) is part of the operation, not an accessory |

## 4. Evidence

```
$ ./scripts/dev.sh python3 scripts/llm/eval.py --provider cursor-agent \
    --model composer-2.5 --only-class stop --repeats 3 --tag cursor-stop-r3
$ ./scripts/dev.sh python3 scripts/check_ac.py AC-29 results/latest_llm
{"AC-29": {"stop_cases": 8, "model_requests_for_stop_cases": 0,
           "grammar_pass": {"point": 1.0, "low": 0.862024, "high": 1.0, "n": 24, "k": 24}}}
PASS AC-29
```

The interval is the result, not the point estimate.

## 5. What this operation must not claim

- **The end-to-end stop latency is not yet measured.** AC-34 (utterance end → recovery function
  active, with the model process killed) is M10. What is measured today is that the model is
  never in the path, not how long the path takes.
- The keyword → PX4 mode mapping is specified (ADR 0008) and not yet implemented as a runtime
  component; `scripts/sitl/ros_action.py set-nav-state` exercises the platform side in scenarios.
- Voice is not a safety case. An ASR failure is a stop failure, which is why abort is also a
  button.

## 6. Open items

- M10: the voice pipeline, the physical button, and AC-34's measured stop latency.
- Language packs beyond `en` and `pt-BR`, each gated by an admission check, with the English
  safety grammar always active (ADR 0008).
