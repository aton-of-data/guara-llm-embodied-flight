#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""AC-2 (air) and AC-103 (space): verify the run contract of one run directory (SPEC §6).

The air profile checks config.yaml (seed, pinned third_party commits, Guará SHA, PX4 build
commit) and that at least one valid ULog was written; if the scenario declares
`expect.min_altitude_m`, the ULog must show the vehicle reached it.

The space profile has no PX4 and no ULog. What it checks instead is the declaration ADR 0015
rule 1 requires: which SDLS security association and which decryptor the uplink was configured
with. F´ v4.3.0 routes SA 0 to `ClearTextDecryptor`, which authenticates nothing
(`GROUNDING.md` D.9), so a default deployment is an unauthenticated command path. Such a run is
permitted and marked, exactly as the air side marks an SROS2-less run; what is refused is a run
that *claims* an authenticated origin the declaration does not support.

The declaration is one block, `command_path`, shared by both domains and filled per profile.
"""
import argparse
import pathlib
import re
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
ULOG_MAGIC = b"ULog\x01\x12\x35"
STARTUP_ERROR = re.compile(r"ERROR \[param\]|rcS: \d+: .*not found")
REQUIRED_KEYS = (
    "run_id", "created_utc", "scenario", "scenario_sha256", "seed", "headless",
    "guara_sha", "guara_dirty", "image_id", "px4_build_commit", "third_party", "simulator",
    "px4_params",
)
SPACE_REQUIRED_KEYS = (
    "run_id", "created_utc", "scenario", "scenario_sha256", "seed", "headless",
    "guara_sha", "guara_dirty", "command_path",
)
# Decryptors that perform no authentication, and the SA the default map routes to one
# (GROUNDING.md D.9). A run declaring either of these cannot claim an authenticated origin.
CLEARTEXT_DECRYPTORS = ("Svc::Ccsds::ClearTextDecryptor", "ClearTextDecryptor")
UNAUTHENTICATED_SA_INDEX = 0

# Values the run must have pinned and read back; see REQUIRED_PX4_PARAMS in sitl/run_scenario.py.
REQUIRED_PX4_PARAMS = {"COM_MODE_ARM_CHK": 0}


def pinned_commits(versions_md: pathlib.Path) -> dict:
    """Parse the pinned-commit table in third_party/VERSIONS.md."""
    commits = {}
    for line in versions_md.read_text().splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) >= 4:
            match = re.fullmatch(r"`([0-9a-f]{40})`", cells[3])
            if match:
                commits[cells[0]] = match.group(1)
    return commits


def max_altitude_m(ulog_path: pathlib.Path) -> float:
    from pyulog import ULog  # installed by PX4 Tools/setup/requirements.txt

    ulog = ULog(str(ulog_path), message_name_filter_list=["vehicle_local_position"])
    datasets = [d for d in ulog.data_list if d.name == "vehicle_local_position"]
    if not datasets or len(datasets[0].data["z"]) == 0:
        return float("nan")
    return float(-min(datasets[0].data["z"]))  # NED: altitude = -z


def check(run_dir: pathlib.Path) -> list:
    errors = []
    config_path = run_dir / "config.yaml"
    if not config_path.is_file():
        return [f"missing {config_path}"]
    config = yaml.safe_load(config_path.read_text()) or {}

    for key in REQUIRED_KEYS:
        if key not in config:
            errors.append(f"config.yaml missing key: {key}")
    if errors:
        return errors

    if not isinstance(config["seed"], int):
        errors.append("seed must be an integer")
    if not re.fullmatch(r"[0-9a-f]{40}", str(config["guara_sha"])):
        errors.append(f"guara_sha is not a commit SHA: {config['guara_sha']}")

    expected = pinned_commits(ROOT / "third_party" / "VERSIONS.md")
    if config["third_party"] != expected:
        errors.append(f"third_party commits differ from VERSIONS.md: {config['third_party']} != {expected}")
    if config["px4_build_commit"] != expected.get("PX4-Autopilot"):
        errors.append(f"px4_build_commit {config['px4_build_commit']} != pinned PX4-Autopilot commit")

    px4_params = config.get("px4_params") or {}
    for name, want in REQUIRED_PX4_PARAMS.items():
        entry = px4_params.get(name)
        if entry is None:
            errors.append(f"config.yaml px4_params does not record {name}")
        elif entry.get("read_back") != want:
            errors.append(
                f"{name} read back {entry.get('read_back')!r}, the run contract requires {want!r}")

    px4_log = run_dir / "px4.log"
    if not px4_log.is_file():
        errors.append(f"missing {px4_log}")
    else:
        for line in px4_log.read_text(errors="replace").splitlines():
            # Startup script errors silently leave parameters at defaults (GROUNDING A.22).
            if STARTUP_ERROR.search(line):
                errors.append(f"px4.log startup error: {line.strip()}")

    ulogs = sorted(run_dir.rglob("*.ulg"))
    valid = [p for p in ulogs if p.stat().st_size > len(ULOG_MAGIC) and p.read_bytes()[:7] == ULOG_MAGIC]
    if not valid:
        errors.append(f"no valid .ulg under {run_dir} (found {len(ulogs)} file(s))")
        return errors

    min_alt = (config.get("expect") or {}).get("min_altitude_m")
    if min_alt is not None:
        reached = max(max_altitude_m(p) for p in valid)
        if not reached >= float(min_alt):
            errors.append(f"max altitude {reached:.2f} m < expected {min_alt} m")
    return errors


def check_space(run_dir: pathlib.Path) -> tuple[list, bool]:
    """AC-103. Returns the errors and whether the declared command path is authenticated."""
    config_path = run_dir / "config.yaml"
    if not config_path.is_file():
        return [f"missing {config_path}"], False
    config = yaml.safe_load(config_path.read_text()) or {}

    errors = [f"config.yaml missing key: {key}"
              for key in SPACE_REQUIRED_KEYS if key not in config]
    if errors:
        return errors, False

    declaration = config["command_path"]
    if not isinstance(declaration, dict):
        return ["command_path must be a mapping (ADR 0015 rule 1)"], False
    for key in ("authenticated", "sdls_sa_index", "decryptor"):
        if key not in declaration:
            errors.append(f"command_path missing key: {key} (GROUNDING.md D.9)")
    if errors:
        return errors, False

    authenticated = declaration["authenticated"]
    sa_index = declaration["sdls_sa_index"]
    decryptor = str(declaration["decryptor"])
    if not isinstance(authenticated, bool):
        errors.append("command_path.authenticated must be a boolean")
    if not isinstance(sa_index, int) or isinstance(sa_index, bool):
        errors.append(f"command_path.sdls_sa_index must be an integer, got {sa_index!r}")
    if errors:
        return errors, False

    if authenticated:
        # The claim has to be supported by the SA map the run says it ran with.
        if decryptor in CLEARTEXT_DECRYPTORS:
            errors.append(
                f"command_path claims an authenticated origin through {decryptor}, which performs "
                "no authentication, no integrity checking and no decryption (GROUNDING.md D.9)")
        if sa_index == UNAUTHENTICATED_SA_INDEX:
            errors.append(
                f"command_path claims an authenticated origin on SA {sa_index}, the index the "
                "default F´ SA map routes to the pass-through decryptor (GROUNDING.md D.9)")
    return errors, bool(authenticated) and not errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=pathlib.Path)
    parser.add_argument("--profile", choices=("air", "space"), default="air",
                        help="air: PX4 SITL run (AC-2). space: F´ run declaration (AC-103).")
    args = parser.parse_args()
    run_dir = args.run_dir.resolve()
    if args.profile == "space":
        errors, authenticated = check_space(run_dir)
    else:
        errors, authenticated = check(run_dir), None
    for err in errors:
        print(f"FAIL {err}")
    if errors:
        return 1
    origin = ""
    if args.profile == "space":
        origin = (" · authenticated command path" if authenticated
                  else " · unauthenticated command path (GROUNDING.md D.9)")
    print(f"PASS run contract: {run_dir.name}{origin}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
