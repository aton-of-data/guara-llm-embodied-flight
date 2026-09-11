# ADR 0008 — Multilingual voice via pluggable language packs

- Status: Accepted (author decision, 2026-09-11); implementation M10
- Related: docs/research/LLM-EMBODIMENT.md §3.3, §5; ADR 0009

## Context

The author wants Portuguese and English from the start, and a simple add-on to add new languages.
Constraints from the research doc: stop/abort must not depend on the LLM (L-M2, L-M5); voice is an attack
surface (L-V3); open models are weaker outside English (L-M7).

## Decision

1. **Canonical core is language-neutral.** Mission intents, capability-pack schemas, compiler, RTA and logs use
   English identifiers and enums only. Languages exist only at the edges (ASR, LLM prompt, readback, TTS).
2. **A language = one folder** `locales/<BCP-47 tag>/` (e.g. `pt-BR`, `en`), no code changes:

   | File | Content | Safety-relevant |
   |---|---|---|
   | `pack.yaml` | tag, name, version, maintainers, fallback tag, ASR model id, TTS voice id | no |
   | `safety_grammar.yaml` | exact-match phrases → `abort` / `land_now` / `return_home` / `hold` (bypass LLM) | **yes** |
   | `readback.yaml` | message templates with named placeholders for every intent confirmation and every RTA event | yes (must be unambiguous) |
   | `lexicon.yaml` | domain terms → canonical enums (crops, sensors, field words, units) | no |
   | `prompts/system.md` | LLM system prompt for this language; output must be canonical intent JSON | no |
   | `eval/utterances.jsonl` | utterance → expected canonical intent | test |
   | `eval/adversarial.jsonl` | jailbreak / unsafe utterances → expected rejection | test |

3. **Admission gate** `scripts/check_locale_pack.py <tag>` must pass before a pack loads:
   schema valid; every safety intent has ≥ 1 phrase and no phrase collides with another intent or the lexicon;
   every intent enum and RTA event has a readback template with matching placeholders; eval files present;
   `safety_grammar.yaml` carries a human-review record (reviewer, date) — packs without it load in SITL only.
4. **Initial packs:** `en` and `pt-BR`, both maintained in-tree. Community packs follow the same gate.
5. **Runtime:** locale selected per operator session; unknown or failed pack → fallback tag; safety grammar of
   `en` is always active in addition to the session language.
6. Metrics RQ6a/RQ6b are reported per language pack.

## Consequences

- (+) Adding a language needs no change to compiler, RTA or ROS 2 packages.
- (+) Safety stop path is deterministic and reviewable per language.
- (−) Per-language eval sets and human review are real work; quality differs by language and model.
- (−) Always-on English safety grammar may false-trigger on English words inside other languages; measured in eval.
