# Packet <ID>

State: READY
Thread: core | A | B | C | S | K
Opened: <YYYY-MM-DD>

## Question

<one sentence>

## Hypothesis

<expected answer, refutable>

## Falsifier

<the observation that kills it>

## Grounding

| Claim | Evidence | Confidence |
|---|---|---|
| <claim> | `repo@commit:file:line` | HIGH / MEDIUM / UNKNOWN |

## Non-goals

- <what this packet must not touch>

## Tasks

```
T1 · <imperative summary>
  Files:     <paths>
  Depends:   none
  Do:        <2-6 imperative lines>
  Gate:      <command>
  Done-when: <observable in the output>
```

## Gates

```bash
<verbatim commands, in run order>
```

## Evidence

| Artifact | Path |
|---|---|
| run | `results/<run>` |
| published | `docs/evidence/<stamp>_<name>` |

## Acceptance

| AC | Claim | Verifying command |
|---|---|---|
| AC-<n> / new | <claim> | `<command>` |

## Invariants

| # | Mark | Why |
|---|---|---|
| Q1 | HOLDS / VIOLATED / N/A | <one clause> |
| Q2 |  |  |
| Q3 |  |  |
| Q4 |  |  |
| Q5 |  |  |
| Q6 |  |  |
| Q7 |  |  |
| Q8 |  |  |
| Q9 |  |  |
| Q10 |  |  |

## Risks

| Risk | Fallback |
|---|---|
| <what breaks> | <cheaper path> |

## Deltas

<empty until a CHANGES review appends here>
