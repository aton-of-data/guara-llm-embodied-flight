# SPDX-License-Identifier: Apache-2.0
#
# Golden input→decision vectors for the switching kernel (ADR 0014 / M19).
# The kernel does not parse this directory; `test_conformance` does, through
# the C ABI. Gateway rules of ADR 0010 are not in these files (they are host
# behaviour). Passing the vectors is necessary and not sufficient: it does not
# make a containing system safe (ADR 0014 decision 4).
