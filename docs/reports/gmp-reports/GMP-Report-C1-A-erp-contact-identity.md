# GMP Report C1-A — ERP contact identity

Campaign C1 (PlasticOS contacts / ERP sync realignment), lane A.
Branch `fix/c1-erp-contact-identity`, from `origin/Staging` `42db406`.

## Phase 0 — Plan

Objective: one real human at an ERP counterparty becomes one `res.partner` with all
roles and sites; role mailboxes stay; no weak-name clutter; sales-rep mailboxes never
reach Odoo.

Scope (lane-owned files only):

| File | Action |
|---|---|
| `plasticos_partner_import/erp/mapping.py` | add `clean_emails`, `email_cell`, `phone_digits`, `is_role_word`, `weak_name_kind`, `email_prefix_title`, `first_word_key` |
| `plasticos_partner_import/models/erp_import_service.py` | weak-row fold in `_import_contacts`; `_import_person` takes `folded` + `name`; anchor from full-name rows only; `_retire_superseded_partner` archives only when no contact marker remains; every email write through `_email` → `mapping.email_cell` (counterparty `APEMail` included) |
| `plasticos_partner_import/__manifest__.py`, `README.md` | version `19.0.2.10.39` → `19.0.2.10.40` |
| `docs/erp_import_mapping.md` §5 | R1–R3, replay, email order |
| `tests/test_erp_contact_identity.py` | new, pure pytest |

Not touched: `models/partner_import_service.py`, `models/validation.py`, wizards.

## Phase 1 — Baseline

`pytest tests/test_erp_*.py tests/test_pristine_runtime_seams.py tests/test_import_summary_schema.py`
→ **395 passed**. `tests/test_legacy_import_ui_retired.py` does not collect in this
container (`defusedxml` not installed); environment defect, unrelated, not changed.

## Phase 2 — Implement

- R1 `mapping.weak_name_kind`: `blank`, `role`, `email_prefix`, `first_name`, or `None`
  (full name, multi-person titles included).
- R2/R3 `_fold_weak_rows` (module function in the service): per company, index the
  full-name groups by phone digits and cleaned addresses; a weak row folds when the
  union of hits is exactly one group; disjoint phone/email hits → `alias conflict`;
  any other count → `alias ambiguous: N full-name candidates`. A plain first name is
  restricted to groups with that first word.
- Folded rows alias the person; channels, sites, notes and roles union onto it;
  name and anchor come from the full-name rows only (`_anchor_contact_id(own)`).
- Blank rows are rejected only when they do not fold.
- Replay: `_alias_xmlid` re-points the marker; `_retire_superseded_partner` archives
  the old partner only when `_named_by_contact_marker` finds no remaining
  `legacy_erp_contact_%` marker.
- Email: `mapping.email_cell` = drop internal mailboxes → split `;`/`,`, trim, drop
  empty / non `local@domain.tld`, lower-case, de-dup → join `", "`. Site-mailbox first
  address now splits on `,`.

Decision recorded during execution: R3 says an unfolded e-mail-prefix name is
title-cased. A role mailbox titled `AP` with `ap@…` is an e-mail prefix, and
title-casing renamed it `Ap`, which damaged test 2. Only a prefix written in lower
case (an address local part) is title-cased; a title with capitals keeps its
spelling. Documented in §5.

Zero-candidate weak rows also report `alias ambiguous: 0 full-name candidates`,
per the lane brief ("Zero / two+ candidates … report.anomaly"). This is a
diagnostic only; counts are unaffected.

## Phase 3 — Enforce

- `ruff check` / `ruff format --check` (0.16.0): clean.
- `python3 scripts/check_module_wiring.py`: passed.
- No new field, model, or dependency.

## Phase 4 — Validate

`pytest tests/test_erp_contact_identity.py tests/test_erp_*.py tests/test_pristine_runtime_seams.py tests/test_import_summary_schema.py tests/test_repo_dependency_integrity.py`
→ **431 passed** (395 baseline + 27 new + 9 from the dependency-integrity module).

New tests (brief numbering): 1 Sky shape · 2 role mailbox · 3 multi-person e-mail
prefix fold · 4 unmatched prefix → own title-cased card · 5/6 shared phone / email
stay two · 7 ambiguous first name · 8 conflict · 9 internal mailbox never matches ·
10 `+1 (980)` vs `980-` · 11 blank folds, not rejected (+ unfolded blank still
rejected) · 12 replay 0 created / 0 updated, old split archived with markers on the
survivor (+ a partner still named by another marker stays active) · 13 summary
balance, duplicates 0 · 14/15 `APEMail` and contact email cleaning, internal-only →
no email · R1 kind table.

Not run here: Odoo Enterprise runtime / install-smoke (lane T owns it).

## Phase 5 — Recursive verify

Diff stays inside the lane-owned file list. Existing contract tests (alias,
retire-by-archive, internal-mailbox seam, two `_retire_stale_contact` calls) pass
unchanged.

## Phase 6 — Finalize

Residual risk: the fold is unproven against the restored SQL Server source; the
`alias ambiguous` count on a real run is the evidence to review. Real restored-SQL →
Odoo replay is required before claiming source accuracy (CLAUDE.md, ERP Historical
Import Law).

## Corrective run 2 (2026-11-17) — fold carries what names the superseded card

Finding (CTO review): archiving a folded card left a VanillaSoft lead, its material profiles
and facility profile on an archived partner.

- `_retire_superseded_partner` now calls `_repoint_superseded` before archiving: it moves
  `crm.lead.partner_id`, `plasticos.material.profile.partner_id` and
  `plasticos.facility.profile.partner_id` (each guarded by `"<model>" in self.env`, no new
  dependency) and adds the superseded card's `location_partner_ids` to the survivor. A profile
  that would duplicate one the survivor holds is not moved; the old card then stays visible.
  Never deletes. Moves and refusals are `fold re-pointed …` / `fold kept … visible` anomalies.
- `_import_person` site sync is additive (`(4, id)`), so carried-over or hand-linked sites
  survive replay.
- Tests: lead + material + facility + hand-linked site end on the survivor and replay writes
  nothing; a clashing material profile keeps the old card visible; without the CRM/profile
  modules the fold still archives.

Earlier on the same day, corrective run 1 made `_sync_phone_lines` compare `(label, phone
digits)` so a reformatted number is not re-added.

## Corrective run 3 (2026-11-17) — retire paths without a survivor

`_retire_stale_contact` and `_retire_inactive_contacts` archive a person that has no surviving
person. They now call `_repoint_retired` first (shared `_repoint_records` machinery):
`crm.lead` → the person's company (ADR-131 owning company, local predicate); material and
facility profiles → the single linked site, else the company when it has no site, else no
target. No target, or an equivalent profile already on the target, keeps the person visible
(`retire kept … visible: profiles need a site` / `… already holds …`). A person that nothing
names is archived exactly as before. Report lines now name each move's target
(`… re-pointed: <model> <n> -> partner <id>`). Tests: one test per branch (one site,
company without sites, company with sites and no link, several sites, equivalent profile,
nothing names the person, stale non-person row) plus replay. Partner-import suite: 489 passed.
