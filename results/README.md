<!-- SPDX-License-Identifier: Apache-2.0 -->
# results/

This directory is empty in a fresh clone, and that is deliberate. It is where runs land on
*your* machine, and it is git-ignored: SITL artifacts (ULog, process logs, the PX4 working
directory) are large and belong to the machine that produced them.

**The reviewable part is published elsewhere.** [`docs/evidence/`](../docs/evidence) holds the
run contract and metrics of every run this project cites, copied verbatim out of `results/` by
`scripts/publish_evidence.py`. That is what to read if you want to check a number without
running anything.

## Why the documented commands take a `results/` path

Several commands in the README's reproduce table read a run directory:

```bash
./scripts/dev.sh python3 scripts/aggregate.py results/batch_latency
./scripts/dev.sh python3 scripts/check_ac.py AC-18 results/batch_latency
./scripts/dev.sh python3 scripts/check_run_contract.py results/latest
./scripts/publish_evidence.py results/latest
```

**Each of these needs a run to exist first.** On a clean checkout they have nothing to read and
will say so. Produce one with `./scripts/sitl_run.sh` or `./scripts/sitl_batch.sh`, or point the
same commands at a published directory under `docs/evidence/` instead.

## What a run directory contains

Every run writes `results/{run_id}/` with the scenario hash, the seed, the Guará SHA, the PX4
build commit, the pinned third-party commits and the PX4 parameters read back from the vehicle.
That is what makes a number re-derivable rather than merely reported, and it is why no figure
in this repository may be written down without naming the run it came from.

`latest` and `latest_llm` are convenience symlinks to the most recent run of each kind.
