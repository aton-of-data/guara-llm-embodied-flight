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
    "PYTHON_VERSION",
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

PYPROJECT = "pyproject.toml"

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


def toml_quoted_array(text: str, marker: str) -> list[str] | None:
    """Quoted strings of the first TOML array that follows `marker`."""
    idx = text.find(marker)
    if idx < 0:
        return None
    lb = text.find("[", idx)
    rb = text.find("]", lb)
    if lb < 0 or rb < 0:
        return None
    return re.findall(r'"([^"]+)"', text[lb:rb])


SPEC_RE = re.compile(r"^([A-Za-z0-9._-]+)(>=|==)(.+)$")
LOCK_PKG_RE = re.compile(r"^([A-Za-z0-9._-]+)==(\S+)")
DIRECT_PY = ("PY_PYYAML", "PY_JSONSCHEMA", "PY_PYTEST", "PY_PYULOG")
LOCKFILE = "requirements.lock"


def pep503(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def version_tuple(v: str) -> tuple[int, ...]:
    parts: list[int] = []
    for piece in v.split("."):
        match = re.match(r"(\d+)", piece)
        parts.append(int(match.group(1)) if match else 0)
    return tuple(parts)


def spec_satisfied(locked: str, op: str, floor: str) -> bool:
    lv, fv = version_tuple(locked), version_tuple(floor)
    n = max(len(lv), len(fv))
    lv += (0,) * (n - len(lv))
    fv += (0,) * (n - len(fv))
    if op == ">=":
        return lv >= fv
    if op == "==":
        return lv == fv
    return False


def parse_lock(path: pathlib.Path) -> dict[str, tuple[str, int]]:
    """Map PEP 503 name to (version, hash_count)."""
    found: dict[str, tuple[str, int]] = {}
    current: str | None = None
    version = ""
    hashes = 0
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip().rstrip("\\").strip()
        pkg = LOCK_PKG_RE.match(line)
        if pkg:
            if current is not None:
                found[current] = (version, hashes)
            current = pep503(pkg.group(1))
            version = pkg.group(2)
            hashes = 0
            continue
        if current is not None and "--hash=" in line:
            hashes += line.count("--hash=")
    if current is not None:
        found[current] = (version, hashes)
    return found


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

    pyproject = root / PYPROJECT
    if not pyproject.is_file():
        errors.append(f"missing {PYPROJECT}")
    else:
        text = pyproject.read_text(encoding="utf-8")
        deps = toml_quoted_array(text, "\ndependencies")
        expected = [pins[k] for k in REQUIREMENT_FILES["requirements.txt"]]
        if deps is None:
            errors.append(f"{PYPROJECT} has no dependencies array")
        elif deps != expected:
            errors.append(f"{PYPROJECT} dependencies {deps} != versions.env {expected}")
        dev = toml_quoted_array(text, "\ndev")
        expected_dev = [pins[k] for k in REQUIREMENT_FILES["requirements-dev.txt"]]
        if dev is None:
            errors.append(f"{PYPROJECT} has no optional-dev array")
        elif dev != expected_dev:
            errors.append(f"{PYPROJECT} optional-dev {dev} != versions.env {expected_dev}")

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

    workflow = root / ".github" / "workflows" / "checks.yml"
    if workflow.is_file():
        text = workflow.read_text(encoding="utf-8")
        needle = f'python-version: "{pins["PYTHON_VERSION"]}"'
        if needle not in text:
            errors.append(f".github/workflows/checks.yml does not pin {needle}")
        if "requirements.lock" not in text:
            errors.append(".github/workflows/checks.yml does not install from requirements.lock")

    lock_path = root / LOCKFILE
    if not lock_path.is_file():
        errors.append(f"missing {LOCKFILE}; run scripts/lock_python.sh")
        return errors

    lock_text = lock_path.read_text(encoding="utf-8")
    if f"Python {pins['PYTHON_VERSION']}" not in lock_text:
        errors.append(
            f"{LOCKFILE} was not generated with Python {pins['PYTHON_VERSION']}; "
            "run scripts/lock_python.sh"
        )
    locked = parse_lock(lock_path)
    if not locked:
        errors.append(f"{LOCKFILE} contains no packages")
    unhashed = sorted(name for name, (_, n) in locked.items() if n < 1)
    if unhashed:
        errors.append(f"{LOCKFILE} packages without hashes: {', '.join(unhashed)}")
    for key in DIRECT_PY:
        spec = pins[key]
        match = SPEC_RE.match(spec)
        if not match:
            errors.append(f"versions.env {key}={spec!r} is not a supported pin")
            continue
        name, op, floor = match.group(1), match.group(2), match.group(3)
        entry = locked.get(pep503(name))
        if entry is None:
            errors.append(f"{LOCKFILE} missing direct dependency {name} ({spec})")
            continue
        ver, _ = entry
        if not spec_satisfied(ver, op, floor):
            errors.append(f"{LOCKFILE} {name}=={ver} does not satisfy {spec}")

    return errors
