# SPDX-License-Identifier: Apache-2.0
"""Command-line entry point for the trusted mission layer.

    python3 -m mission.compiler --intent <file.json>
    python3 -m mission.compiler --stop "<utterance>"

Two model-free paths, and they are the two the architecture separates
(ADR 0010 rule 6, ADR 0008):

* `--intent` runs an already-parsed Mission Intent through schema validation and
  the deterministic compiler, and prints a flyable plan or the named checks that
  refused it. This is the trusted disposer; it never talks to a model.
* `--stop` runs the exact-match stop grammar, the path that must never reach a
  model at all (AC-29).

Producing an intent *from* an utterance is the untrusted step and needs a
provider; that is `scripts/llm/eval.py`, not this entry point.

Exit status: 0 a flyable plan or a matched stop verb, 2 a refusal (an invalid
intent, a plan that failed a check, or an utterance the stop grammar does not
match), 1 a usage or I/O error.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

from . import compile as mc
from . import intent as mi
from . import stop_grammar

ROOT = pathlib.Path(__file__).resolve().parents[2]
DEFAULT_SITE = ROOT / "mission/site/demo_farm.yaml"
DEFAULT_PARAMS = ROOT / "config/rta_params.yaml"


def _read_intent(source: str) -> dict:
    text = sys.stdin.read() if source == "-" else pathlib.Path(source).read_text()
    raw = json.loads(text)
    if not isinstance(raw, dict):
        raise ValueError("a Mission Intent is a JSON object")
    return raw


def _summary(plan) -> str:
    lines = [
        f"intent          {plan.intent_verb}",
        f"site            {plan.site_id}",
        f"altitude_agl_m  {plan.altitude_agl_m:.2f}",
        f"speed_m_s       {plan.speed_m_s:.2f}",
        f"waypoints       {len(plan.waypoints)}",
        f"path_length_m   {plan.path_length_m:.1f}",
        f"duration_s      {plan.duration_s:.1f}",
        f"energy_wh       {plan.energy_wh:.1f}",
    ]
    if plan.achieved_gsd_cm is not None:
        lines.insert(3, f"achieved_gsd_cm {plan.achieved_gsd_cm:.2f}")
    for check in plan.checks:
        mark = {"pass": "ok  ", "fail": "FAIL", "skip": "--  "}.get(check.status, "?   ")
        lines.append(f"  {mark} {check.name}"
                     + (f": {check.detail}" if check.detail else ""))
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="python3 -m mission.compiler",
        description="Compile a Mission Intent into a flight plan, or match the stop grammar.")
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--intent", metavar="PATH",
                      help="Mission Intent JSON file, or - for stdin")
    mode.add_argument("--stop", metavar="UTTERANCE",
                      help="match an utterance against the model-free stop grammar")
    p.add_argument("--site", type=pathlib.Path, default=DEFAULT_SITE)
    p.add_argument("--params", type=pathlib.Path, default=DEFAULT_PARAMS)
    p.add_argument("--json", action="store_true",
                   help="print the full canonical plan JSON instead of a summary")
    args = p.parse_args(argv)

    if args.stop is not None:
        verb = stop_grammar.match(args.stop)
        if verb is None:
            print("no stop verb; this utterance would be passed to the model", file=sys.stderr)
            return 2
        print(verb)
        return 0

    try:
        raw = _read_intent(args.intent)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"cannot read intent: {exc}", file=sys.stderr)
        return 1

    try:
        parsed = mi.parse(raw)
    except mi.IntentError as exc:
        print(f"refused ({exc.code}): {exc.reason}", file=sys.stderr)
        return 2

    if not parsed.is_compilable:
        print(f"{parsed.intent}: not a compilable intent; it maps to a mode, not a plan")
        return 0

    site = mc.load_site(args.site)
    limits = mc.load_gateway_limits(args.params)
    plan = mc.compile_plan(parsed, site, limits)

    print(plan.to_json() if args.json else _summary(plan), end="" if args.json else "\n")
    if not plan.flyable:
        print(f"refused (checks): {', '.join(plan.failed_checks())}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
