# Post-run evidence: ERP contacts, then VanillaSoft crosswalk

Contract revision `daytime-v2`. This pack does not include commercial documents or the 4,113 VanillaSoft IDs outside the crosswalk. Those belong to the overnight pack.

A class name without its reason is not evidence. Copy each distinct `signals` reason into section H. An imported ID that also warned stays imported and stays in section H.

Importer outcomes `created` / `updated` / `unchanged` with a persisted `res.partner` provider ref are imported. An approved miss because the ERP person was excluded or is missing is `held`. `duplicate_rejected`, exceptions, and fetch errors are `genuine_failed`.

> Fill only from actual execution receipts. All `NOT_RUN` values must become observed data or explicit BLOCKED/UNKNOWN. Commit only sanitized facts, no customer PII.

**Observed date/UTC:** NOT_RUN  
**Staging SHA under test:** NOT_RUN  
**Enterprise fixture / owned clone:** NOT_RUN  
**Crosswalk SHA256:** NOT_RUN  
**Final verdict:** NOT_RUN

## Bottom line

Did the clone start with no CRM rows and no commercial documents? UNKNOWN. Were all eligible active ERP contacts imported, with inactive aliases excluded? UNKNOWN. Did `sale.order`, `purchase.order`, `account.move`, and `plasticos.transaction` stay at the fresh-clone baseline? UNKNOWN. Were all 763 crosswalk IDs fetched and classified? UNKNOWN. Did `crm.lead` stay empty? UNKNOWN. Which holds remain? UNKNOWN.

## A. Source and policy checks

| Source census | Observed | Evidence reference |
| --- | ---: | --- |
| Raw ERP source contacts | UNKNOWN | |
| Eligible explicitly active contacts | UNKNOWN | |
| Excluded inactive contacts | UNKNOWN | |
| Active contacts excluded by parent status / placeholder / missing parent | UNKNOWN | |
| Alias CT_IDs pointing at an already created person | UNKNOWN | |
| Active contacts routed to a company phone or a site mailbox | UNKNOWN | |
| Pinned crosswalk VanillaSoft IDs | 763 baseline; VERIFY | |
| Distinct ERP CT_IDs in the crosswalk | 716 baseline; VERIFY | |
| Crosswalk IDs fetched from the live API | UNKNOWN | |

Inactive contact IDs recorded as unresolved, with no XMLID: UNKNOWN.

## B. One clone, three checkpoints

| Checkpoint | Business partners | Contact XMLIDs | Distinct contact partners | `sale.order` | `purchase.order` | `account.move` | `plasticos.transaction` | `crm.lead` | Partner refs | Calls | Evidence |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Before imports | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | |
| After partners-only | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | |
| After crosswalk pass | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | |

The commercial columns must be unchanged across all three rows. Odoo seed partners are not imported counterparties. Record fixture admission, clone ownership, the commit SHA, read-only ERP SQL proof, and the commands with exit codes.

## C. ERP contact import

| Layer | Created | Updated | Unchanged (`skipped`) | Unresolved | Rejected | What unchanged means here |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Counterparties | | | | | | |
| Addresses | | | | | | Folded onto the company and already filled, or a child location |
| Contacts | | | | | | Alias marker, or a non-person / site mailbox |
| Roles | | | | | | |
| Salespersons | | | | | | |

Address split: child locations created UNKNOWN; folded onto the company and updated UNKNOWN; folded onto the company and unchanged UNKNOWN. Markers on companies UNKNOWN. Markers on children UNKNOWN.

Contact split: distinct people created UNKNOWN; alias markers UNKNOWN; non-person or site mailbox UNKNOWN; inactive unresolved UNKNOWN; missing-parent unresolved UNKNOWN. Contact XMLIDs must equal distinct people plus alias markers.

Summary equation closed? UNKNOWN. Validators: UNKNOWN. Inactive contact XMLIDs: UNKNOWN. Commercial documents still at the Gate A baseline? UNKNOWN.

## D. Crosswalk reconciliation (MUST SUM TO 763)

| Result | IDs | Notes |
| --- | ---: | --- |
| Imported, bound to the approved ERP person | UNKNOWN | `created`, `updated`, or `unchanged`, plus one `res.partner` provider ref |
| Held, target excluded or missing | UNKNOWN | Importer `failed` with an ERP-marker miss. No lead |
| Genuine failure | UNKNOWN | `duplicate_rejected`, exception, or fetch error |
| **TOTAL** | **UNKNOWN** | Must equal 763 |

`crm.lead` delta: UNKNOWN. Provider refs on `crm.lead`: UNKNOWN. Both must be zero new rows. IDs fetched that are not in the crosswalk: UNKNOWN. Must be zero.

The 18 rejected links and the 4,095 pending IDs are `NOT_RUN` on this pack. Do not record them as failed.

## E. Approved identity against the previous run

- Pinned digest verified? UNKNOWN.
- Shared alias groups: 45 ERP people / 92 source IDs baseline. Observed duplicate people: UNKNOWN.
- Previous run: 735 bound and 28 `no_erp_person` (27 CT_IDs). This run bound: UNKNOWN. Held: UNKNOWN.
- Each hold classified as inactive contact, inactive or missing parent, or a genuine eligible miss: UNKNOWN.
- Wrong person, a new partner minted for an approved ID, or a shared target duplicated: UNKNOWN.

## F. What this pack does not score

Owner, stage, and polymer oracles apply to `crm.lead` rows. This pack must not create those leads. Leave those scores to the overnight 4,876 pack. Record here only what the bind itself wrote: partner comment notes, added phone lines, call events, and custom-table rows.

| Bind detail | Observed |
| --- | --- |
| Call events stored | UNKNOWN |
| Custom-table rows stored | UNKNOWN |
| Notes appended on the ERP person | UNKNOWN |
| Phone lines added | UNKNOWN |

## G. Evidence manifest

Cite the partners-only summary path, the crosswalk checkpoint path, the clone name, exit codes, and the redacted log. No names, emails, phones, notes, or secrets.

**ERP contact acceptance:** NOT_RUN / PASS / PARTIAL / BLOCKED / FAIL.  
**Commercial documents stayed absent:** NOT_RUN / PASS / FAIL.  
**Crosswalk 763 acceptance:** NOT_RUN / PASS / PARTIAL / BLOCKED / FAIL.  
**`crm.lead` stayed empty:** NOT_RUN / PASS / FAIL.  
**Signals retained:** NOT_RUN / PASS / FAIL.  
**Next one necessary action:** UNKNOWN.

## H. Signals kept

Authority: Quantum-L9/.github `docs/ADVISORY.md`. A finding nobody sees is absent. `unknown_outcome` is not collapsed into imported or into an explained failure.

| Level | Reason | IDs | What it changes |
| --- | --- | ---: | --- |
| WARNING | UNKNOWN | UNKNOWN | Stays on the ID. Does not flip an imported bind to failed |
| ERROR | UNKNOWN | UNKNOWN | Held or genuine_failed, and the reason is the evidence |
| UNKNOWN | outcome produced no reason | UNKNOWN | Not a pass. The runner or the adapter dropped the cause |

Checkpoint rows with no `signals` key (written before `daytime-v2`): UNKNOWN. Those rows are not clean. Distinct reasons must also appear in `receipt.json` `open_exceptions`. An empty `open_exceptions` next to a non-zero held, failed, or warning count fails this section.
