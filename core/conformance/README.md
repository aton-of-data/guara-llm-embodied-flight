# SPDX-License-Identifier: Apache-2.0
#
# Golden input→decision vectors for the switching kernel, the CF gateway
# and the monitor table (ADR 0014 / M19, ADR 0010, ADR 0002). The kernel
# does not parse this directory; the C tests and `guara ctk` do, through
# the C ABI or the independent Python port. Passing the vectors is
# necessary and not sufficient: it does not make a containing system
# safe (ADR 0014 decision 4).
