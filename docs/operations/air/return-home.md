# Air operation — return home

| | |
|---|---|
| Intent verb | `return_home` (stop class) |
| Capability class | Safety operation — available in every capability pack |
| Domain / host | Air · PX4 v1.17 + ROS 2 Humble |
| Target platform mode | **RTL** |
| Status | Grammar **implemented**, model-independence measured (AC-29 PASS); mode mapping and button are M10 |
| Evidence | `docs/evidence/20260912T114925Z_cursor-stop-r3_cursor-agent/` |

Break off the mission and fly the PX4 return-to-launch sequence. The lowest-ranked stop verb:
any utterance that also matches `abort` or `land_now` resolves to those instead.

## 1. What the operator asks for

> "Return to launch." · "Come home." · "RTL."
> "Volta pra base." · "Retorna."

## 2. Words to motion

The stop path of [abort](abort.md) §2 with `return_home` as the resolved verb: grammar first,
no model request, straight to the platform mode.

## 3. Why RTL is the platform's business, not Guará's

RTL is a complete PX4 navigation behaviour — climb to the return altitude, fly home, descend,
land — with its own parameters, its own failsafe interactions and years of field use. Guará
does not re-implement any of it, and does not wrap it:

- The recovery function is the *platform's* assured mode (ADR 0001). RTL as an operator command
  and RTL as an RTA recovery target are the same PX4 behaviour reached from two directions.
- Guará never defers a PX4 failsafe, and a pilot RC/GCS mode change drops Guará to `INACTIVE`
  immediately (principle 7). An operator who says "come home" gets the same aircraft behaviour
  a pilot flipping the switch would get.
- The RTA's v1 recovery for a geofence or DAA violation is Hold, **not** RTL: a return path is
  a trajectory, and commanding a trajectory in response to a predicted violation would put
  Guará in the business of planning at exactly the moment it should be stopping (ADR 0005).

## 4. Evidence

Covered by the AC-29 stop-corpus run: 24/24 resolved by the grammar, zero model requests
(command and output in [abort](abort.md) §4).

## 5. What this operation must not claim

- RTL is not a safe path. It flies a route PX4 computes; Guará's geofence and DAA channels keep
  watching, but no one has proven the return corridor is clear.
- Stop-path latency is unmeasured until AC-34 (M10).
- Link loss, low battery and other PX4-initiated returns are PX4 failsafes, unmodified and
  authoritative — they are not this operation.

## 6. Open items

- M10 voice pipeline, physical button, AC-34 latency.
- Announcing the return, its cause and its estimated duration in the operator's language pack
  (ADR 0008, AC-35).
