# Example Mission Intents

Worked examples of the document an untrusted model is allowed to emit — the *only* thing it
may emit (ADR 0010 rule 6). They exist so the compiler can be exercised without a model, a
key or a network, and they are what the README's no-container path runs.

| File | What it demonstrates |
|---|---|
| `survey_north_3.json` | Inside the envelope: compiles to a flyable plan, every check passes |
| `survey_north_3_out_of_envelope.json` | The same intent at 40 cm/px: schema-valid, well-formed, and refused by `gsd_bounds`, `altitude_ceiling` and `energy` |

Both are validated against [`../schema/mission_intent.schema.json`](../schema/mission_intent.schema.json)
before the compiler sees them. `utterance_hash` binds an intent to the utterance it came from;
here it is the hash of the English nominal utterance `en-nom-01` in
[`../corpus/nominal.yaml`](../corpus/nominal.yaml).

```bash
python3 -m mission.compiler --intent mission/intents/survey_north_3.json
python3 -m mission.compiler --intent mission/intents/survey_north_3_out_of_envelope.json
```

A refusal is exit status 2 with the failed check names on stderr. Nothing here is a plan: the
compiler produces the plan, and only a plan whose every check passed is flyable.
