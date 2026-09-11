# SPDX-License-Identifier: Apache-2.0
# NOSA isolation tree (ADR 0003). DAIDALUS and any other NOSA-licensed runtime
# code live only here. Apache-2.0 packages must not depend on or include headers
# from this directory (AC-11: `python3 scripts/check_license_isolation.py`).
#
# `guara_daidalus` links the pinned DAIDALUS clone in third_party/daidalus.
# It is not on the default colcon base-paths; build it with `./scripts/daa.sh`.
# Generation-time FRET sources stay in the formal-methods image
# (`docker/Dockerfile.fm`), not in this tree.
