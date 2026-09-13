# third_party — pinned versions

Single API source of the project (see CLAUDE.md). The machine-readable pins
live in [`versions.env`](../versions.env); this file is the human table and the
licence record. `python3 scripts/check_reproducible.py --pins` fails if they
drift. Repositories are shallow clones (`--depth 1`, no submodules) recreated
by `scripts/fetch_third_party.sh`. Clone contents are not versioned.

Cloned on 2026-09-11.

| Repository | Remote | Ref | Commit | Commit date | License |
|---|---|---|---|---|---|
| PX4-Autopilot | https://github.com/PX4/PX4-Autopilot.git | tag `v1.17.0` | `d6f12ad1c4f70ad3230afd7d86e971421e02fef4` | 2026-04-24 | BSD-3-Clause |
| px4_msgs | https://github.com/PX4/px4_msgs.git | branch `release/1.17` | `86d8239e962f6939e05c3737784f60c02fa884db` | 2026-03-22 | BSD-3-Clause |
| px4-ros2-interface-lib | https://github.com/Auterion/px4-ros2-interface-lib.git | branch `release/1.17` | `4a3370f084ac6f1ef001a4afa2b007845ffd0837` | 2026-06-09 | BSD-3-Clause |
| ogma | https://github.com/nasa/ogma.git | tag `v1.15.0` | `69485b3442d76c48faaee30b37f9cbee212ceca6` | 2026-07-22 | Apache-2.0 |
| daidalus | https://github.com/nasa/daidalus.git | tag `DAIDALUSv2.0.3a` | `0647596edb218f8e8c7731ff800396297bbace99` | 2023-09-08 | NASA Open Source Agreement (NOSA) |
| fret | https://github.com/NASA-SW-VnV/fret.git | tag `v3.1.0` | `58db455be35182a015e607232d9f4e3c86731932` | 2026-03-13 | NOSA (see `LICENSE.pdf`) |
| copilot | https://github.com/Copilot-Language/copilot.git | tag `v4.8.1` | `365fb21429aa0b880f81d72dcaa9f207f5ea2d0a` | 2026-09-08 | BSD-3-Clause |
| fprime | https://github.com/nasa/fprime.git | tag `v4.3.0` | `7d8f579f159d2f7c2d4984d92828575e37f87fa6` | 2026-08-19 | Apache-2.0 |

## PX4 ↔ px4_msgs ↔ px4-ros2-interface-lib compatibility

Verified byte by byte: every `.msg` in `px4_msgs@86d8239` is identical to
`PX4-Autopilot@d6f12ad` (`msg/` and `msg/versioned/`), 0 differences.

```bash
cd third_party
for f in px4_msgs/msg/*.msg; do b=$(basename $f); \
  src=$(ls PX4-Autopilot/msg/$b PX4-Autopilot/msg/versioned/$b 2>/dev/null | head -1); \
  [ -z "$src" ] && echo "missing $b" || cmp -s $f $src || echo "diff $b"; done
```

`px4-ros2-interface-lib` `release/1.17` is the release branch matching
PX4 1.17. Its `dependencies.repos` points to `px4_msgs` `main`; Guará overrides
that with the commit pinned above.

## Version choices (confirmed in CLAUDE.md on 2026-09-11)

- PX4: `v1.17.0` — latest stable tag (`v1.18.0-rc1` and betas exist, not stable).
- ROS 2: Humble — the only distro "supported and recommended" by PX4 v1.17.0 docs
  (see GROUNDING.md, row R0). Ogma's ROS template uses Jazzy (Space ROS); see risk in GROUNDING.md.
- Ogma: `v1.15.0` — latest tag.
- F´: `v4.3.0` — latest tag at clone time; the framework host for the space-domain
  RTA (ADR 0011) and the target of Ogma's existing `fprime` backend
  (`ogma-core/src/Command/FPrimeApp.hs`). Apache-2.0, so it raises no isolation
  requirement of the kind ADR 0003 imposes on DAIDALUS.
