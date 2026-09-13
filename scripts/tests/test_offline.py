#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""G-S6 / AC-56: GUARA_OFFLINE=1 never clones, fetches or builds an image."""
from __future__ import annotations

import os
import pathlib
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]


def test_offline_fetch_refuses_to_clone_when_the_cache_is_empty(tmp_path):
    tree = tmp_path / "repo"
    (tree / "scripts").mkdir(parents=True)
    shutil.copy2(ROOT / "scripts" / "fetch_third_party.sh", tree / "scripts")
    shutil.copy2(ROOT / "versions.env", tree / "versions.env")
    (tree / "third_party").mkdir()
    env = os.environ.copy()
    env["GUARA_OFFLINE"] = "1"
    r = subprocess.run(
        ["bash", str(tree / "scripts" / "fetch_third_party.sh")],
        cwd=str(tree),
        capture_output=True,
        text=True,
        env=env,
    )
    assert r.returncode != 0, r.stdout + r.stderr
    assert "GUARA_OFFLINE=1" in r.stderr
    assert "will not fetch" not in r.stderr
    assert "clone is not cached" in r.stderr
    assert not (tree / "third_party" / "PX4-Autopilot").exists()


def test_offline_fetch_refuses_a_wrong_commit_without_fetching(tmp_path):
    tree = tmp_path / "repo"
    (tree / "scripts").mkdir(parents=True)
    shutil.copy2(ROOT / "scripts" / "fetch_third_party.sh", tree / "scripts")
    shutil.copy2(ROOT / "versions.env", tree / "versions.env")
    repo = tree / "third_party" / "PX4-Autopilot"
    repo.mkdir(parents=True)
    subprocess.run(["git", "init"], cwd=str(repo), check=True, capture_output=True)
    subprocess.run(
        ["git", "-c", "user.email=dev@example.com", "-c", "user.name=dev",
         "commit", "--allow-empty", "-m", "stub"],
        cwd=str(repo),
        check=True,
        capture_output=True,
    )
    env = os.environ.copy()
    env["GUARA_OFFLINE"] = "1"
    r = subprocess.run(
        ["bash", str(tree / "scripts" / "fetch_third_party.sh")],
        cwd=str(tree),
        capture_output=True,
        text=True,
        env=env,
    )
    assert r.returncode != 0, r.stdout + r.stderr
    assert "will not fetch" in r.stderr
    log = subprocess.run(
        ["git", "-C", str(repo), "log", "--oneline"],
        capture_output=True, text=True, check=True,
    )
    assert log.stdout.count("\n") == 1


def test_dev_sh_uses_network_none_when_offline():
    text = (ROOT / "scripts" / "dev.sh").read_text(encoding="utf-8")
    assert "GUARA_OFFLINE" in text
    assert "--network=none" in text
    assert "image ${image} is not cached" in text
    fetch = (ROOT / "scripts" / "fetch_third_party.sh").read_text(encoding="utf-8")
    clone_idx = fetch.index("git -c advice.detachedHead=false clone")
    offline_idx = fetch.index('GUARA_OFFLINE:-')
    assert offline_idx < clone_idx
