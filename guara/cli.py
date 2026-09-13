# SPDX-License-Identifier: Apache-2.0
"""Workstation CLI. Subcommands are trusted-layer tools; none of them fly."""
from __future__ import annotations

import argparse
import sys

from . import doctor


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv[:1] == ["compile"]:
        from mission.compiler.__main__ import main as compile_main
        return compile_main(argv[1:])

    parser = argparse.ArgumentParser(
        prog="guara",
        description="Guará trusted-layer tools. Nothing here commands a vehicle.")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser(
        "doctor",
        help="workstation preflight: pins, platform and the reachable install tier",
    )
    sub.add_parser(
        "compile",
        help="compile a Mission Intent, or match the model-free stop grammar",
    )
    args = parser.parse_args(argv)
    if args.cmd == "doctor":
        return doctor.run()
    parser.error(f"unknown command {args.cmd}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
