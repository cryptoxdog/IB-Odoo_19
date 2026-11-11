# Workflow State — PlasticOS (IB-Odoo_19)

Hand-edited operational state, as of 2026-11-08. No script writes this file.

This page keeps three things: unproven acceptance criteria, the revision each proof is bound to, and standing safeguards. The October 21 campaign packs are not current execution instructions. Their SHA pins, private inputs, and clone procedures do not govern a promotion.

`memory-bank/` is retired. Session resume is [l9-graphiti-memory](https://github.com/Quantum-L9/l9-graphiti-memory).

## Unproven acceptance

These are proof gaps. A safeguard that refuses the wrong database is not one of them.

| Criterion | Bound evidence | Still unproven |
|---|---|---|
| Full historical VanillaSoft cohort (4,876 IDs) | [Gate 7](tests/production-rehearsal/evidence/2026-11-08_173212/gate-7.json) at `f8733d213fc96419698b1fd374de5fea54c4d362` created 250 durable references in a rolling window and set `full_cohort_claimed` to false | The complete historical cohort, if go-live requires it |
| Full-volume ERP source resolution | [Gate 6](tests/production-rehearsal/evidence/2026-11-08_173212/gate-6.json) at the same SHA compared 46,886 fields with zero failures | 1,250 attributed unresolved source records remain. The run imported every partner layer and the newest 10% of worksheets (797, plus pinned worksheet 58699 when the source contains it). It does not prove every full-volume record resolves |
| This Staging head | Rehearsal head `f8733d213fc96419698b1fd374de5fea54c4d362`. Observed Staging `b5b6056f01639212e722ccdec5b964b36deee9f5` | The `f8733d2` rehearsal does not authorize `b5b6056f` |
| Web-lead qualification live routing (ADR-016 2026-11-11) | Pure decision tests (`tests/test_web_lead_qualification.py`) and Odoo flow tests (`plasticos_web_leads/tests/test_web_lead_qualification_flow.py`, not executed in the authoring session). `qualification_mode` defaults to `shadow` | A broker-labelled historical corpus, a shadow-period report (`scripts/web_lead_qualification_report.py`) with no go-live blockers, Staging real-provider runs, and an operator decision before switching to `live` |
| Hosted import | `make import-erp` exists. No production permit is recorded here | Source, target, phase, and permit are unauthorized. A disposable-clone rehearsal does not authorize an Odoo.sh write |

## Evidence

| Run | Revision | What it proves |
|---|---|---|
| [Approved identity, 2026-10-18](docs/reports/evidence/crm-erp-approved-identity-2026-10-18/README.md) | `750f9a0` | 735 of 763 approved contacts bound. 28 failed closed because the ERP import had no person for their CT_ID. CRM replay wrote nothing. A later ERP replay left that state byte-identical. An earlier crosswalk and revision. Not 763/763, and the final CRM replay after the ERP replay was not executed |
| [Rehearsal verdict, 2026-11-08](tests/production-rehearsal/evidence/2026-11-08_173212/verdict.json) | `f8733d213fc96419698b1fd374de5fea54c4d362` on `fix/rehearsal-evidence-20261108` | Seven gates passed, including the ERP slice and the rolling VanillaSoft window above. Verdict `ready` is for that SHA |
| [Install-smoke, 2026-11-08](tests/production-rehearsal/evidence/2026-11-08_173212/03-install-smoke.txt) | same SHA | `l10n_us`, `l10n_us_account`, `l10n_us_1099`, `l10n_us_reports`, `l10n_us_check_printing`, and `l10n_us_payment_nacha` loaded. Satisfied on that run, not six open defects |

Mack PR #197 merged into Development on 2026-11-08. That merge is not an import item and it is not on Staging.

## Standing safeguards

These stay. They are not debt.

- ERP historical import is `make import-erp`. The contract is [ADR-021](docs/adr/ADR-021-erp-sql-crm-api-import.md) and `plasticos_partner_import` (`erp/mapping.py`, `erp/mapping_status.py`, `erp/reader.py`).
- The empty-partner guard refuses a first import onto a database that already has business partners. `ERP_REQUIRE_EMPTY=0` is the deliberate second-phase switch. Partner and commercial phases each take their own one-use permit.
- The database check still requires the six USA localization modules before an import. The November 8 smoke loaded them. The check remains.
- Odoo.sh Connect values live in `.env.local` (`ODOO_SH_STAGING_SSH`, `ODOO_SH_STAGING_URL`). Build ids rotate. Build `36099032`, still named in `.cursor/rules/98-odoo-sh-staging.mdc`, must not be used.
- **Allow my IP** lasts one hour. It is an operational prerequisite, not a standing firewall entry.
- A census stays `BEGIN READ ONLY` … `ROLLBACK`.
- `make import-erp` stays off Odoo.sh until a separate authorization. Merging Staging into Production transfers code, not a Staging database's imported rows.

## Accepted decision

`plasticos.material.profile.sub_grade` is a free `Char`, hidden on the form, with `TODO: Define sub-grade logic`. The letters A, B, and C are literals in `plasticos_material_profile/models/material_normalizer.py` and are copied onto that field. There is no grade master for them. Accepted 2026-11-04; no grade master is added for this.
