# Guará — Project proposal

Status: founding document (author's original proposal, translated to English on
2026-09-11). Engineering truth lives in `docs/SPEC.md`, `docs/adr/` and
`GROUNDING.md`; where they differ, those files win. Every external claim below
has a verification status in §11.

## 1. Summary

Guará is an open runtime assurance (RTA) kit, aligned with ASTM F3269, for PX4 via ROS 2.
It has four parts:

- Requirements written in structured language become verifiable C99 monitors (FRET → Ogma → Copilot).
- Traffic detect-and-avoid uses the DO-365 reference implementation (DAIDALUS).
- A predictor computes the time until geofence violation.
- An arbiter switches from the complex function (e.g. an LLM planner) to PX4's internal recovery modes.

12-week deliverables: repository, upstream PR to nasa/ogma, reproducible benchmark, preprint, NFM 2027 submission.

Long-term direction: voice-driven, open-weight LLM operation of civil drones
(agriculture first), with Guará as the safety boundary. See `docs/research/LLM-EMBODIMENT.md`.

## 2. Evidence of the gap

**G1. NASA's safe-drone stack stopped at an older architecture.**
- ICAROUS integrates DAIDALUS (detect and avoid) and PolyCARP (geofence) as cFS applications.
- It runs on an auxiliary onboard computer and depends on an external autopilot for control.
- Its latest release (V-2.2.6) is from January 2022.
- DAIDALUS is at v2.0.4, from November 2023.

**G2. Ogma has no PX4 target.** It generates monitors for cFS, ROS 2, F´ and standalone mode.
PX4's uXRCE-DDS bridge already exposes internal (uORB) messages as ROS 2 messages. The
missing piece is small and upstream-acceptable: a variable DB for `px4_msgs` and a template.
Ogma having switched from NOSA to Apache helps.

**G3. PX4 fallback does not look at safety properties.**
- External-mode fallback only fires if the mode dies, detected by arming-check timeout. The PR
  itself suggests extending it later to setpoint timeouts.
- That interface has been considered experimental since v1.15.
- Nothing switches modes because a safety property is about to be violated.

**G4. The literature points at exactly this step.**
- In the Volocopter/DLR work (CAV 2024), the authors note monitoring tools leave integration to the user,
  and conclude the next step is triggering automatic contingencies from the monitor instead of only warning the pilot.
- Platum (April 2026) monitors the MAVLink mission protocol at the ground/drone boundary and leaves other
  services as future work. It is complementary to Guará, which monitors the physical flight state.

**G5. There is demand for formal guarantees.** F3269-21 was written to integrate unassured
functions, including AI and ML. Works controlling PX4 with LLMs rely on prompt-engineering
checks, not formal guarantees.

**G6. Brazil.**
- In August 2026 there were 13,224 registered agricultural drones; 83.9% DJI and 9.1% XAG.
- 83.3% of that fleet exceeds 25 kg and operates in the specific category, with authorization and
  risk assessment. RBAC 100 is in force since 2026-06-16.
- BVLOS operations require SORA and a flight termination plan.
- No open, auditable assurance stack on an open autopilot targeting this framework was found.

## 3. Contributions

- **C1 `guara_rta`:** RTA arbiter as a PX4 ModeExecutor, explicitly mapping F3269 roles. Feasible
  because, once activated, the executor can select any mode, and the user keeps the ability to take
  back control via RC or ground station. (SPEC §2, ADR 0001, [G 1.1-1.7])
- **C2 (upstream nasa/ogma):** variable DB for `px4_msgs` and an example monitor over `/fmu/out/*`
  topics. Quick win that lands work in a NASA repository. (P7)
- **C3 `guara_daa`:** ROS 2 node for DAIDALUS v2 publishing time to loss of well-clear and maneuver
  bands. Separate package because DAIDALUS is NOSA. (ADR 0003; SPEC names it `guara_daidalus`)
- **C4 BR-UAS-Bench:** scenario suite (agricultural encounters, geofence with wind, link degradation)
  and an evidence-report generator oriented to SORA and RBAC 100. (P4)

## 4. Architecture

```
ENGINEERING (offline)
 RBAC100/SORA/F3269 ─► FRETish ─FRET─► pmLTL
      ─Ogma(+C2 px4 var-DB)─► Copilot ─► C99
      └─ CopilotVerifier ─► monitor proof

RUNTIME (companion, ROS 2)
 ┌───────────────────────────┐
 │ Complex function (C:      │
 │ LLM/ML, PX4 external mode)│
 └────────────┬──────────────┘
              │ setpoints
 ┌────────────▼──────────────┐   verdicts
 │ RTA arbiter (C1)          │◄───────────┐
 │ ModeExecutor + hysteresis │            │
 └────────────┬──────────────┘  ┌─────────┴─────────┐
              │ mode switch     │ Copilot monitors  │
 ┌────────────▼──────────────┐  │ DAIDALUS (C3)     │
 │ PX4 FMU: Hold/RTL/Land    │  │ Geofence predictor│
 │ (recovery function R)     │  └─────────▲─────────┘
 └────────────┬──────────────┘            │
              └──── /fmu/out/* (uXRCE-DDS)┘
```

