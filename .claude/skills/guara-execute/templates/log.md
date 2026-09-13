# Log <ID>

Executor: cursor/grok · Started: <YYYY-MM-DD HH:MM> · Repo: `<git sha>`
Loop: `/loop 5m` · Iterations: <n>

## Next agent — rewrite this section every iteration

The only section a cold session reads first. It must be true at the moment the iteration ends.

| Field | Value |
|---|---|
| Next task | `T<k>` — <its one-line summary> |
| Its gate | `<command>` |
| Tree state | clean / dirty (`<what is uncommitted and why>`) |
| Last gate run | `<command>` → green / red |
| Do not touch | <paths outside the next task's Files, or "nothing beyond the Read-set"> |
| Watch for | <what bit the previous iteration, or "nothing"> |

## Attempts

| # | Iter | Task | Gate | Result | Output excerpt |
|---|---|---|---|---|---|
| 1 | 1 | T1 | `<command>` | green / red | `<the deciding line>` |

## Files changed

| Path | Task | Kind |
|---|---|---|
| `<path>` | T1 | new / edit |

## Commits

| SHA | Task | Message |
|---|---|---|

## Findings not acted on

| Where | What | Why not acted on |
|---|---|---|

## Blocked

| Task | Gate | Last output (verbatim) |
|---|---|---|
