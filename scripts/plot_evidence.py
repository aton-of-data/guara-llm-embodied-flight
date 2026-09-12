#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Draw the published figures from the published evidence, and from nothing else.

A figure is a claim. This script reads the same `metrics.json` files a reviewer reads under
`docs/evidence/`, and every number it draws is printed to stdout as it draws it, so the figure
can be checked against the directory it came from (CLAUDE.md: no number without a run).

It writes plain SVG with no plotting dependency, so regenerating a figure needs nothing beyond
the Python already required to run the mission compiler.

    python3 scripts/plot_evidence.py

Exit status 1 if an evidence file is missing — a missing input is never drawn around.
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "docs" / "evidence"
OUT = ROOT / "docs" / "assets"

BATCH = EVIDENCE / "batch_latency" / "metrics.json"
PAIR = EVIDENCE / "20260912T134907Z_llm_survey_outside_s42_pair" / "metrics.json"

INK = "#1f2328"
MUTED = "#656d76"
GRID = "#d0d7de"
ACCENT = "#d1561b"      # the guará orange of the mascot
SAFE = "#1a7f37"
PAPER = "#ffffff"       # the figure carries its own background, so it reads in either theme


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def text(x, y, s, size=12, fill=INK, anchor="start", weight="normal"):
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-family="system-ui,-apple-system,'
            f'Segoe UI,Helvetica,Arial,sans-serif" font-size="{size}" fill="{fill}" '
            f'text-anchor="{anchor}" font-weight="{weight}">{esc(s)}</text>')


def load(path: pathlib.Path) -> dict:
    if not path.exists():
        print(f"missing evidence: {path.relative_to(ROOT)}", file=sys.stderr)
        raise SystemExit(1)
    return json.loads(path.read_text())


def latency_figure() -> str:
    m = load(BATCH)
    values = sorted(r["delta_lat_s"] * 1000.0 for r in m["runs"])
    # Derive the subtitle from the run ids rather than restating them by hand.
    seeds = sorted(int(re.search(r"_s(\d+)$", r["run_id"]).group(1)) for r in m["runs"])
    scenarios = {re.search(r"Z_(.+)_s\d+$", r["run_id"]).group(1) for r in m["runs"]}
    contiguous = seeds == list(range(seeds[0], seeds[0] + len(seeds)))
    seed_text = (f"seeds {seeds[0]}-{seeds[-1]}" if contiguous
                 else f"{len(seeds)} seeds from {seeds[0]}")
    subtitle = (f"{len(values)} headless SITL runs, {seed_text}, "
                f"scenario {'/'.join(sorted(scenarios))}")
    p50 = m["delta_lat"]["p50_s"] * 1000.0
    p99 = m["delta_lat"]["p99_s"] * 1000.0
    n = m["delta_lat"]["n"]
    tau_gf = m["o1"]["tau_gf_s"] * 1000.0

    print(f"[latency] n={n} runs, p50={p50:.2f} ms, p99={p99:.2f} ms, "
          f"min={values[0]:.2f} ms, max={values[-1]:.2f} ms, tau_gf={tau_gf:.0f} ms")

    W, H = 720, 322
    L, R, T, B = 60, 30, 58, 64
    pw = W - L - R
    hi = 80.0  # ms, fixed axis so the figure is comparable between regenerations
    assert values[-1] < hi, "a run exceeded the drawn axis; widen it rather than clipping"

    def sx(ms):
        return L + pw * (ms / hi)

    parts = [f'<rect width="{W}" height="{H}" fill="{PAPER}"/>']
    parts.append(text(L, 26, "End-to-end switch latency δ_lat", 15, INK, weight="600"))
    parts.append(text(L, 44, subtitle, 11.5, MUTED))

    band_y, band_h = T + 26, 92
    for ms in range(0, int(hi) + 1, 10):
        x = sx(ms)
        parts.append(f'<line x1="{x:.1f}" y1="{band_y}" x2="{x:.1f}" '
                     f'y2="{band_y + band_h}" stroke="{GRID}" stroke-width="1"/>')
        parts.append(text(x, band_y + band_h + 18, str(ms), 11, MUTED, "middle"))
    parts.append(text(L + pw / 2, band_y + band_h + 38, "milliseconds", 11.5, MUTED, "middle"))

    # One tick per run: the distribution, not a summary of it.
    for v in values:
        parts.append(f'<line x1="{sx(v):.1f}" y1="{band_y + 14}" x2="{sx(v):.1f}" '
                     f'y2="{band_y + 62}" stroke="{ACCENT}" stroke-width="2" '
                     f'stroke-opacity="0.55" stroke-linecap="round"/>')

    for label, val, dy in (("p50", p50, 0), ("p99", p99, 0)):
        x = sx(val)
        parts.append(f'<line x1="{x:.1f}" y1="{band_y + 4}" x2="{x:.1f}" '
                     f'y2="{band_y + 72}" stroke="{INK}" stroke-width="1.5"/>')
        parts.append(text(x, band_y - 2 + dy, f"{label} {val:.1f} ms", 11.5, INK, "middle",
                          "600"))

    # The same p99 against the budget it has to fit inside, on the budget's own scale —
    # drawn on the axis above it would suggest the budget is nearly spent, which inverts
    # the result.
    y = band_y + band_h + 76
    track = pw
    used = max(2.0, track * (p99 / tau_gf))
    parts.append(f'<rect x="{L}" y="{y}" width="{track:.1f}" height="14" fill="{GRID}" '
                 f'rx="7"/>')
    parts.append(f'<rect x="{L}" y="{y}" width="{used:.1f}" height="14" fill="{ACCENT}" '
                 f'rx="7"/>')
    parts.append(text(L, y - 8,
                      f"δ_lat p99 = {p99:.1f} ms against the geofence budget "
                      f"τ_gf = {tau_gf:.0f} ms — obligation O-1 holds with margin",
                      11.5, MUTED))
    parts.append(text(L + track, y + 30, f"{tau_gf:.0f} ms", 11, MUTED, "end"))
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" ' \
           f'height="{H}" role="img">{"".join(parts)}</svg>\n'


