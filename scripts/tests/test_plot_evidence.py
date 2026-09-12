# SPDX-License-Identifier: Apache-2.0
"""The committed figures still match the evidence they were drawn from.

A figure that has drifted from its run is a published number with no run behind it, which is
the one thing this project does not allow. Regenerating into a temporary directory and
comparing byte for byte is the cheapest possible guard against that.
"""
from __future__ import annotations

import json
import pathlib
import re
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
ASSETS = ROOT / "docs" / "assets"
FIGURES = ("latency-distribution.svg", "geofence-rta-pair.svg")


@pytest.fixture(scope="module")
def regenerated(tmp_path_factory):
    """Draw into a temporary directory. Never into docs/assets: a test that rewrites the
    file it is checking cannot fail, and would edit the working tree as a side effect."""
    out = tmp_path_factory.mktemp("figures")
    r = subprocess.run([sys.executable, "scripts/plot_evidence.py", "--out", str(out)],
                       capture_output=True, text=True, cwd=str(ROOT))
    assert r.returncode == 0, r.stderr
    return out


@pytest.mark.parametrize("name", FIGURES)
def test_the_committed_figure_matches_a_fresh_regeneration(name, regenerated):
    committed = (ASSETS / name).read_text()
    fresh = (regenerated / name).read_text()
    assert committed == fresh, (
        f"docs/assets/{name} differs from what scripts/plot_evidence.py produces now. "
        f"Regenerate it with `python3 scripts/plot_evidence.py` rather than editing it "
        f"by hand.")


def test_the_drawn_numbers_are_the_ones_in_the_evidence():
    m = json.loads((ROOT / "docs/evidence/batch_latency/metrics.json").read_text())
    p50_ms = m["delta_lat"]["p50_s"] * 1000.0
    p99_ms = m["delta_lat"]["p99_s"] * 1000.0
    svg = (ASSETS / "latency-distribution.svg").read_text()
    assert f"p50 {p50_ms:.1f} ms" in svg
    assert f"p99 {p99_ms:.1f} ms" in svg
    # One tick per run, so the figure shows the distribution rather than a summary of it.
    assert svg.count('stroke-opacity="0.55"') == m["delta_lat"]["n"]


def test_the_geofence_figure_carries_both_measured_depths():
    m = json.loads((ROOT / "docs/evidence/20260912T134907Z_llm_survey_outside_s42_pair"
                    / "metrics.json").read_text())["AC-9"]
    svg = (ASSETS / "geofence-rta-pair.svg").read_text()
    assert f"{m['depth_rta_on_m']:.3f} m" in svg
    assert f"{m['depth_rta_off_m']:.3f} m" in svg


def test_the_readme_table_agrees_with_the_figure():
    """The headline numbers appear twice; they must not disagree."""
    m = json.loads((ROOT / "docs/evidence/batch_latency/metrics.json").read_text())
    readme = (ROOT / "README.md").read_text()
    for seconds in (m["delta_lat"]["p50_s"], m["delta_lat"]["p99_s"]):
        assert re.search(rf"\b{seconds:.4f}\b", readme), (
            f"{seconds:.4f} s is in the evidence but not in the README results table")


def test_a_missing_evidence_file_is_an_error_not_a_drawn_guess(tmp_path):
    """Exercise the loader itself. Running the script from another directory proves
    nothing: it resolves its paths from __file__, so it finds the real evidence whatever
    the working directory is."""
    sys.path.insert(0, str(ROOT / "scripts"))
    import plot_evidence

    with pytest.raises(SystemExit) as exc:
        plot_evidence.load(tmp_path / "no_such_run" / "metrics.json")
    assert exc.value.code == 1


def test_the_script_runs_from_any_working_directory(tmp_path):
    """The corollary: the figures do not depend on where it is invoked from."""
    out = tmp_path / "figs"
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "plot_evidence.py"),
                        "--out", str(out)],
                       capture_output=True, text=True, cwd=str(tmp_path))
    assert r.returncode == 0, r.stderr
    for name in FIGURES:
        assert (out / name).read_text() == (ASSETS / name).read_text()


def test_the_readme_scenario_count_matches_the_directory():
    """A count written in prose drifts the moment a scenario is added."""
    words = {12: "Twelve", 13: "Thirteen", 14: "Fourteen", 15: "Fifteen", 16: "Sixteen",
             17: "Seventeen", 18: "Eighteen", 19: "Nineteen", 20: "Twenty"}
    n = len(list((ROOT / "scenarios").glob("*.yaml")))
    readme = (ROOT / "README.md").read_text()
    assert f"{words[n]} scenarios ship in" in readme, (
        f"{n} scenario files exist; the README says something else")
