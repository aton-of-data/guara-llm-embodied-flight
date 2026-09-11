# LLM embodiment of drones — limitations and solution design

Status: research draft (2026-09-11). Not a SPEC. Nothing here is a result; external
numbers are attributed to their sources and are not Guará measurements.

## 1. Problem

> An owner tells the drone, by voice, what to do ("survey the north soybean field and show me
> where it looks sick"). The drone plans, flies, collects images and areas, and talks back —
> locally in the field or remotely — like a robot that flies.

Target users: farmers, agronomists, cooperatives, small service providers. Open source,
open weights, auditable, usable offline in rural areas.

## 2. Is this "first of a kind"? Honest positioning

Natural-language drone control is **not** new:

| Work | What it does | Safety basis |
|---|---|---|
| ChatGPT for Robotics / PromptCraft (Microsoft, 2023) | LLM writes code over a drone function library in AirSim | Human reviews code |
| TypeFly (2023, IEEE TMC 2025) | LLM emits MiniSpec, a token-efficient DSL, stream-interpreted | DSL restricts actions |
| Taking Flight with Dialogue (2025) | PX4 + ROS 2 + Ollama local LLMs/VLMs, sim + real quadcopter | Not specified in abstract |
| EchoPilot (2025) | Voice → LangGraph → MCP → MAVSDK → PX4, local Ollama | Telemetry verification; author asks for safety ideas |
| MAVLinkMCP, ardupilot-mcp | MCP servers exposing MAVLink to LLM agents | SITL-first, "safety-gated", human in loop |
| Universal LLM–Drone C2 interface (UC Irvine, 2026) | MCP + MAVSDK, many LLMs, sub-250 g real drone in cage | "Human in the loop for manual override"; non-determinism acknowledged |
| AerialClaw (2026) | Brain–skill–runtime agent framework, PX4 SITL/AirSim | "Safety-oriented runtime validation" (unspecified) |

Common pattern: safety = prompt engineering + tool restriction + human override.
None found uses a **formally specified, measured runtime-assurance boundary** (F3269-style) between the
LLM and the autopilot.

Defensible novelty claim (still [REVIEW] until a systematic literature search in P6):
**an open-source, open-weight, voice-driven drone agent whose physical authority is bounded by a
formally specified RTA with measured latency and verified monitors, targeting a real regulatory
framework (RBAC 100 / MAPA Portaria 298).** That is exactly Guará + a language layer.

## 3. Limitations inventory

### 3.1 Guará itself (inherited, see SPEC §7 and §9)

| # | Limitation | Source |
|---|---|---|
| L-G1 | Arbiter on companion, not high-assurance; FM-2 (dead arbiter in Hold undetected), FM-3 (no re-register in flight) | SPEC §5, [G 2.6, 2.7] |
| L-G2 | All thresholds and latencies are hypotheses until M7 | SPEC R-12 |
| L-G3 | DAA recovery is Hold — does not resolve converging traffic (agricultural aircraft!) | SPEC §7.2, R-6 |
| L-G4 | DAIDALUS config sized for large aircraft; pin behind upstream | SPEC R-5, R-14 |
| L-G5 | Non-cooperative traffic (no ADS-B) invisible; spoofing not handled | SPEC §7.5 |
| L-G6 | ROS 2 DDS unauthenticated — any node can publish setpoints | [G A.13], FM-12 |
| L-G7 | SITL only; no transfer guarantee | SPEC §7.8 |
| L-G8 | Monitors cover specified physical properties only; mission-level mistakes pass | SPEC §7.6, §7.12 |
| L-G9 | Open blockers: executor-death timing, FRET→Ogma run, CopilotVerifier toolchain | GROUNDING status table, R-11 |

### 3.2 Language model

| # | Limitation | Why it matters in flight |
|---|---|---|
| L-M1 | Hallucination and non-determinism | Same sentence can yield different plans; wrong field, wrong altitude |
| L-M2 | Token-by-token generation latency | TypeFly was built specifically to cut plan latency; an LLM cannot sit in a control loop |
| L-M3 | Weak metric/spatial reasoning | "50 m left of the barn" requires grounding in a map, not language |
| L-M4 | Long-horizon drift | UC Irvine interface reports conflicting commands and missions limited to minutes |
| L-M5 | Jailbreaks | RoboPAIR reports 100% jailbreak rate against three LLM-controlled robots |
| L-M6 | Indirect prompt injection via perception | A VLM reading signs, labels or QR codes in the field is an input channel for an attacker |
| L-M7 | Portuguese/rural vocabulary, crop and agronomic terms | Open models are weaker outside English; misclassification of intent |
| L-M8 | Model licenses | "Open weights" licenses vary (some restrict use/scale); must be checked per model [REVIEW] |

### 3.3 Voice

| # | Limitation | Note |
|---|---|---|
| L-V1 | Rotor noise makes onboard ASR impractical for commanding | Put the microphone on the ground device (phone/tablet/radio), not the drone |
| L-V2 | Accents, wind noise outdoors, code-switching | Needs field-recorded evaluation set |
| L-V3 | Inaudible/adversarial audio (DolphinAttack) | Voice is an attack surface; commands must be confirmed and authenticated |
| L-V4 | Who is speaking? | Any bystander could command the aircraft without speaker binding / push-to-talk |
| L-V5 | Ambiguity and deixis ("there", "that part") | Needs map/touch disambiguation and explicit readback |
| L-V6 | TTS stack churn | Piper was archived Oct 2025 (moved to Open Home Foundation fork) — dependency risk |

### 3.4 Compute, energy, connectivity

| # | Limitation | Note |
|---|---|---|
| L-C1 | Onboard LLM costs mass and power → flight time | Keep LLM on the ground in phases 1–2 |
| L-C2 | Rural connectivity gaps | Cloud LLM cannot be a dependency; offline-first |
| L-C3 | Link loss mid-mission | Plan must be fully uploaded and executable without the LLM; RC/PX4 link-loss failsafe stays |
| L-C4 | Edge hardware variance | Reported local voice-assistant latencies range from ~1–2 s (desktop GPU) to 5–8 s (Raspberry Pi 5) per community write-ups — acceptable for mission dialog, never for control |

### 3.5 Perception and agronomy

| # | Limitation | Note |
|---|---|---|
| L-P1 | "Looks sick" is not a measurement | VLM opinions ≠ agronomic diagnosis; need indices (NDVI/NDRE) + calibrated sensors + agronomist sign-off |
| L-P2 | Photogrammetry is batch and slow | OpenDroneMap produces orthomosaics/indices offline, not in flight |
| L-P3 | Radiometric calibration, georeferencing error | Without calibration, index maps are not comparable across flights |
| L-P4 | No public benchmark for voice→agro mission | Must be built (BR-UAS-Bench extension) |

### 3.6 Regulation, liability, privacy (Brazil first) [REVIEW]

| # | Limitation | Note |
|---|---|---|
| L-R1 | RBAC 100 (in force 2026-06-16) classifies by operational risk: Open / Specific / Certified | Voice-commanded autonomy likely pushes toward Specific with risk assessment |
| L-R2 | BVLOS needs specific authorization via DECEA/SARPAS | Phase 1 must be VLOS |
| L-R3 | Spraying/solids: MAPA Portaria 298/2021 — SIPEAGRO registration, CAAR course or responsible agronomist, per-application records, 20 m buffers | In scope as class-D capability packs (ADR 0009), disabled until dispense monitors, T2 airframe and regulatory preconditions exist |
| L-R4 | Remote pilot remains responsible | The LLM cannot be the pilot in command; a certified human is |
| L-R5 | LGPD: imagery of neighbors, people, houses | Data minimization, on-device storage, retention policy |
| L-R6 | Market is ~84% DJI (closed) | Guará needs PX4; target open airframes or PX4 retrofits; DJI SDK integration is out of scope |

### 3.7 Human factors

| # | Limitation | Note |
|---|---|---|
| L-H1 | Over-trust in a talking machine | Talk-back must state uncertainty and what was *not* checked |
| L-H2 | Mode confusion (who is flying?) | Always announce RTA interventions and mode changes by voice |
| L-H3 | Intent vs safety | "Keep going" is not permission to ignore an RTA switch (ADR 0005 T5 still applies) |

## 4. Design principle

**The LLM proposes, a deterministic compiler disposes, the RTA enforces, PX4 falls back, the human commands.**

The LLM is treated as the adversarial complex function of RQ5: its output is untrusted data.
It never emits setpoints, MAVLink, or code. It emits a typed, bounded **Mission Intent**.

## 5. Architecture

```mermaid
flowchart TB
  subgraph Ground[Ground device: phone / tablet / laptop — offline-first]
    PTT[Push-to-talk + speaker binding]
    ASR[ASR: local Whisper-class model]
    AG[Language agent: open-weight LLM\ntools = read farm map, propose intent, explain]
    MAP[(Farm map: field polygons,\nno-fly zones, buffers, home points)]
    MC[Mission compiler — deterministic\nintent → coverage plan\nstatic checks + energy model]
    RB[Readback + confirmation\nTTS + map preview]
    REP[Reports: ODM orthomosaic, NDVI,\nfindings summarized by LLM]
  end
  subgraph Air[Aircraft: PX4 + companion]
    CF[Guará CF: plan executor\nvia GuaraCfGateway]
    RTA[Guará RTA arbiter + monitors]
    PX4[PX4: Hold / RTL / Land\nfailsafes, RC override]
    CAM[Camera trigger / capture]
  end
  PTT --> ASR --> AG
  MAP --> AG
  AG -- MissionIntent JSON --> MC
  MAP --> MC
  MC -- rejected + reason --> AG
  MC -- plan --> RB
  RB -- human confirms --> CF
  CF --> RTA --> PX4
  CAM --> REP
  RTA -- events: switches, reasons --> AG
  AG -- speech --> RB
```

### 5.1 Layers and trust

| Layer | Trust | Can it move the aircraft? | Failure handled by |
|---|---|---|---|
| Human (remote pilot) | Authority | Yes (RC/GCS override) | Regulation, training |
| ASR | Untrusted | No | Readback + confirmation |
| LLM agent | Untrusted | No | Mission compiler rejects; RQ5-style testing |
| Mission compiler | Trusted, deterministic, unit-tested | No (produces a plan) | Tests + static property checks |
| Guará CF (plan executor) | Untrusted by RTA | Only through gateway | RTA |
| Guará RTA | Assured (measured, verified monitors) | Switches to RF | PX4 fallback (FM-1..FM-5) |
| PX4 | Assured baseline | Yes | Internal failsafes |

### 5.1.1 What the gateway enforces today (ADR 0010)

The trust table above says the CF "can only move the aircraft through the gateway". Since the review
of 2026-09-11 the gateway also states *what it accepts* from that untrusted layer, which is the part
that matters once a language model is behind it (`docs/adr/0010-untrusted-complex-function-contract.md`):

| Threat from an LLM-driven CF | Enforced where | Evidence |
|---|---|---|
| Stalls, then a stale setpoint keeps flying | Freshness measured from reception on the gateway clock; implausible stamps rejected | `test_gateway_envelope.cpp` |
| Confident but out-of-envelope command (speed, climb, yaw step) | Clamp to `gateway.max_*`, non-finite rejected | `test_gateway_envelope.cpp` |
| Plausible command that flies at the fence | Shadow check of the *proposed* velocity against the predictor before forwarding | AC-9 re-run: 0.000 m outside, no mode switch |
| Keeps proposing the unsafe motion after a recovery | T5 also requires the CF's intent to be clear | `test_return_policy.cpp` |
| Resets the anti-chattering budget by toggling modes | Switch history survives T1 | `test_return_policy.cpp` |
| Silent degradation (monitor or DAA process dies) | Enabled channels fail closed; the flight profile refuses an undeclared omission | `test_channel_gating.cpp` |

Open before any LLM drives a CF, in order: transport authentication on `/guara/cf/*` and `fmu/in/*`
(SROS2, FM-12); the RQ6b jailbreak corpus against the mission compiler; the RQ5 fuzz corpus against
the gateway (future stamps, NaN, extreme values, mode-tool abuse).

### 5.2 Mission Intent (sketch, v0)

Closed vocabulary; everything else is rejected.

```json
{
  "intent": "survey",               // survey | inspect_point | return_home | land_now | status | abort
  "field_id": "north-3",            // must exist in farm map
  "sensor": "rgb",                  // rgb | multispectral | thermal
  "gsd_cm": 3.0,                    // bounded by compiler table
  "overlap": {"front": 0.75, "side": 0.65},
  "altitude_agl_m": null,           // null = compiler derives from gsd; clamp to regulatory max
  "deliver": ["orthomosaic", "ndvi"],
  "utterance_hash": "sha256:…"      // audit link to the recorded command
}
```

Safety-relevant commands (`abort`, `land_now`, `return_home`) bypass the LLM: keyword grammar on the
ASR output + physical button, mapped directly to PX4 modes. The LLM path is never required to stop.

### 5.3 Mission compiler checks (pre-flight, deterministic)

- Coverage polygon ⊆ field polygon ⊖ buffers ⊆ geofence loaded into Guará **and** PX4 (same file, hashed — ADR 0004).
- Altitude ≤ configured regulatory ceiling [PARAMETER TBD from RBAC 100].
- Energy: planned path length × consumption model + reserve ≤ battery budget [HYPOTHESIS model].
- VLOS: every waypoint within configured VLOS radius of the pilot position.
- Output plan is the only input to the CF; the RTA monitors the *flight*, the compiler checks the *plan*.
  Two independent layers, like ADR 0004's Guará + PX4 geofence.

### 5.4 Deployment modes

| Mode | Where LLM/ASR run | Link needed | Phase |
|---|---|---|---|
| Local | Ground laptop / edge GPU in the truck | Only RC/telemetry | 1–2 |
| Remote | Ground node at farm office; operator connects over 4G/satellite | Operator ↔ ground node; aircraft still controlled locally | 2 |
| Onboard assist | Small model on companion for talk-back/status only | None | 3 (after power budget study) |

## 6. Limitation → mitigation map

| Limitation | Mitigation | Verified by |
|---|---|---|
| L-M1, L-M3, L-M4 | Closed intent schema; map-grounded field IDs; compiler rejects; LLM out of control loop | Intent accuracy eval (RQ6a) |
| L-M2, L-C4 | LLM only at mission level; stop commands bypass LLM | Latency of stop path measured (RQ6d) |
| L-M5, L-M6 | Treat LLM as adversarial CF; compiler + RTA independent of LLM; no VLM text read as instructions | Jailbreak corpus (PT/EN) against compiler (RQ6b); RQ5 |
| L-M7 | Evaluate models on Portuguese agro command set; fine-tune only if needed | RQ6a per language |
| L-V1..L-V5 | Ground mic, push-to-talk, speaker binding, readback + explicit confirm, map disambiguation | Field audio test set |
| L-C1..L-C3 | Offline-first, plan fully uploaded, PX4 link-loss failsafe unchanged | SITL link-drop scenario (P4 degradations) |
| L-P1..L-P3 | Indices from calibrated sensors via ODM; LLM summarizes, agronomist decides | Report contains method + uncertainty |
| L-R1..L-R6 | VLOS, survey-only scope, human PIC, LGPD policy, PX4 airframes | Regulatory review [REVIEW] |
| L-H1..L-H3 | Voice announcements of every RTA switch with reason; uncertainty statements | Usability study |
| L-G6 | SROS2 on CF/gateway topics (phase 2) | New P0 on SROS2 + PX4 bridge |

## 7. Research questions (RQ6, extends PROPOSAL §6)

All values only from `results/` via script (CLAUDE.md).

- **RQ6a intent accuracy:** fraction of spoken commands compiled into the intended mission, per model, language, noise level.
- **RQ6b unsafe-intent rejection:** fraction of adversarial/jailbreak utterances that yield a flyable unsafe plan (target: compiler rejects all out-of-envelope plans; RTA catches in-flight residuals).
- **RQ6c RTA interventions with LLM CF:** switches per flight hour, true vs false (reuses RQ1/RQ2 machinery).
- **RQ6d voice latency:** utterance end → readback; stop-word → RF active (must not depend on LLM).
- **RQ6e task success:** mission completion and data-product quality (coverage %, GSD achieved).

## 8. Roadmap (after the 12-week RTA plan; does not change NFM scope)

| Milestone | Content | Depends on |
|---|---|---|
| M8 | Mission Intent schema + deterministic compiler + unit tests (no LLM) | M4 (geofence) |
| M9 | LLM agent in SITL producing intents; RQ6a/b with text input | M8, P5 |
| M10 | Voice pipeline on ground device (ASR, push-to-talk, readback, stop grammar) | M9 |
| M11 | Imaging + ODM reports + talk-back summaries | M10 |
| M12 | Field-trial readiness: VLOS ops manual, risk assessment, LGPD policy | M11, human regulatory review |

Written ADRs: 0006 license (Apache-2.0), 0007 reference airframe, 0008 language packs, 0009 capability packs.
Candidate ADRs (not yet written): 0010 LLM emits intents only; 0011 stop path bypasses LLM;
0012 ASR on ground device with confirmation; 0013 offline-first model selection and model-license check;
0014 mission compiler as pre-flight monitor; 0015 SROS2 for CF topics.

## 9. Author decisions (2026-09-11)

| Question | Decision | Record |
|---|---|---|
| Scope | All civil uses of LLM embodiment, via capability packs gated by risk class | ADR 0009, §10 |
| Airframe | Holybro X500 V2 + Pixhawk (PX4 Dev Kit), `gz_x500` twin; SIH for batches; heavy-lift tier later | ADR 0007 |
| Languages | Portuguese (`pt-BR`) and English (`en`) from the start; new languages as drop-in packs | ADR 0008 |
| License | Apache-2.0 (as Ogma, cFS, F Prime, ROS 2) | ADR 0006 |

## 10. Civil use-case catalog (capability packs, ADR 0009)

Class: S sense · D dispense · T transport · C cooperate. Phase: when the pack can first run (S packs need
M8–M11; D/T need the T2 airframe and extra monitors; C needs multi-vehicle work). "Extra monitors" are on top
of the base RTA (geofence, DAA, stale inputs). Regulatory notes are pointers, all [REVIEW].

| Domain | Use case | Example voice command | Class | Extra monitors / data | Regulatory pointer | Phase |
|---|---|---|---|---|---|---|
| Agriculture | Crop scouting and NDVI/NDRE survey | "Map north field with the multispectral camera" | S | coverage, GSD, light conditions | RBAC 100 | 2 |
| Agriculture | Plant counting / stand gaps / yield estimate | "Count plants in plot 4" | S | model uncertainty reported | RBAC 100 | 2 |
| Agriculture | Pest/disease hotspot detection → scouting route for agronomist | "Where does the soybean look sick?" | S | agronomist sign-off (L-P1) | RBAC 100 | 2 |
| Agriculture | Irrigation pivot, canal, reservoir, fence inspection | "Check pivot 2 for leaks" | S | thermal calibration | RBAC 100 | 2 |
| Agriculture | Frost / heat stress thermal mapping at dawn | "Thermal map of the orchard at 5 am" | S | night-ops constraints | RBAC 100 (night) | 3 |
| Agriculture | Pesticide / fertilizer spraying | "Spray fungicide on hotspots, 20 m from the river" | D | flow/dose, wind/drift, buffer zones, tank level | MAPA Portaria 298, SIPEAGRO, CAAR | 3 |
| Agriculture | Solid spreading / seeding / cover crops | "Seed brachiaria on the terrace" | D | release rate, swath | MAPA Portaria 298 | 3 |
| Agriculture | Biological control release (e.g. parasitoid insects) | "Release capsules every 30 m in sugarcane block B" | D | release-point logging | MAPA [REVIEW] | 3 |
| Livestock | Herd counting, locating strays, water trough checks | "Find cattle outside pasture 3" | S | animal-disturbance altitude floor | RBAC 100 | 2 |
| Forestry / environment | Deforestation, illegal fire spots, wildlife census, riparian monitoring | "Scan the reserve border for smoke" | S | smoke/visibility | RBAC 100, environmental agency rules | 2 |
| Fire | Pasture/forest fire perimeter mapping for brigades | "Map the fire front and send to the truck" | S | heat/updraft limits, manned-aircraft traffic (DAA critical) | RBAC 100, DECEA coordination | 3 |
| Infrastructure | Power line, solar farm, wind turbine, telecom tower, bridge inspection | "Inspect panels row 1 to 20 for hotspots" | S | obstacle proximity, EMI | RBAC 100 | 3 |
| Mapping | Orthomosaic, topography, rural cadastre (CAR) | "Make an orthomosaic of the whole property" | S | GCP/RTK accuracy | RBAC 100 | 2 |
| Construction / mining | Progress tracking, stockpile volumes | "Measure the gravel pile" | S | volume uncertainty | RBAC 100 | 3 |
| Emergency | Flood / landslide / storm damage assessment | "Show me flooded roads" | S | BVLOS likely | RBAC 100 BVLOS, civil defense | 3 |
| Emergency | Search and rescue support (find people to help them) | "Search the riverbank for the missing hiker" | C | people-proximity policy, privacy minimization | RBAC 100, civil defense | 4 |
| Logistics | Medical/sample transport between farm sites or clinics | "Take this sample to the lab" | T | payload mass/CG, drop zone | RBAC 100 specific/certified | 4 |
| Logistics | Spare part drop to field machinery | "Drop the fuse at tractor 7" | T | drop-zone clearance | RBAC 100 | 4 |
| Communications | Temporary telemetry/radio relay over hills | "Hover as relay at 60 m" | S | endurance, tether option | RBAC 100 | 3 |
| Property care | Consented perimeter check of own property | "Check the gate is closed" | S | no person identification; LGPD minimization | RBAC 100, LGPD | 2 |
| Research / education | Teaching RTA, formal methods, robotics | "Fly the geofence demo" | S | SITL-first | — | 1 |
| Multi-vehicle | Coordinated survey or spraying by several drones | "Split field 5 between two drones" | C | inter-vehicle separation, shared geofence | RBAC 100 [REVIEW] | 4 |

Never packs (ADR 0009 §4): weapons or harmful payloads; target selection or tracking of specific people for
enforcement or harassment; covert surveillance; interference with aircraft; defeating geofence, remote ID or failsafes.

## 11. Sources

- TypeFly: [arXiv 2312.14950](https://arxiv.org/abs/2312.14950), [site](https://typefly.github.io/)
- ChatGPT for Robotics: [arXiv 2306.17582](https://ar5iv.labs.arxiv.org/html/2306.17582), [PromptCraft AirSim](https://github.com/microsoft/PromptCraft-Robotics/tree/main/chatgpt_airsim)
- Taking Flight with Dialogue (PX4 + ROS 2 + Ollama): [arXiv 2506.07509](https://arxiv.org/abs/2506.07509), [repo](https://github.com/limshoonkit/ros2-agent-ws)
- EchoPilot: [PX4 forum](https://discuss.px4.io/t/echopilot-langgraph-mcp-server-for-natural-language-px4-control/46998)
- MAVLinkMCP: [repo](https://github.com/ion-g-ion/MAVLinkMCP); ardupilot-mcp: [repo](https://github.com/rmeadomavic/ardupilot-mcp)
- Universal LLM–Drone C2 interface: [arXiv 2601.15486](https://arxiv.org/html/2601.15486v2)
- AerialClaw: [arXiv 2606.12142](https://arxiv.org/abs/2606.12142)
- UAVs meet LLMs survey: [arXiv 2501.02341](https://arxiv.org/pdf/2501.02341)
- Jailbreaking LLM-controlled robots (RoboPAIR): [arXiv 2410.13691](https://arxiv.org/abs/2410.13691)
- RoboGuard: [arXiv 2503.07885](https://arxiv.org/abs/2503.07885); SafePlan: [arXiv 2503.06892](https://arxiv.org/abs/2503.06892); Safety Chip: [arXiv 2309.09919](https://arxiv.org/pdf/2309.09919)
- DolphinAttack: [arXiv 1708.09537](https://arxiv.org/pdf/1708.09537)
- Local voice stack notes (Whisper + Ollama + Piper, Piper archival): [write-up](https://dev.to/kunal_d6a8fea2309e1571ee7/local-ai-voice-assistant-stack-2026-whisper-piper-ollama-wired-together-572l), [Jetson Orin robot brain](https://thomasthelliez.com/blog/building-a-local-robot-brain-on-jetson-orin-nano-super/)
- OpenDroneMap multispectral: [docs](https://docs.opendronemap.org/multispectral/)
- VLMs in agriculture review: [arXiv 2407.19679](https://arxiv.org/pdf/2407.19679)
- RBAC 100 overview: [article](https://irlenmenezes.com.br/rbac-100-drone-o-que-muda-2026/); RBAC-E 94: [ANAC](https://antigo.anac.gov.br/assuntos/legislacao/legislacao-1/rbha-e-rbac/rbac/rbac-e-94)
- MAPA Portaria 298/2021: [LegisWeb](https://www.legisweb.com.br/legislacao/?id=420676)
- Brazilian agri-drone fleet (SISANT): [ranking](https://irlenmenezes.com.br/marcas-drones-agricolas-brasil-ranking-sisant-2026/)
- Holybro PX4 Development Kit X500 V2: [product](https://holybro.com/products/px4-development-kit-x500-v2), [docs](https://docs.holybro.com/drone-development-kit/px4-development-kit-x500v2)
- PX4 payload use cases (spraying as generic actuator): [PX4 docs](https://docs.px4.io/main/en/payloads/use_cases)
- Heavy-lift octocopter platforms (secondary): [article](https://zbotic.in/octocopter-drone-build-heavy-lift-platform-for-industry/)