Refined process view: SPEC §2.

## 5. Switching logic (Simplex)

```
Inputs at time t:
  φ_i(t) ∈ {⊤,⊥}   Copilot verdicts (pmLTL)
  τ_daa(t)          time to loss of well-clear (DAIDALUS)
  τ_gf(t)           time to geofence violation
  τ_rec             measured worst case of R to safe state
  δ_lat             measured latency detection → mode active
  h, T_d            hysteresis and dwell time

C → R  if  ∃i: φ_i = ⊥
        ∨  min(τ_daa, τ_gf) ≤ τ_rec + δ_lat

R → C  only if  min(τ_daa, τ_gf) > τ_rec + δ_lat + h
        continuously for T_d, and all φ_i = ⊤
        (return latched after N switches/window)
```

SPEC §3 refines this into per-channel thresholds (`T_*` signals, `τ_*` thresholds, obligation O-1),
stale-input detection `V(k)`, escalation, and return only from Hold (ADR 0005).

The scientific value is not the rule, which is classic. It is measuring τ_rec and δ_lat on real PX4
and producing each monitor with a correctness proof. There is precedent that this evidence chain is
accepted: Copilot monitors have flown on NASA Langley drones, justified by:
- correctness proof of the generated C (CopilotVerifier);
- evidence of bounded time and memory;
- evidence of absence of crashes.

## 6. Evaluation

- **RQ1 (effectiveness):** loss of well-clear and geofence violation with RTA on vs off, plus PX4
  default failsafe as baseline. More than 1,000 encounters per configuration, Wilson 95% CI.
- **RQ2 (cost):** false-switch rate and mission completion rate.
- **RQ3 (latency):** detection → recovery mode active, p50 and p99, compared with the τ_rec budget.
- **RQ4 (assurance):** proof generated for 100% of monitors and bounded resource use. Copilot
  monitors are constant-time and can run as a separate process.
- **RQ5 (LLM guardrail):** an adversarial planner injects k% unsafe setpoints, k ∈ {0, 0.05, 0.2}.
- **RQ6 (voice/LLM embodiment, added 2026-09-11):** see `docs/research/LLM-EMBODIMENT.md` §7.

RQ → artifact map: RQ1/RQ2 → P4 + AC-9, AC-10; RQ3 → M7, AC-18, AC-19, AC-22; RQ4 → CopilotVerifier
(blocked by R-11 toolchain); RQ5 → P5.

## 7. 12-week schedule

| Weeks | Work | Milestones |
|---|---|---|
| 1–2 | Headless SITL in container; API grounding; first Ogma monitor over `/fmu/out/*`; open Discussion on nasa/ogma | P0 ✔, P1 ✔ (draft), M1, M2 |
| 3–5 | Arbiter (C1), geofence predictor, DAIDALUS node (C3) | M3, M4, M5 |
| 6–8 | Scenario generator, batch execution, LLM planner (nominal and adversarial) | M6, P4, P5 |
| 9–10 | CopilotVerifier, latency measurement, evidence report (C4), C2 PR | M7, P7 |
| 11–12 | arXiv preprint, NFM submission, demo at PX4 weekly dev call, contact Brazilian UAS groups | P6 |

Timing fits NFM: the paper deadline was 2024-12-22 for 2025 and 2026-01-24 (after extensions) for 2026.
The 2026 edition accepted remote presentation, charged no registration and had foreign participants.
Confirm the 2027 call when it is published.

## 8. Why this builds reputation quickly

- NASA visibility: extends four NASA-maintained tools (FRET, Ogma, Copilot, DAIDALUS) to the dominant
  open autopilot — the natural continuation of the 2020 work linking FRET and Copilot to ICAROUS via cFS.
- Timing: PX4 has an active community with a weekly dev call, and the external-modes interface is still
  consolidating. The first semantic RTA sets the reference.
- Concrete Brazilian narrative: an open assurance kit with an RBAC 100-aligned evidence package, in a market
  almost entirely dependent on closed platforms.

## 9. Limitations

- The arbiter on the auxiliary computer is not high-assurance. Mitigation: PX4 returns to an internal mode
  if the external component dies. Phase 2: monitors inside the FMU. (ADR 0002, SPEC §7)
- SITL is not certification. F3269 is a certification strategy for functions that do not pass traditional
  DO-178C, not a certificate.
- DAIDALUS license: NOSA requires isolation and a compatibility review against Guará's Apache license. (ADR 0003)
- LLM-formalized requirements: Ogma itself warns it does not guarantee correctness of LLM-translated properties;
  responsibility is the user's.
- Technical curve: requires C++ and ROS 2, and some Haskell, since Copilot is a Haskell-embedded DSL.

