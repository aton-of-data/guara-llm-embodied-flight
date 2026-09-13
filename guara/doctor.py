# SPDX-License-Identifier: Apache-2.0
"""Workstation preflight (M17 / AC-51, gap G-S5).

Prints the platform, the pins from versions.env and the highest install tier
this machine currently reaches. Exit 0 if and only if tier 0 is usable: the
mission and space layers import, and versions.env is readable. Higher tiers
are reported, never required — a laptop running the compiler is a valid T0
host (PLAN-M17-M28.md §3).

This output is a configuration record, not an assurance argument. It does not
use the word "safe" of Guará (ADR 0014 decision 4).
"""
from __future__ import annotations

import importlib
import os
import platform
import shutil
import sys
from pathlib import Path

TIER0_MODULES = ("yaml", "jsonschema", "mission.compiler", "space.keepout")
PIN_KEYS = ("PX4_REF", "PX4_COMMIT", "ROS2_DISTRO", "OGMA_REF", "FPRIME_REF",
            "PY_PYYAML", "PY_JSONSCHEMA")


def repo_root() -> Path | None:
    """Locate the clone: versions.env next to pyproject.toml.

    Editable installs and a working tree both have this layout. A published
    wheel without the clone is M20 (AC-69) and is not claimed here.
    """
    starts = [Path.cwd().resolve(), Path(__file__).resolve()]
    seen: set[Path] = set()
    for start in starts:
        for cand in [start, *start.parents]:
            if cand in seen:
                continue
            seen.add(cand)
            if (cand / "versions.env").is_file() and (cand / "pyproject.toml").is_file():
                return cand
    return None


def _ram_bytes() -> int | None:
    try:
        pages = os.sysconf("SC_PHYS_PAGES")
        size = os.sysconf("SC_PAGE_SIZE")
        return int(pages) * int(size)
    except (ValueError, OSError, AttributeError):
        return None


def _fmt_bytes(n: int) -> str:
    return f"{n / (1024 ** 3):.1f} GiB"


def _which_cxx() -> str | None:
    for name in ("c++", "clang++", "g++"):
        path = shutil.which(name)
        if path:
            return path
    return None


def _module_ok(name: str) -> tuple[bool, str]:
    try:
        importlib.import_module(name)
        return True, "ok"
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"


def run(out=None, err=None) -> int:
    """Print the workstation preflight. Streams resolve at call time."""
    out = sys.stdout if out is None else out
    err = sys.stderr if err is None else err
    plat = sys.platform
    machine = platform.machine() or "unknown"
    py = platform.python_version()
    print(f"platform       {plat}", file=out)
    print(f"machine        {machine}", file=out)
    print(f"python         {py}", file=out)

    root = repo_root()
    if root is None:
        print("FAIL doctor: versions.env not found; run from a clone or `pip install -e .`",
              file=err)
        return 1
    print(f"root           {root}", file=out)

    scripts = root / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    from pins import load_env

    try:
        pins = load_env(root / "versions.env")
    except (OSError, ValueError) as exc:
        print(f"FAIL doctor: cannot read versions.env: {exc}", file=err)
        return 1
    print("pins           versions.env", file=out)
    for key in PIN_KEYS:
        print(f"  {key:<13} {pins.get(key, '?')}", file=out)

    disk = shutil.disk_usage(root)
    print(f"disk_free      {_fmt_bytes(disk.free)}", file=out)
    ram = _ram_bytes()
    print(f"ram            {_fmt_bytes(ram) if ram is not None else 'unreported'}", file=out)

    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    t0_ok = True
    print("T0             mission and space compilers (no ROS, no PX4, no Docker)", file=out)
    for name in TIER0_MODULES:
        ok, detail = _module_ok(name)
        mark = "ok  " if ok else "FAIL"
        print(f"  {mark} {name}" + ("" if ok else f" ({detail})"), file=out)
        t0_ok = t0_ok and ok
    if disk.free < 100 * 1024 * 1024:
        print("  FAIL disk_free < 0.1 GiB", file=out)
        t0_ok = False

    cxx = _which_cxx()
    cmake = shutil.which("cmake")
    core = (root / "core").is_dir()
    print("T1             host-free C++ kernel (M18)", file=out)
    print(f"  {'ok  ' if cxx else '--  '} cxx            {cxx or 'not found'}", file=out)
    print(f"  {'ok  ' if cmake else '--  '} cmake          {cmake or 'not found'}", file=out)
    print(f"  {'ok  ' if core else '--  '} core/          {'present' if core else 'not extracted'}",
          file=out)

    docker = shutil.which("docker")
    print("T2             SITL image (Docker)", file=out)
    print(f"  {'ok  ' if docker else '--  '} docker         {docker or 'not found'}", file=out)

    print("T3             HITL / vehicle — not probed (M21+)", file=out)

    if not t0_ok:
        print("FAIL doctor: tier T0 is not usable", file=err)
        return 1
    print(f"PASS doctor: tier T0 on {plat}/{machine}", file=out)
    return 0
