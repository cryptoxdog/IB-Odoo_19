# Slice C — Security Scanner Truthfulness

## Objective

Eliminate the two scoped `SENSITIVE_DATA_LOGGED` false positives by fixing the generic scanner, not application logs.

## Owner

`scripts/audit/security_audit.py`

Scanner tests should live in an existing appropriate test surface if one exists. Create a new test file only if no existing owner can lawfully hold focused audit-scanner regression tests.

## Current defect

The scanner interprets sensitive vocabulary in a logging source line as evidence that a sensitive value is emitted.

This confuses:

```python
_logger.info("api_key configuration is missing")
```

with:

```python
_logger.info("api_key=%s", api_key)
```

## Required implementation

Use Python AST or equivalently structural parsing of log/print calls.

The analysis must distinguish:

1. static literal text;
2. dynamic positional formatting arguments;
3. f-string interpolations;
4. `.format(...)` or `%` interpolation where values are present;
5. variables/attributes with sensitive identifiers being emitted.

## Minimum regression matrix

Must prove:

| Case | Expected |
|---|---|
| literal `"api_key not configured"` | no finding |
| literal `"token rotation required"` | no finding |
| `_logger.info("api_key=%s", api_key)` | HIGH |
| `_logger.info(f"token={token}")` | HIGH |
| `_logger.info("secret=%s" % secret)` | HIGH |
| `_logger.info("secret={}".format(secret))` | HIGH |
| unrelated dynamic value with word `token` only in static prose | no secret-value finding |

Do not special-case the migration path or the `perplexity_api_key` string.

## Expected scoped closure

Both original migration findings disappear with application code unchanged.

## Out-of-scope findings

If the improved scanner reveals actual sensitive logging elsewhere, report exact findings separately. Do not silently add them to this campaign and do not suppress them.
