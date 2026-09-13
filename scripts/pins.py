#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Single-source pin check (M17 / AC-52, gap G-S2).

`versions.env` is the only place a pin may be written. Dockerfiles, the
requirements files, `third_party/VERSIONS.md` and `scripts/fetch_third_party.sh`
must agree with it. The checker is stdlib-only so `check_reproducible.py --pins`
runs on a machine that has not yet installed the Python layer.
"""
from __future__ import annotations

import pathlib
import re

ARG_RE = re.compile(r"^ARG\s+([A-Z][A-Z0-9_]*)=(\S+)\s*$")
FROM_RE = re.compile(r"^FROM\s+(\S+)")
ENV_LINE_RE = re.compile(r"^([A-Z][A-Z0-9_]*)=(.*)$")
COMMIT_RE = re.compile(r"\b[0-9a-f]{40}\b")
TABLE_ROW_RE = re.compile(r"^\|([^|]+)\|([^|]+)\|([^|]+)\|([^|]+)\|")

REQUIRED_KEYS = (
    "ROS2_DISTRO",
    "ROS2_BASE_IMAGE",
    "FM_BASE_IMAGE",
    "PX4_REMOTE",
    "PX4_REF",
    "PX4_COMMIT",
    "PX4_MSGS_REMOTE",
    "PX4_MSGS_REF",
    "PX4_MSGS_COMMIT",
    "PX4_ROS2_INTERFACE_LIB_REMOTE",
    "PX4_ROS2_INTERFACE_LIB_REF",
    "PX4_ROS2_INTERFACE_LIB_COMMIT",
    "XRCE_AGENT_REMOTE",
    "XRCE_AGENT_REF",
    "OGMA_REMOTE",
    "OGMA_REF",
    "OGMA_COMMIT",
    "COPILOT_REMOTE",
    "COPILOT_REF",
    "COPILOT_COMMIT",
    "FRET_REMOTE",
    "FRET_REF",
    "FRET_COMMIT",
    "DAIDALUS_REMOTE",
    "DAIDALUS_REF",
    "DAIDALUS_COMMIT",
    "FPRIME_REMOTE",
    "FPRIME_REF",
    "FPRIME_COMMIT",
    "GHC_VERSION",
    "CABAL_VERSION",
    "NODE_MAJOR",
    "PY_PYYAML",
    "PY_JSONSCHEMA",
    "PY_PYTEST",
    "PY_PYULOG",
)

# Dockerfile ARG names that must exist and equal the same key in versions.env.
DOCKERFILE_ARGS = {
    "docker/Dockerfile": ("PX4_REF", "PX4_COMMIT", "XRCE_AGENT_REF"),
    "docker/Dockerfile.fm": (
        "GHC_VERSION",
        "CABAL_VERSION",
        "OGMA_REF",
        "OGMA_COMMIT",
        "COPILOT_REF",
        "COPILOT_COMMIT",
        "FRET_REF",
        "FRET_COMMIT",
        "NODE_MAJOR",
    ),
}

DOCKERFILE_FROM = {
    "docker/Dockerfile": "ROS2_BASE_IMAGE",
    "docker/Dockerfile.fm": "FM_BASE_IMAGE",
}

REQUIREMENT_FILES = {
    "requirements.txt": ("PY_PYYAML", "PY_JSONSCHEMA"),
    "requirements-dev.txt": ("PY_PYTEST", "PY_PYULOG"),
}

VERSIONS_MD_REPOS = (
    ("PX4-Autopilot", "PX4_REMOTE", "PX4_REF", "PX4_COMMIT"),
    ("px4_msgs", "PX4_MSGS_REMOTE", "PX4_MSGS_REF", "PX4_MSGS_COMMIT"),
    ("px4-ros2-interface-lib", "PX4_ROS2_INTERFACE_LIB_REMOTE",
     "PX4_ROS2_INTERFACE_LIB_REF", "PX4_ROS2_INTERFACE_LIB_COMMIT"),
    ("ogma", "OGMA_REMOTE", "OGMA_REF", "OGMA_COMMIT"),
    ("daidalus", "DAIDALUS_REMOTE", "DAIDALUS_REF", "DAIDALUS_COMMIT"),
    ("fret", "FRET_REMOTE", "FRET_REF", "FRET_COMMIT"),
    ("copilot", "COPILOT_REMOTE", "COPILOT_REF", "COPILOT_COMMIT"),
    ("fprime", "FPRIME_REMOTE", "FPRIME_REF", "FPRIME_COMMIT"),
)

FETCH_COMMIT_VARS = (
    "PX4_COMMIT",
    "PX4_MSGS_COMMIT",
    "PX4_ROS2_INTERFACE_LIB_COMMIT",
    "OGMA_COMMIT",
    "DAIDALUS_COMMIT",
    "FRET_COMMIT",
    "COPILOT_COMMIT",
    "FPRIME_COMMIT",
)

# Clone URLs still written in Dockerfiles (ARG covers the version, not the host).
DOCKERFILE_URLS = {
    "docker/Dockerfile": ("PX4_REMOTE", "XRCE_AGENT_REMOTE"),
    "docker/Dockerfile.fm": ("OGMA_REMOTE", "COPILOT_REMOTE", "FRET_REMOTE"),
}


def load_env(path: pathlib.Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        match = ENV_LINE_RE.match(line)
        if not match:
            raise ValueError(f"{path}: not KEY=VALUE: {raw}")
        key, value = match.group(1), match.group(2).strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
            value = value[1:-1]
        values[key] = value
    return values


def dockerfile_args(path: pathlib.Path) -> dict[str, str]:
    found: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        match = ARG_RE.match(raw.strip())
        if match:
            found[match.group(1)] = match.group(2)
    return found


def dockerfile_from(path: pathlib.Path) -> str | None:
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line.startswith("#"):
            continue
        match = FROM_RE.match(line)
        if match:
            return match.group(1)
    return None


def requirement_lines(path: pathlib.Path) -> list[str]:
    lines: list[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        lines.append(line)
    return lines


def versions_md_rows(path: pathlib.Path) -> dict[str, tuple[str, str, str]]:
    rows: dict[str, tuple[str, str, str]] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        match = TABLE_ROW_RE.match(raw)
        if not match:
            continue
        name = match.group(1).strip()
        remote = match.group(2).strip()
        ref_cell = match.group(3).strip()
        commit_cell = match.group(4).strip().strip("`")
        if name in ("Repository", "---"):
            continue
        if not COMMIT_RE.fullmatch(commit_cell):
            continue
        rows[name] = (remote, ref_cell, commit_cell)
    return rows


def check(root: pathlib.Path) -> list[str]:
    """Return human-readable errors; empty means the tree is consistent."""
    errors: list[str] = []
    env_path = root / "versions.env"
    if not env_path.is_file():
        return [f"missing {env_path}"]
    try:
        pins = load_env(env_path)
    except ValueError as exc:
        return [str(exc)]

    missing = [k for k in REQUIRED_KEYS if k not in pins]
    extra_required_empty = [k for k in REQUIRED_KEYS if not pins.get(k)]
    if missing:
        errors.append(f"versions.env missing keys: {', '.join(missing)}")
    if extra_required_empty:
        errors.append(f"versions.env empty keys: {', '.join(extra_required_empty)}")
    if errors:
        return errors

    for rel, keys in DOCKERFILE_ARGS.items():
        path = root / rel
        if not path.is_file():
            errors.append(f"missing {rel}")
            continue
        args = dockerfile_args(path)
        undeclared = sorted(k for k in args if k not in pins)
        if undeclared:
            errors.append(f"{rel} ARG not in versions.env: {', '.join(undeclared)}")
        for key in keys:
            if key not in args:
                errors.append(f"{rel} missing ARG {key}")
            elif args[key] != pins[key]:
                errors.append(f"{rel} ARG {key}={args[key]!r} != versions.env {pins[key]!r}")

        from_key = DOCKERFILE_FROM[rel]
        image = dockerfile_from(path)
        if image is None:
            errors.append(f"{rel} has no FROM")
        elif image != pins[from_key]:
            errors.append(f"{rel} FROM {image!r} != versions.env {from_key}={pins[from_key]!r}")

        text = path.read_text(encoding="utf-8")
        for url_key in DOCKERFILE_URLS.get(rel, ()):
            if pins[url_key] not in text:
                errors.append(f"{rel} does not contain {url_key}={pins[url_key]!r}")

    for rel, keys in REQUIREMENT_FILES.items():
        path = root / rel
        if not path.is_file():
            errors.append(f"missing {rel}")
            continue
        lines = requirement_lines(path)
        expected = [pins[k] for k in keys]
        if rel == "requirements-dev.txt":
            if not lines or lines[0] != "-r requirements.txt":
                errors.append(f"{rel} must start with '-r requirements.txt'")
            lines = lines[1:]
        if lines != expected:
            errors.append(f"{rel} pins {lines} != versions.env {expected}")

    versions_md = root / "third_party" / "VERSIONS.md"
    if not versions_md.is_file():
        errors.append("missing third_party/VERSIONS.md")
    else:
        rows = versions_md_rows(versions_md)
        for name, remote_k, ref_k, commit_k in VERSIONS_MD_REPOS:
            if name not in rows:
                errors.append(f"third_party/VERSIONS.md missing row {name}")
                continue
            remote, ref_cell, commit = rows[name]
            if remote != pins[remote_k]:
                errors.append(
                    f"third_party/VERSIONS.md {name} remote {remote!r} != {pins[remote_k]!r}"
                )
            if pins[ref_k] not in ref_cell:
                errors.append(
                    f"third_party/VERSIONS.md {name} ref {ref_cell!r} does not contain {pins[ref_k]!r}"
                )
            if commit != pins[commit_k]:
                errors.append(
                    f"third_party/VERSIONS.md {name} commit {commit} != versions.env {pins[commit_k]}"
                )

    fetch = root / "scripts" / "fetch_third_party.sh"
    if not fetch.is_file():
        errors.append("missing scripts/fetch_third_party.sh")
    else:
        text = fetch.read_text(encoding="utf-8")
        if "versions.env" not in text:
            errors.append("scripts/fetch_third_party.sh does not source versions.env")
        for var in FETCH_COMMIT_VARS:
            if "${" + var + "}" not in text:
                errors.append(f"scripts/fetch_third_party.sh does not use ${{{var}}}")
        hardcoded = COMMIT_RE.findall(text)
        if hardcoded:
            errors.append(
                "scripts/fetch_third_party.sh hardcodes commits; they belong in versions.env: "
                + ", ".join(hardcoded)
            )

    pip_in_docker = (root / "docker" / "Dockerfile").read_text(encoding="utf-8")
    pip_lines = [ln for ln in pip_in_docker.splitlines()
                 if re.search(r"\bpip3?\s+install\b", ln)]
    if pip_lines and not any("requirements" in ln for ln in pip_lines):
        errors.append("docker/Dockerfile installs Python packages without a requirements file")

    return errors
