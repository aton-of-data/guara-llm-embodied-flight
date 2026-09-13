# SPDX-License-Identifier: Apache-2.0
#
# Golden input→decision vectors for the switching kernel and the CF gateway
# (ADR 0014 / M19, ADR 0010). The kernel does not parse this directory;
# `test_conformance` and `test_gateway_vectors` do, through the C ABI.
# Passing the vectors is necessary and not sufficient: it does not make a
# containing system safe (ADR 0014 decision 4).
