# ADR 0013 — LLM evaluation protocol: cloud models as instruments, intent as the only output

- Status: Accepted (2026-09-11); implemented in M8–M9 (`docs/PLAN-M8-M16.md`)
- Related: ADR 0008 (language packs), ADR 0009 (capability packs), ADR 0010 (untrusted CF
  contract, rules 6 and 7); `docs/research/LLM-EMBODIMENT.md` §4, §5.2, §7; CLAUDE.md
  §Prohibitions ("results only from `results/` via script")

## Context

`LLM-EMBODIMENT.md` commits the deployment to offline-first, open-weight models on a ground
device (L-C2, §5.4), for a good reason: rural connectivity cannot be a dependency of a
flight operation. But the research questions RQ6a (intent accuracy) and RQ6b (unsafe-intent
rejection) are questions about *how bad the untrusted layer can be*, and answering them
needs strong models, several of them, in the same harness — not just the one model that fits
on the operator's laptop.

Two failure modes to avoid:

- **Instrument creep.** A cloud API used for evaluation quietly becomes a runtime
  dependency, and the offline-first claim silently dies.
- **Unreproducible results.** A language model is non-deterministic (L-M1). A number
  reported from one sampling of one model version is not a result, and no amount of
  averaging makes it one if the raw exchanges were not kept.

## Decision

1. **Two roles, never mixed.**
   - *Instrument*: a hosted model, reached over an API, used to generate Mission Intents
     for the evaluation corpus. Instruments measure the boundary; they never fly.
   - *Candidate*: an open-weight model that could actually run on the ground device in the
     deployment of §5.4. Only candidates appear in a deployment recommendation.

   Every reported number carries its model identifier and its role. An instrument result is
   an *upper bound on what a strong untrusted layer produces*, which is exactly what a
   safety boundary should be sized against; it is never evidence that the field system
   works.

2. **The LLM's only output is a Mission Intent.** Unchanged from ADR 0010 rule 6 and
   `LLM-EMBODIMENT.md` §5.2: a closed-vocabulary JSON document. The harness rejects
   anything else without interpretation. The model never sees a setpoint schema, a MAVLink
   verb, an F´ command name or an Fpy directive, because a model that cannot name an
   actuator cannot be prompted into commanding one.

3. **The provider is an interface, and `mock` is one of them.** The harness talks to a
   provider abstraction with one operation: prompt in, text out. Adding a provider must
   not touch the corpus, the compiler or the metrics. A deterministic `mock` provider is a
   first-class provider so that the whole pipeline — corpus, compilation, scoring,
   reporting — is testable in CI with no key, no network and no cost.

4. **Every exchange is recorded verbatim, before it is scored.** For each corpus case the
   run directory keeps the rendered prompt, its SHA-256, the raw response text, the model
   id, the wall-clock duration and the provider's own request identifiers. Scoring reads
   those files. A metric that cannot be recomputed from the recorded exchanges does not
   exist. This is the LLM-thread form of the rule that numbers come only from `results/`.

5. **Non-determinism is reported, not hidden.** Every model runs the corpus `R` times
   (`R ≥ 3`, default 3). Reported rates are accompanied by Wilson 95% intervals, as RQ1
   already requires, and by the per-repetition spread. A case whose outcome is not stable
   across repetitions is flagged as unstable in the report rather than averaged away.

6. **Safety-relevant commands are never routed through a model, and the corpus proves it.**
   `abort`, `land_now` and `return_home` are matched by a keyword grammar on the
   transcription and mapped directly to platform modes
   (`LLM-EMBODIMENT.md` §5.2). The corpus therefore contains stop utterances whose expected
   outcome is *handled without any model call*, and the harness records that no request was
   made for them.

7. **The credential lives in `.env` and never in the repository, the results or the
   prompts.** `.env` is git-ignored; the harness reads the key from the environment,
   records only the *name* of the environment variable it used, and fails closed with an
   explanatory message when the variable is absent. No key, model identifier or endpoint is
   written into `results/`. Run directories are publishable evidence.

8. **A rejection is a pass.** For an adversarial case the desired outcome is that the
   deterministic compiler refuses the plan, whatever the model produced. RQ6b counts
   *flyable unsafe plans*, and its target is zero; a model that produces a fluent, confident,
   out-of-envelope intent and is refused is the system working.

## Consequences

- (+) RQ6a/RQ6b can be answered now, with strong models, without weakening the offline-first
  deployment claim — the two roles keep it honest.
- (+) The whole pipeline is testable with no key and no network, so the evaluation harness
  itself is unit-tested rather than trusted.
- (+) Recorded exchanges make every reported rate recomputable, and make the adversarial
  corpus a reusable artifact for others.
- (−) Instrument results say nothing about the field system's accuracy; two sets of numbers
  must be maintained and explained, and the instrument set must never be quoted alone.
- (−) `R` repetitions × models × corpus size makes wall-clock time and cost the binding
  constraint on corpus size, and the first corpora will be small enough that the intervals
  are wide. A wide interval that is reported is acceptable; a narrow interval from one
  sampling is not.
