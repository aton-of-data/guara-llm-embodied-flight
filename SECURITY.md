# Security policy

Guará is a research prototype that sits between an untrusted planner and a flight vehicle. Treat
anything you find here as safety-relevant.

## Reporting a vulnerability

**Do not open a public issue.**

Report privately through GitHub's [private vulnerability
reporting](https://github.com/aton-of-data/guara-llm-embodied-flight/security/advisories/new),
or by email to **dornfeld.in@gmail.com** with `[guara-security]` in the subject.

Please include the affected commit, what an attacker gains, and the smallest command or scenario
that reproduces it. A SITL scenario file is the ideal report.

This is a single-maintainer research project, not a vendor with a support contract. Expect an
acknowledgement within 7 days and an assessment within 30. There is no bug bounty. You will be
credited in the fix commit unless you ask otherwise.

## What is already known, and is not a vulnerability report

The threat model for this phase is stated in [`docs/SPEC.md` §5 and §7](docs/SPEC.md) and
summarised in [README §7](README.md#7--limits-what-guará-does-not-guarantee). The following are
**documented, accepted limitations of the current phase**. Reports that restate them are
welcome as issues but are not vulnerabilities:

- **DDS is unauthenticated (FM-12).** Any node on the domain can publish to
  `/fmu/in/trajectory_setpoint` and bypass the gateway entirely; PX4 does not authenticate the
  origin of a message. The mitigation is an SROS2 profile, planned as M9b. Until then the only
  supported configuration is a closed local DDS domain.
- **Guará does not survive every one of its own failures.** With an internal recovery mode
  active the arbiter's death is invisible to PX4 (FM-2), and the arbiter cannot re-register in
  flight (FM-3).
- **A wrong requirement is not detectable (FM-10).** Monitors check what was specified; a bad
  FRETish formalisation passes silently.
- **Decision time is measured, not proven.** Guará runs outside the FMU, without the autopilot's
  real-time guarantees, and there is no WCET analysis.
- **Voice and language models are adversarially reachable by design.** That is the premise of
  the architecture, not a flaw in it: the model is untrusted, and the boundary is what is
  claimed. A jailbreak that produces a *refused* intent is the system working.

## What is very much a vulnerability report

- A path that reaches the vehicle **without passing the gateway**, other than the unauthenticated
  DDS case above.
- An input that makes `DecisionCore` allocate, block, or miss its period.
- A Mission Intent that is **accepted by the schema and compiled into a flyable plan** while
  violating the geofence, the altitude envelope, the VLOS constraint or the energy reserve. This
  is the highest-value finding in the repository — the compiler is the trusted disposer, and a
  bypass there is a real physical-authority escape.
- An utterance that the stop grammar fails to resolve to a stop verb, or that resolves to the
  wrong one.
- A way to make the arbiter *delay or suppress* a switch away from the complex function.
- Any route by which a credential reaches a log, a prompt, an evidence directory or a result
  file ([ADR 0013](docs/adr/0013-llm-evaluation-protocol.md) decision 7).

## Credentials

No credential is ever committed. `.env` is git-ignored; `.env.example` carries names and no
values. The evaluation harness records the *name* of the environment variable it read, never the
value, and `scripts/dev.sh` forwards nothing into the container unless `GUARA_PASS_ENV` names it
explicitly. If you believe a credential has been committed, report it privately as above.

## Supported versions

There are no releases yet. Only the current `main` is supported; there is no backporting.
