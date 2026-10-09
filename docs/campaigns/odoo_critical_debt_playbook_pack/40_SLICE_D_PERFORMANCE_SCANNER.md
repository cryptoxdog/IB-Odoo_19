# Slice D — Performance Scanner Truthfulness

## Objective

Replace spelling-based N+1 detection with generic structural analysis after the scoped runtime causes have been repaired.

## Owner

`scripts/audit/performance_audit.py`

## Current defects

The current scanner:

- can require literal `self.env` on the ORM-call line;
- misses `self.search(...)`;
- misses model aliases such as `Profile.search(...)`;
- treats `browse()` as if it were inherently a database query;
- conflates query/read and mutation patterns.

## Required architecture

Use AST-based loop/context analysis.

At minimum distinguish these categories:

### Query/read in loop

Potentially includes:

- `search`
- `search_count`
- `read`
- other target-proven ORM read calls

### Mutation in loop

Potentially includes:

- `create`
- `write`
- `unlink`

These should not be mislabeled as N+1 reads. If kept under one audit family, the issue type/message must remain semantically honest.

### Recordset construction

`browse()` alone is not a query and must not generate an N+1 SQL finding merely because it appears in a loop.

## Call-shape recognition

The detector must recognize equivalent model access forms where statically supportable:

- `self.search(...)`
- `self.env["model"].search(...)`
- local aliases assigned from `self.env[...]`
- obvious model variables used consistently in the same scope

Do not attempt heroic whole-program type inference. Unknown forms should remain unknown rather than be guessed into findings.

## Regression matrix

Must include positive and negative fixtures for:

| Pattern | Expected |
|---|---|
| `for x in xs: self.search(...)` | finding |
| alias from `self.env[...]`, alias `.search(...)` in loop | finding |
| `self.env[...].search(...)` in loop | finding |
| `browse(id)` in loop with no field access | no N+1 query finding |
| one batch search before loop, dict lookup inside loop | no finding |
| static list manipulation in loop | no finding |

## Scope control

After implementation run the improved scanner across the repo.

Classify results:

- scoped original findings eliminated;
- same-root latent findings within the already-modified authoritative methods may be closed if necessary for internal consistency;
- unrelated newly visible findings are **reported only**.

Do not add baseline entries automatically for newly exposed findings.