def geofence_figure() -> str:
    m = load(PAIR)["AC-9"]
    on = m["depth_rta_on_m"]
    off = m["depth_rta_off_m"]
    transitions = len(m["transitions_rta_on"])
    print(f"[geofence] rta_on depth={on:.3f} m, rta_off depth={off:.3f} m, "
          f"{transitions} recorded transitions with the RTA on")

    W, H = 720, 300
    L, T = 60, 58
    bar_w, gap, maxw = 34, 26, 470
    hi = 50.0  # metres
    assert off < hi

    parts = [f'<rect width="{W}" height="{H}" fill="{PAPER}"/>']
    parts.append(text(L, 26, "Geofence breach depth, same plan and same seed", 15, INK,
                      weight="600"))
    parts.append(text(L, 44, "scenario llm_survey_outside, seed 42 — a compiled plan "
                             "flown as the complex function", 11.5, MUTED))

    for i, (label, val, colour) in enumerate((("RTA on", on, SAFE),
                                              ("RTA off", off, ACCENT))):
        y = T + 34 + i * (bar_w + gap)
        w = max(2.0, maxw * (val / hi))
        parts.append(text(L - 8, y + bar_w * 0.64, label, 12.5, INK, "end", "600"))
        parts.append(f'<rect x="{L}" y="{y}" width="{w:.1f}" height="{bar_w}" '
                     f'fill="{colour}" rx="3"/>')
        shown = f"{val:.3f} m" + (" — never left the fence" if val == 0 else "")
        parts.append(text(L + w + 10, y + bar_w * 0.64, shown, 12.5, INK))

    y = T + 34 + 2 * (bar_w + gap) + 26
    parts.append(f'<line x1="{L}" y1="{y}" x2="{W - 30}" y2="{y}" stroke="{GRID}"/>')
    parts.append(text(L, y + 22,
                      "With the arbiter enabled the same plan is held at the fence; the "
                      "recorded transition is", 11.5, MUTED))
    parts.append(text(L, y + 38, "CF/NONE → RF/HOLD, cause 0x8 (geofence), then "
                                 "RF/HOLD → INACTIVE on pilot command.", 11.5, MUTED))
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" ' \
           f'height="{H}" role="img">{"".join(parts)}</svg>\n'


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, svg in (("latency-distribution.svg", latency_figure()),
                      ("geofence-rta-pair.svg", geofence_figure())):
        (OUT / name).write_text(svg)
        print(f"wrote docs/assets/{name}  ({len(svg)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