## 10. Prompt pack

`docs/guara-prompt-pack.md` holds the project `CLAUDE.md` and eight sequential prompts:
P0 grounding · P1 spec and ADRs · P2 milestones (TDD loop, stop after 3 attempts) · P3 FRETish requirements
with human review · P4 batch benchmark with statistics · P5 adversarial LLM complex function · P6 NFM
reviewer · P7 Ogma upstream PR. Git rules (granular commits as aton-of-data, no Co-authored-by) and pnpm are embedded.

Warning: NFM prohibits generative AI for the paper's textual narrative. Use agents for code, experiments
and review; the author writes the text.

## 11. Claim verification (2026-09-11)

Status: **VERIFIED-SRC** = checked in pinned/upstream source; **VERIFIED-WEB** = checked on a primary or
publisher page; **SECONDARY** = only secondary web sources; **UNVERIFIED** = not checked yet.

| Claim | Status | Evidence |
|---|---|---|
| ICAROUS latest release V-2.2.6, 2022-01-03 | VERIFIED-SRC | `nasa/icarous` README "Current Releases"; last commit 2022-01-12 (note: latest git tag is `v2.1.22`) |
| DAIDALUS at v2.0.4, 2023-11-30 | VERIFIED-SRC | `nasa/daidalus` README line 64. **Our pin is `v2.0.3a`**; `master` has commits up to 2025-05-07 → SPEC R-14 |
| Ogma targets cFS, ROS 2, F´, standalone; no PX4 | VERIFIED-SRC | `ogma@69485b3:ogma-core/src/Command/{CFSApp,ROSApp,FPrimeApp,Standalone}.hs`; [G 4.3] |
| Ogma replaced NOSA with Apache | VERIFIED-SRC | `ogma@69485b3:ogma-core/CHANGELOG.md:93` (#293); `LICENSE` = Apache-2.0 |
| External-mode fallback only on arming-check timeout | VERIFIED-SRC | [G 2.1-2.4, 2.10] |
| PR suggests extending fallback to setpoint timeouts | VERIFIED-WEB | [PX4 PR #20707](https://github.com/PX4/PX4-Autopilot/pull/20707) |
| Interface experimental since v1.15 | SECONDARY | [PX4 ROS 2 Control Interface v1.15 docs](https://docs.px4.io/v1.15/en/ros2/px4_ros2_control_interface); re-check exact wording |
| Volocopter/DLR monitoring paper, CAV 2024 | VERIFIED-WEB | [arXiv 2404.12035](https://arxiv.org/abs/2404.12035), [Springer](https://link.springer.com/chapter/10.1007/978-3-031-65630-9_10). The "next step = automatic contingencies" paraphrase: UNVERIFIED, re-read the conclusion |
| Platum, April 2026, MAVLink boundary monitor | VERIFIED-WEB | [arXiv 2604.03886](https://arxiv.org/abs/2604.03886) (NFM 2026) |
| F3269-21 targets unassured functions incl. AI/ML | UNVERIFIED | Standard text not available (SPEC R-8) [REVIEW] |
| PX4 LLM works rely on prompt engineering, no formal guarantees | VERIFIED-WEB (sample) | [arXiv 2506.07509](https://arxiv.org/abs/2506.07509); [arXiv 2601.15486](https://arxiv.org/abs/2601.15486) states human-in-the-loop as the safety measure |
| 13,224 agri drones (2026-08-23), DJI 83.9%, XAG 9.1% | SECONDARY | [SISANT-based ranking](https://irlenmenezes.com.br/marcas-drones-agricolas-brasil-ranking-sisant-2026/); re-derive from ANAC open data before publishing |
| 83.3% > 25 kg, specific category | UNVERIFIED | — |
| RBAC 100 in force since 2026-06-16, replaces RBAC-E 94 | SECONDARY | [overview](https://irlenmenezes.com.br/rbac-100-drone-o-que-muda-2026/); cite ANAC Resolution 805 directly |
| BVLOS requires SORA + flight termination plan | UNVERIFIED | Needs RBAC 100 text [REVIEW] |
| Copilot monitors flew on NASA Langley drones; CopilotVerifier used on them | VERIFIED-WEB | [Copilot README](https://github.com/Copilot-Language/copilot/); [CopilotVerifier ICFP'23 report](https://ryanglscott.github.io/papers/copilot-verifier-icfp23.pdf) |
| 2020 FRET+Copilot+ICAROUS/cFS work | VERIFIED-WEB | [NASA/TM-20220000049](https://ntrs.nasa.gov/citations/20220000049) |
| NFM prohibits generative AI for narrative text | VERIFIED-WEB (2025) | [NFM 2025 CfP](https://shemesh.larc.nasa.gov/nfm2025/cfp.html); confirm for 2027 |
| NFM 2025/2026 deadlines and remote/free 2026 | UNVERIFIED | [NFM 2026 site](https://nfm2026.github.io/) |
