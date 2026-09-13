#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""G-S2 / AC-52: versions.env is the single pin source; drift fails the check.

The tests copy the pin files into a temporary tree and mutate one of them, so a
regression that stops detecting drift cannot hide behind a green run of the
real repository.
"""
from __future__ import annotations

import pathlib
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import pins  # noqa: E402

PIN_FILES = (
    "versions.env",
    "docker/Dockerfile",
    "docker/Dockerfile.fm",
    "requirements.txt",
    "requirements-dev.txt",
    "third_party/VERSIONS.md",
    "scripts/fetch_third_party.sh",
)


def clone_pin_tree(tmp_path: pathlib.Path) -> pathlib.Path:
    for rel in PIN_FILES:
        dest = tmp_path / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / rel, dest)
    return tmp_path


def rewrite(path: pathlib.Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    assert old in text, f"{path} does not contain {old!r}"
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def test_the_repository_pins_are_consistent():
    errors = pins.check(ROOT)
    assert errors == [], errors


def test_a_dockerfile_arg_drift_is_detected(tmp_path):
    tree = clone_pin_tree(tmp_path)
    rewrite(tree / "docker" / "Dockerfile", "ARG PX4_REF=v1.17.0", "ARG PX4_REF=v1.16.0")
    errors = pins.check(tree)
    assert any("PX4_REF" in e and "v1.16.0" in e for e in errors), errors


def test_a_from_image_drift_is_detected(tmp_path):
    tree = clone_pin_tree(tmp_path)
    rewrite(tree / "docker" / "Dockerfile",
            "FROM ros:humble-ros-base-jammy",
            "FROM ros:iron-ros-base-jammy")
    errors = pins.check(tree)
    assert any("FROM" in e and "iron" in e for e in errors), errors


def test_a_requirements_drift_is_detected(tmp_path):
    tree = clone_pin_tree(tmp_path)
    rewrite(tree / "requirements.txt", "PyYAML>=6.0", "PyYAML>=5.0")
    errors = pins.check(tree)
    assert any("requirements.txt" in e for e in errors), errors


def test_a_versions_md_commit_drift_is_detected(tmp_path):
    tree = clone_pin_tree(tmp_path)
    rewrite(tree / "third_party" / "VERSIONS.md",
            "d6f12ad1c4f70ad3230afd7d86e971421e02fef4",
            "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
    errors = pins.check(tree)
    assert any("PX4-Autopilot" in e and "aaaaaaaa" in e for e in errors), errors


def test_a_hardcoded_fetch_commit_is_detected(tmp_path):
    tree = clone_pin_tree(tmp_path)
    fetch = tree / "scripts" / "fetch_third_party.sh"
    rewrite(fetch, "${PX4_COMMIT}", "d6f12ad1c4f70ad3230afd7d86e971421e02fef4")
    errors = pins.check(tree)
    assert any("hardcodes commits" in e for e in errors), errors


def test_an_undeclared_dockerfile_arg_is_detected(tmp_path):
    tree = clone_pin_tree(tmp_path)
    dockerfile = tree / "docker" / "Dockerfile"
    dockerfile.write_text(dockerfile.read_text(encoding="utf-8") + "\nARG UNTRACKED_PIN=1\n",
                          encoding="utf-8")
    errors = pins.check(tree)
    assert any("UNTRACKED_PIN" in e for e in errors), errors


def test_a_dockerfile_url_drift_is_detected(tmp_path):
    tree = clone_pin_tree(tmp_path)
    rewrite(tree / "docker" / "Dockerfile",
            "https://github.com/PX4/PX4-Autopilot.git",
            "https://github.com/example/PX4-Autopilot.git")
    errors = pins.check(tree)
    assert any("PX4_REMOTE" in e for e in errors), errors


def test_pip_install_without_requirements_is_detected(tmp_path):
    tree = clone_pin_tree(tmp_path)
    dockerfile = tree / "docker" / "Dockerfile"
    text = dockerfile.read_text(encoding="utf-8")
    old = ("COPY requirements.txt requirements-dev.txt /tmp/guara-py/\n"
           "RUN pip3 install --no-cache-dir -r /tmp/guara-py/requirements-dev.txt \\\n"
           " && rm -rf /tmp/guara-py\n")
    new = 'RUN pip3 install --no-cache-dir "PyYAML>=6.0" "jsonschema>=4.0"\n'
    assert old in text, "Dockerfile pip install block moved; update this test"
    dockerfile.write_text(text.replace(old, new, 1), encoding="utf-8")
    errors = pins.check(tree)
    assert any("without a requirements file" in e for e in errors), errors


def test_cli_pins_exits_zero_on_the_real_tree():
    r = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "check_reproducible.py"), "--pins"],
        cwd=str(ROOT), capture_output=True, text=True,
    )
    assert r.returncode == 0, r.stdout + r.stderr
    assert "PASS pins" in r.stdout
