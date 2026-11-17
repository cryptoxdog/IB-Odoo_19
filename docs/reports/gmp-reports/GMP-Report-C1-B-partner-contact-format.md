# GMP Report — C1 lane B: partner contact format

- Campaign: C1 (PlasticOS contacts / ERP sync realignment), lane B
- Branch: `fix/c1-partner-contact-format` (from `origin/Staging` `42db406`)
- Module: `plasticos_facility_profile` `19.0.5.4.15` → `19.0.5.4.16`

## Phase 0 — Plan

Objective: every phone and email stored on `res.partner` and on its phone lines
(`plasticos.partner.phone`) is in one format, whatever wrote it (ERP import,
VanillaSoft, manual edit).

Scope (lane contract): new files only in `plasticos_facility_profile`, plus
`__manifest__.py`, `models/__init__.py`, the README version line, a new
migration folder and new tests. `models/res_partner.py`, `models/partner_phone.py`
and every view are untouched.

## Phase 1 — Baseline

- `res.partner.mobile` is a computed projection of the `mobile` phone line
  (`_compute_mobile` / `_inverse_mobile` in `models/res_partner.py`), so
  formatting `plasticos.partner.phone.number` also formats the mobile.
- `plasticos.partner.phone` has `unique(partner_id, label, number)`.
- `phone_validation` is not a dependency of this module and Odoo source is not
  on this machine, so Odoo's `_phone_format` API was not confirmed and is not
  used. The helper uses the `phonenumbers` library (the library that
  `phone_validation` wraps) through a lazy optional import for non-NANP
  numbers, and a deterministic digit formatter for NANP. No pip dependency was
  added.

## Phase 2 — Implement

| File | Change |
|---|---|
| `services/contact_format.py` | New pure helper: `format_phone`, `format_phone_result`, `format_emails`, `format_emails_result`. No Odoo import. |
| `services/__init__.py` | New package init. |
| `models/res_partner_contact_format.py` | `_inherit res.partner`: formats `phone` / `email` in `create` and `write` before the row is written. Country: the partner's, else its parent's, else US; a multi-record write is grouped by country. Unparseable phones and dropped email entries are logged once per call at INFO. |
| `models/partner_phone_contact_format.py` | `_inherit plasticos.partner.phone`: formats `number` in `create` / `write` with the partner's country (covers `mobile`). |
| `models/__init__.py` | Imports the two new model files. |
| `migrations/19.0.5.4.16/post-migrate.py` | Reformats stored partners and phone lines in batches of 1000 ids, tracking and mail notifications disabled, inactive rows included. Writes only rows whose value changes. A phone line whose formatted number duplicates another line of the same partner and label is removed (same number twice; keeps the unique constraint). Logs formatted / unchanged / unparseable / invalid_email_dropped / duplicate_lines_removed. |
| `__manifest__.py`, `README.md` | Version `19.0.5.4.16`. |
| `tests/test_partner_contact_format.py` | New pure pytest file. |

Rules:

- NANP (`US`, `CA` and the other `+1` countries, or any `+1` number):
  `(XXX) XXX-XXXX`, extension ` x123`. Area code or exchange starting 0/1 is
  not a valid NANP number and is left unchanged.
- Other numbers: international `+CC ...` through `phonenumbers` when importable;
  without it, a `+` number keeps its digits with spacing collapsed.
- Unparseable, blank, `NULL`: returned unchanged (stripped).
- Emails: split on `;` / `,`, strip, extract `<addr>` when present, lowercase,
  keep `local@domain.tld` only, de-duplicate keeping the first, join `", "`.
  No domain is ever removed.

## Phase 3 — Enforce

- `ruff 0.16.0` check + format: clean.
- `pre-commit run --files <changed>`: all hooks passed.
- `scripts/check_module_wiring.py`, `ci/check_circular_deps.py`: pass.

## Phase 4 — Validate

- `tests/test_partner_contact_format.py`: 39 passed without `phonenumbers`,
  39 passed with `phonenumbers` installed (both code paths).
- Full pure suite `pytest tests/`: the first run had 1 failure,
  `test_phantom_enum_values[plasticos_facility_profile]`, which flagged the
  migration's counter dict literal keys as phantom enum values. The migration
  now uses `collections.Counter`, no literal keys, and the test is unchanged.
  Re-run: `tests/test_phantom_enum_values.py` + the new file, 93 passed. The
  full run had 3575 passed and 49 skipped.
- Not run here: Odoo runtime / Enterprise install-smoke (owned by Cursor lane T).
  The model overrides and the migration are proven only by the runtime gate.

## Phase 5 — Recursive verify

No file outside the lane contract was changed. `models/res_partner.py`,
`models/partner_phone.py` and the views are untouched.

## Remediation: Production probe 3 tuning (operator 2026-11-17)

Probe facts:

- 7,129 phone values: 6,340 NANP, 756 already `+international`, 24 international without "+".
- 27 values sit on partners with no country.
- 4 values are unparsed, and 203 have an extension.

Changes:

1. **Country:** the partner's country, else its commercial company's (for a child, the parent's commercial company), else US.
   - One pure helper, `country_for`, holds the rule.
   - The partner create/write path (ERP import, VanillaSoft sync, manual save), the phone-line path and the post-migrate all use it.
2. **Everything else is unchanged.** No trailing-extension handling and no special case for a foreign number with no country (CTO correction 2026-11-17: the 7 values involved are not worth code). An unparsed value stays unchanged, as before.

Tests: the country rule. `tests/test_partner_contact_format.py`: 41 passed (39 + 2 country tests).

Version: kept at 19.0.5.4.16. That version is unreleased, and its post-migrate imports the formatter, so the tuned rules run on upgrade. The stacked #524 already uses 19.0.5.4.17 (version and migration folder), so a bump here would collide when the stack merges bottom-up.

## Phase 6 — Finalize

Residual risk:

- Formatting a non-NANP number without a `+` needs `phonenumbers` at runtime.
  Without it the number is stored unchanged and counted as unparseable.
- A `not-an-email` value becomes empty: the email field is cleared, as specified.
