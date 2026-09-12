# Licensing, copyright and the NOSA boundary

The licence, the NOSA isolation boundary and the trademark position. Split out of the
README, which links here from §13.

---

Guará is **Apache-2.0** ([`LICENSE`](../LICENSE), [`NOTICE`](../NOTICE),
[ADR 0006](adr/0006-license-apache-2.md)) — the same licence as Ogma, cFS, F´ and ROS 2.
Every source file carries `SPDX-License-Identifier: Apache-2.0`; the documentation and the
figures under [`docs/`](docs) are released under the same licence.

> Copyright 2026 Aton Bertini Dornfeld &lt;dornfeld.in@gmail.com&gt; and the Guará contributors.

DAIDALUS and FRET are under the NASA Open Source Agreement. NOSA code lives only in
[`nosa/`](nosa), is kept off the default colcon path, and is built by its own wrapper; FRET is
generation-time tooling in the formal-methods image and never ships in a runtime artefact. The
boundary is enforced by `scripts/check_license_isolation.py`, not by convention. F´, the second
host, is Apache-2.0 and raises no isolation requirement of its own
([`GROUNDING.md`](../GROUNDING.md) D.1). The legal interpretation of NOSA alongside Apache-2.0 and
BSD is marked [REVIEW] and needs a human lawyer before any container that embeds DAIDALUS is
distributed ([ADR 0003](adr/0003-daidalus-nosa-isolation.md), risk R-9).

<a id="trademarks"></a>

## Trademarks

No part of this project implies endorsement by NASA, JPL, the Dronecode Foundation, Open
Robotics, PX4, Auterion or any other upstream project. Guará is an independent research
prototype and is not affiliated with, sponsored by, or reviewed by any of them.

NASA, FRET, Ogma, Copilot, DAIDALUS, F´, PX4, ROS and ROS 2 are the marks of their respective
owners. This repository refers to them **nominatively** — by name, in plain text, only as far as
is needed to say which software Guará integrates and at which pinned commit. It deliberately
carries **no** third-party logo, insignia or logotype:

- The **NASA Insignia, Logotype and Seal** are protected by law, are not in the public domain,
  and may not be used in a way that implies NASA endorsement of software. They do not appear
  here, and neither do the project identifiers of the NASA-maintained tools Guará builds on
  ([NASA Brand Center, images and media](https://www.nasa.gov/nasa-brand-center/images-and-media/)).
- The **PX4 and Dronecode** marks are governed by the Dronecode Foundation trademark policy,
  which requires official unmodified artwork, no suggestion of affiliation, and a disclaimer —
  this section is that disclaimer
  ([Dronecode trademarks](https://dronecode.org/trademarks/)).
- The **ROS** marks are governed by the Open Robotics trademark rules; ROS is written in
  capitals and never pluralised or possessive
  ([ROS Trademark Rules and Guidelines](https://www.ros.org/imgs/TrademarkRulesAndGuidelines2022.pdf)).

The Apache-2.0 licence of Ogma and F´, and the BSD-3-Clause licence of PX4 and Copilot, grant
rights to the **code** only; Apache-2.0 §6 expressly grants no trademark rights. Nothing in
`third_party/` is redistributed by this repository — the clones are recreated locally by
[`scripts/fetch_third_party.sh`](../scripts/fetch_third_party.sh).

The Guará name and the guará-fox mascot are the project's own, commissioned for it and released
with the repository under Apache-2.0 ([`docs/assets/README.md`](assets/README.md)).
