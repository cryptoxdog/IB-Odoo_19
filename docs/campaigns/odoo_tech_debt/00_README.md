# Odoo tech-debt register

This pack is the open-debt record for the two campaigns it replaces:

- `docs/campaigns/odoo_critical_debt_playbook_pack`
- `docs/campaigns/odoo_noncritical_gmp_campaign_pack`

Those packs can be deleted. Closed work is listed under `sealed` so it is not rediscovered as new debt. Open work is one row per site, with the file, line, source line, and the change a coding agent is allowed to make.

Bound subject: `cryptoxdog/IB-Odoo_19` `origin/Staging` `e78af874604890f8adb6b049694f93c48311eab4` on 2026-10-22. The scanners ran on a `git archive` export of that commit, so nothing in the working tree or the current branch was part of the census.

## Files

| File | Role |
|---|---|
| `OPEN_REGISTER.json` | Remediation contract. Schema `plasticos.odoo_tech_debt.open_register.v1`. |
| `OPEN_REGISTER.sha256` | SHA-256 of that JSON, repo-root relative. |
| `OPEN_REGISTER.md` | Same rows, reading order. The JSON wins if they differ. |
| `_build_register.py` | Rebuilds the JSON and the markdown by running the `origin/Staging` scanners on an export of that commit. The census date is the rebuild date. |

Check the hash from the repo root:

```bash
shasum -a 256 -c docs/campaigns/odoo_tech_debt/OPEN_REGISTER.sha256
```

Rebuild only when `origin/Staging` has moved and a fresh census is required:

```bash
python3 docs/campaigns/odoo_tech_debt/_build_register.py
```

## Current work lives elsewhere

Open campaigns are [`workflow_state.md`](../../../workflow_state.md). This register does not copy those campaigns, and the campaigns do not copy these rows. This file remains the debt tracker.

## How an agent uses it

1. Load `OPEN_REGISTER.json`.
2. Keep rows with `"remediate": true`.
3. Take one `recommended_batch` (one file, or one scanner) per change.
4. Obey that row's `action`, `do_not`, and `proof`.
5. Publish with `make pr`.

Rows with `"remediate": false` stay in the file as evidence. They are not a work queue.

## What is still open

250 rows. 115 are allowed to change. The rest are classified so they are not "fixed" by accident.

| Start here | Rows | What to do |
|---|---:|---|
| `real_debt` | 32 | 27 assertion-free tests (`TD-WEAK-*`), one sudo comment on the wrong line (`TD-SUDO-001`), the normalizer log payload that cannot be stored (`TD-DEF-D01`), the CRM webhook token accepted from the query string (`TD-DEF-D05`), and two `tracking=True` fields on models that do not inherit `mail.thread` (`TD-TRACK-001` `plasticos.freight.estimate.status`, `TD-TRACK-002` `plasticos.freight.quote.selected`). |
| `policy_deferred` | 4 | Public methods left by GMP-NC-B: CSV import paths, geo backfill cron, VanillaSoft `action_sync_now`, and `persist_match_lines`. The action on each row is concrete. Confirm the allowed group before renaming or restricting. |
| `documentation_misalignment` | 1 | `web_lead_api.py` class note disagrees with the pre-auth `get_config()` call (`TD-DEF-D06`). |
| `scanner_misalignment` | 7 | `TD-SCAN-001` is the one code change for all 101 `FIELD_NOT_FOUND` rows. `TD-XPATH-001` is a fix string that still recommends a positional `[1]`. The other five are duplicate state checkers and stated limits of the unbounded-search scanner; leave them. |
| `accepted_bounded_debt` | 90 | 76 live HIGH loop-query sites from the 2026-10-10 acceptance, plus business-complete searches and install-hook `sudo()` calls. Fix one `recommended_batch` at a time. Removing a loop must delete that row's `fingerprint` from `ci/baselines/extended_audit_baseline.json` in the same change. |
| `false_positive` | 113 | Nested-view fields, action-record fields, cross-module `_inherit` fields, the commission constraint stub, and searches whose bound the scanner cannot see. Do not edit the application line. |
| `baseline_housekeeping` | 2 | Stale HIGH fingerprints. Safe to prune. They do not fail CI. |
| `evidence_gap` | 1 | Sales-dashboard `sudo()` over Enterprise `documents.document` (`TD-DEF-D07`). Same-line reason is present. Re-check only on an Enterprise database. |

Live scanner counts on that SHA: 77 `N_PLUS_ONE_QUERY` (0 new against the baseline, 2 stale), 27 weak tests, 22 unbounded searches, 1 unjustified sudo, 0 state bypass, 0 sensitive-data logs, 101 field mismatches, 1 constraint mismatch. XPath findings: 0.

Hand-recorded after that census, because the scanners do not inspect field parameters: 2 illegal `tracking` parameters (`TD-TRACK-001`, `TD-TRACK-002`). Both print on every registry load. Remove `tracking=True`. Do not add `mail.thread` to either model. The stored values stay, and the load already audits the outcome.

## Sealed, and not in the work queue

PR #234 closed the eight relationship N+1 paths, load and commission uniqueness, and both High scanners. PR #235 gave weak tests one owner. PR #236 removed the unjustified elevations that campaign found. PR #237 left both state checkers in place because both are silent. PR #240 narrowed the two real partner-import over-fetches and refuses a negative normalizer batch limit. Named XPath anchors replaced the medium notebook findings. GMP-NC-F, the final reconciliation, was never written; this register is that reconciliation.

## Rules carried forward

- Do not add `limit=1` to silence an unbounded search.
- Do not add a field onto the parent model named in a `FIELD_NOT_FOUND` message. Read `scanner_cause` on the row: `nested_subview`, `record_context_bleed`, or `cross_module_inherit`.
- Do not special-case a filename inside `scripts/audit/performance_audit.py` or `scripts/audit/security_audit.py`.
- Do not clear the register in one branch.
- Do not inherit `mail.thread` on `plasticos.freight.estimate` or `plasticos.freight.quote` to silence `tracking`. Remove `tracking=True` (`TD-TRACK-001`, `TD-TRACK-002`).
