# SPDX-License-Identifier: Apache-2.0
"""Ground-side mission layer: intent schema, deterministic compiler, site model.

Nothing in this package may command a vehicle. It turns an untrusted Mission Intent
(ADR 0010 rule 6) into a plan that a trusted executor can fly, or rejects it with a reason.
"""
