# Exact ADR dispositions and supersession contract

**Do not modify an accepted ADR merely to make a story tidy.** Keep original status/history and append a narrow, dated approved successor where justified. The following are proposals requiring actual owner admission.

| Current source owner | Path | Disposition | Required action |
|---|---|---|---|
| Odoo | `docs/adr/ADR-012-crm-writeback-allowlist-provenance.md` | **EDIT, P0** | State that the historical auto_writeback=1 default was superseded: current config requires two flags, both OFF; granular reviewer admission is now mandatory for this addon. Preserve 8-field allowlist, merge-not-overwrite and factual provenance. Existing live-mode tests change in step. |
| Odoo | `docs/adr/PROPOSED-enrichment-granular-approval.md` | **CREATE** | Adopt new source-owned ADR for minimal proposal-line, server-side decisions/CAS, ACL, native UI and no automatic CRM writeback. Assign unique final number at adoption. |
| Odoo | `docs/adr/ADR-003-single-external-intelligence-authority.md` | NO_CHANGE | Gate -> EIE/CEG only; no local intelligence fallback and no direct peer requests. |
| Odoo | `docs/adr/ADR-009-enrichment-selection-ranking-not-in-odoo.md` | NO_CHANGE | CEG owns ranking; old Odoo cron remains retired. Do not claim this pack creates a ranked consumer. |
| Odoo | `docs/adr/ADR-010-odoo-consumer-trigger-ownership.md` | NO_CHANGE | Existing manual Odoo trigger remains; no future external queue consumer implemented here. |
| Odoo | `docs/adr/ADR-013-fail-closed-gate-transport.md` | NO_CHANGE | Remove stale log phrase in code only; no exception fallback to local crawl. |
| Odoo | `docs/adr/ADR-017-constellation-enrichment-feedback-channel.md` | NO_CHANGE | Feedback and nightly CEG route remain outside this Odoo work. |
| Odoo | `docs/adr/ADR-015-persistence-shells-matching-enrichment.md` | NO_CHANGE | Retain existing source ownership and use Odoo as persistence/review shell. |
| Odoo | `plasticos_enrichment/migrations/19.0.2.0.0/post-migrate.py` | NO_CHANGE | Keep original historical migration; new corrected upgrade placed in a later installed-version-bound directory. |
| External | EIE, CEG, Constellation.Gate service and SDK ADRs | EXPLICIT NO_CHANGE | Consumer-only source-contract review, not code changes. |

## Specific proposed text for ADR-012

> The historical single-switch writeback default description is superseded. At the current source revision, `plasticos.gate.auto_writeback` and `plasticos.gate.auto_writeback_operator_approved` are both seeded 0; the Gate config requires both to be explicitly enabled to permit the historical live path. Under the newly adopted granular-review policy, `plasticos.enrichment.run` is review-only regardless of these flags, and a current authorized human must accept individual allowed fields before any ORM CRM write. This is not permission to expand the eight-field allowlist or enable automatic enrichment elsewhere. Original historical entries and tests remain traceable; follow-on implementation updates the actual producer/consumer tests to the same current meaning.

**Required preservation evidence:** Accepted law current source hashes in `EVIDENCE/REPOSITORY_REVISION_AND_BLOBS.json`; specific consumed interface changes are in case effects E23/E24 with P05/P25/P28.
