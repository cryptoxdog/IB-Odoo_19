# F10: inherited residuals and release notes (S6)

None of the S6 proofs found a defect in these residuals, so S6 records them for the final audit and fixes none of them. C06-RECON F10 allows a fix only when a proof shows a defect.

| Residual | Source | S6 observation | Disposition |
|---|---|---|---|
| E7: `trucker_followup` sender fallback | C05 verification | `plasticos_automation` tests pass on the upgraded control clone (m=all). No mail server exists and no `mail.mail` row was produced on the clones (V19). | Record for the final audit |
| Per-wizard composer context key | S4 review nit | No failing test or upgrade effect | Record for the final audit |
| An ordinary user can no longer delete documents | PR #477 note | Intended by S3. Release note below. | Release note |
| D4b: enrichment maps BALE/BALES to the form retired on 2026-11-10 | S6 proof | An extracted "bales" becomes form OTHER, and no packaging Bales is recorded | Business question; the coordinator took it to the operator. Not changed |
| D2b: the front matter of every PlasticOS README is invalid RST | S6 proof | Odoo renders it only when a module has no manifest `description` | Final audit. Not changed |

## Release notes for the Export campaign stack

- **Documents.** `base.group_user` lost `perm_unlink` on `plasticos.document`: in `plasticos_documents/security/ir.model.access.csv`, `access_document_all` went from 1,1,1,1 to 1,1,1,0. `group_documents_manager` keeps it. Documents 19.0.2.1.18 classifies every existing evidence row as `legacy` and leaves provenance unchanged (census digest proof in `L-MIGRATE.json`). Documents 19.0.2.1.19 (S6) reports the legacy rows after that step, and refuses unless they equal the census total.
- **Logistics 19.0.1.14.20.**
  - `plasticos.load.company_id` is now an explicit source company. A legacy load with no company is repaired from its sale order or its parent transaction, and each repair is logged.
  - An ambiguous load, or a load with no source, stops the upgrade before any row changes.
  - Container journey tables start empty.
- **Logistics 19.0.1.14.22 (S6).**
  - A Linda queue claim for no mail is skipped instead of failing in SQL.
  - The acknowledgement escalation job skips loads already escalated today before it takes its page of 100. Newer loads are no longer starved behind 100 older escalated ones.
- **Security Base 19.0.1.2.25.** The load record rule no longer accepts `company_id = False`. The upgrade refuses while any load has no company.
- **Base 19.0.1.1.11.** Retires the attachment-orphan cleanup cron.
- **Export 19.0.1.1.0, then 19.0.1.1.1 in S6, which adds an explicit description for the Apps page.** A new application that is not auto-installed. It adds one active automation, `automation_linda_incoming_booking_reply`, which acts on inbound booking e-mail only. Every existing inactive cron and automation stays inactive (V19).
- **Operator step.** Before the Staging promotion, upgrade from the Staging versions listed in `L-MIGRATE.json` `versions_before`. A supported upgrade starts from Documents 19.0.2.1.17 and Logistics 19.0.1.14.19.
