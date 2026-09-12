## What this changes

<!-- One paragraph. If it closes an issue, say "Closes #N". -->

## The command you ran, and its output

<!--
No claim without a run. Paste the command and an excerpt of its output.
For a pure-Python change:   python3 -m pytest scripts/tests -q
For the C++ core:           ./scripts/dev.sh colcon test --packages-select guara_rta guara_geofence guara_monitors
For a licence-boundary change: python3 scripts/check_license_isolation.py
-->

```
```

## Checklist

- [ ] One logical change per commit; messages are `type(scope): imperative summary`
- [ ] No `Co-authored-by` trailer, and no mention of an assistant or AI tool anywhere in the diff
- [ ] Every new source file starts with `SPDX-License-Identifier: Apache-2.0`
- [ ] If this adds a safety function: a test that failed before the implementation
- [ ] If this touches an upstream API: the `repo@commit:file:line` row is in `GROUNDING.md`
- [ ] If this adds a flight operation: its document is in `docs/operations/`
- [ ] If this reports a number: it came from `results/` via a script, and the run is named
- [ ] Nothing NOSA-licensed outside `nosa/` (`scripts/check_license_isolation.py` passes)
- [ ] Civil flight safety only (ADR 0009 §4)
