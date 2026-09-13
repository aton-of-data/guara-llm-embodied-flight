# SPDX-License-Identifier: Apache-2.0
"""`python -m guara` — same entry as the `guara` console script."""
from __future__ import annotations

import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
