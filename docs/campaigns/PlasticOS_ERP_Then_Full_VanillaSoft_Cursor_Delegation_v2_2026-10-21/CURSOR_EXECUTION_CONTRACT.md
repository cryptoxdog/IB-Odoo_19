# Cursor execution contract: ERP first, full VanillaSoft CRM second

**Contract ID:** `PLASTICOS-ERP-THEN-VS-FULL-CRM-2026-10-21-v2`  
**Target:** https://github.com/cryptoxdog/IB-Odoo_19  
**Runner:** Cursor on the operator's existing workstation, with the existing Odoo 19 Enterprise Docker fixture, restored ERP SQL database (read-only), and authorized VanillaSoft API access.  
**Starting reference only:** `Staging` at `e78af874604890f8adb6b049694f93c48311eab4`. Rebind to current `origin/Staging`; record the actual SHA under test.  
**Supersedes:** the prior active-only delegation that stopped after a 763-ID mapping pass.

## Outcome

On **one fresh, verified Enterprise Docker clone**, execute the real **two-source bootstrap in order**:

1. **ERP:** import all eligible, explicitly active companies/contacts via the existing direct-SQL, partners-only importer. Do not import inactive people, inactive companies, transactions, or fabricated identities.
2. **VanillaSoft:** with that ERP population now available, ingest the **entire frozen 4,876-ContactID, Flagged=True CRM cohort** through the existing VanillaSoft integration, applying the operator-confirmed identity matrix and the approved field mappings. This is a real CRM write/import into the previously empty CRM, not a read-only analysis and not just a 763-ID crosswalk experiment.
3. **Reconcile:** account for all 4,876 source ContactIDs, exact identity outcomes, CRM lead records, calls, approved field mappings, blocked decisions, exclusions and true defects. Deliver a detailed evidence report plus a machine-readable receipt.

**Meaning of "full":** all 4,876 source IDs in the supplied verified October 13 historical snapshot, plus an explicitly reported assessment of whether the current live provider population contains additions/deletions after that snapshot. An historical source cohort is not, by itself, proof of full current provider history.

## Nonnegotiable boundaries

- **No use of the retired vendor application, UI, proprietary data-export workflow or tooling.** The ERP source is the existing restored read-only SQL database accessed only by the repo's canonical `make import-erp` / projection reader. Never create a second ERP ETL path, use the frozen ERP grid as runtime authority, or mutate the source database.
- **ERP active only.** Existing `10_counterparty.sql` requires `ActiveStatus='A'`; preserve that and its placeholder ID exclusions. `12_contact.sql` presently has no `IsActive` filter. Prove true/false spellings from read-only raw source before adding the smallest source-owned eligibility filter. A blank/unknown flag is not proof of active. Do not materialize inactive CT_IDs, marker aliases, notes or phone enrichment on the fresh clone.
- **CRM cohort eligibility differs.** All 4,876 `Flagged=True` source IDs are in scope **regardless of native Lead Status, ClosedFlag, Unqualified, Do Not Call or Prison classification** under the existing operator decision. Do not confuse a CRM call restriction or lead stage with `ERP Contact.IsActive`. Preserve Do Not Call restrictions, never trigger outbound calls. Do not filter CRM down to only 763 approved people.
- **One disposable test clone.** No hosted Staging/Production/Odoo.sh DB, no production source writes, no SQL changes, no test template replacements, no new private Enterprise mirror.
- **No invoice/order/accounting/document/transaction imports.** Always explicitly set `ERP_PARTNERS_ONLY=1`, with no `LIMIT`; do not run unrestricted `make import-erp` or default `make import-erp-test` (its usual run is sampled).
- **No fuzzy ERP person linking.** Do not promote 4,095 unreviewed CRM source IDs into approved ERP links. The 18 operator rejected suggested links are hard negatives. For all source IDs, preserve provider ContactID as primary identity. Never create or relink an `res.partner` to force a success percentage.
- **No new Odoo fields/models/stages/material masters as a shortcut.** Use current Odoo-native fields, existing provider refs, existing module ownership and approved mapping decisions. Do not treat pending stage mappings or proposed polymer codes as approved. Equipment omitted.
- **Do not run redundant full API replays or broad suite cycles.** One actual full two-stage load, cheap local correctness checks, and targeted replay verification only if needed by a changed invariant.
- Code changes may be made **only where essential** to make the authorized two-stage flow work correctly. One narrow PR to Staging using the repo's `make pr` only if changes occur. No merge or deploy.

## 0. Supplied private input authority: verify before executing

The ZIP includes these exact files in `PRIVATE_INPUTS/`. They are PRIVATE operator inputs and **must not be checked into GitHub**. Keep them outside the repo, or in a verified ignored private runtime folder. Only sanitized counts, proofs and scripts may be committed.

| Input | Purpose | Decision status |
| --- | --- | --- |
| `CRM Leads - VanillaSoft - Scrap-Management(1).csv` | Immutable 4,876-row, 96-field historical CRM snapshot, identity census and ID enumeration | Source evidence, not permission to replace the API importer |
| `PlasticOS_ERP_VanillaSoft_Operator_Confirmed_Crosswalk_2026-10-16.xlsx` | Operator-confirmed CRM/ERP identity decision matrix and complete 4,876-ID classifications | Authoritative for 763 YES, 18 NO, 4,095 PENDING |
| `03_APPROVED_CONTACT_CROSSWALK.csv` | Existing approved-ID file for `plasticos_crm_sync.approved_contact_crosswalk`; generated byte-exact from the matrix | Its SHA256 **must equal** `f22c707a7b6fceba40a20fa393e0c8887e3f05a8d183865ca28f0ccfc16fede2`, the hash pinned in code |
| `VanillaSoft_4876_Field_Mapping_Resolved_Owners_Stage_Review.xlsx` | Exact source-field to Odoo field handling, locked owner email aliases, stage proposals and unresolved gates | Apply LOCKED rules only; STAGE REVIEW proposals are not approved |
| `VanillaSoft_to_Odoo_Polymer_Mapping_Decisions_2026-10-14.xlsx` | Approved/reserved material aliases and polymer decisions, source evidence, unapproved proposals | Apply approved exact/resolved codes only; defer ambiguous or absent masters |

Read `INPUT_MANIFEST.json`; check SHA256 for all five files, exact 4,876 distinct source IDs, all `Flagged=True`, exact operator-decision partition `763 + 18 + 4,095 = 4,876`, and exact crosswalk `763 VS IDs / 716 distinct ERP CT_IDs`. The workbook has 45 ERP people intentionally shared among 92 approved CRM source IDs. Preserve these aliases, never duplicate the person.

Historical CRM snapshot SHA256: `40df04991e9497b3b723e1478f5ea8b1a5dda74e8a052054beb856d81eb942d9`. Treat it as a benchmark for full 4,876-ID coverage, not as a current live API census or as a new direct-CSV importer.

## 1. Gate A: bind Enterprise environment; establish empty CRM baseline

- Rebind repo and inspect current code/manifest/recent merges. Record commit SHA, actual installed modules, current ERP/CRM code revisions and code digests.
- Check the *existing* pinned Enterprise fixture from `config/test_env_fixture.conf` through `scripts/test_env.sh status`. The reference fixture name is `odoo_test_tpl_ee_c9e8a81f52f23680`; require its proved image/Postgres/Enterprise checkout/module fingerprint. Do not replace or build an alternate template to clear drift.
- Create ONE new owned disposable clone via the documented `scripts/test_env.sh clone`/`run` workflow. Record clone identifier and ownership. Do not reuse the earlier October 18 imported clone.
- **Before either import, prove the CRM is empty**: record `crm.lead` row count, source-specific `plasticos.crm.external.ref` count, VanillaSoft sync run rows, CRM call/event and custom-provider-row counts, plus ERP business partner/source-XMLID baseline. An Enterprise fixture may have Odoo seed partners; that is not a CRM import. If the clone has prior CRM source records, replace only your own newly created disposable clone using the guarded workflow; never silently reuse imported state.
- Check the restored ERP SQL database is read-only to the importing principal. Bind the existing VanillaSoft API credentials privately through approved secret management; neither credentials nor full source notes/emails may enter logs, PRs, or receipts.

**Gate A passes when:** one verified Enterprise clone is identified and the *before* inventory explicitly shows no preimported CRM source contacts.

## 2. Gate B: active-only ERP import (first real write stage)

- On read-only ERP SQL, census raw Contact `IsActive` flag spellings, company `ActiveStatus` spellings, parent CpIDs, rejected placeholders, known missing parents and source identities. Determine the explicit true set from observed values; do not assume blank/unknown means active. The active-only policy applies to the ERP partner source, not a CRM lead-stage value.
- Verify `plasticos_partner_import/erp_extracted_data/12_contact.sql` currently selects all rows; minimally correct the canonical projection/reader semantics to select **only explicitly active source contacts** if needed. Keep eligible active company scope exactly as installed. Prevent inactive-only names/aliases, roles, phones and notes from being installed on the clone. Add only the targeted tests necessary for the changed selection, including active and inactive aliases of one person.
- Import the entire eligible, active partner population (five partner tables) from the original read-only SQL source through the repo's existing guarded `make import-erp` path within `scripts/test_env.sh run <owned-clone> -- ...`, explicitly `ERP_PARTNERS_ONLY=1`, `ERP_LIMIT` empty, `ERP_REQUIRE_EMPTY` fail-closed on first load, and `ODOO_DB_NAME` exactly the verified clone. Do not use the sampled `make import-erp-test` or import any deals.
- Capture the five layer validators, source and target counts, contact XMLID/alias census, created/updated/unchanged, policy exclusions separated from genuine invalid references, and before/after target DB identity. Independently reconcile all explicitly eligible active source CT_IDs, accounting for established nonperson/site-mailbox routing rather than counting them as lost people.
- The previous 28 approved links failing `no_erp_person` (27 distinct CT_IDs) were parents missing from the active-company export. Classify **each** using the real read-only parent status and placeholder/missing-parent predicates; do not assume all 28 are inactive or make the parent active just to increase matches.

**Gate B passes when:** the ERP eligible active population is reconciled and persisted to this clone, no intentionally inactive partner/contact or alias was imported, and the mapped ERP people are available for the CRM stage.

## 3. Gate C: the missing step - FULL VanillaSoft CRM import (second real write stage)

**This stage is mandatory and follows the ERP import on the SAME clone. The prior handoff omitted it.**

1. Bind the 763-ID approved crosswalk **before the first CRM contact is written**, using the existing config parameter and the shipped byte-exact CSV. Verify the strict SHA256 and 763/716 population, without editing the matrix. In the same read-only preflight, load the 18 NO decisions and all 4,095 PENDING IDs from the confirmed workbook.
2. The **goal is to ingest all 4,876 `Flagged=True` ContactIDs as actual CRM source records/outcomes**, not merely reconcile IDs in Excel or run the 763 approved matcher. Use the existing VanillaSoft adapter, DTO mapper, orchestrator and provider-identity upsert. Prefer an existing API-supported complete enumeration if proven; otherwise use the **existing ID-based `SyncOrchestrator.upsert_contact_external_id`** for the whole verified 4,876-ID cohort, with one bounded, checkpointed pass. The shipped historical CSV provides the enumerated ContactIDs and audit snapshot, **not** a parallel manual CSV writer to Odoo.
3. Historical full `/Contacts` list queries were observed to fail at more than a 30-day modification floor (HTTP 400). Do NOT run a known-bad 2019 list import repeatedly, secretly clamp the date, or call a 30-day import "full." Single-ID fetch worked on the earlier approved cohort. Before the long pass, verify that the current API can still resolve older source IDs and that real per-ID calls/custom fields are available. If it cannot, stop that path and report the exact blocked cohort; do not fabricate from the CSV.
4. Run **one** full ID-census import with bounded provider request pacing, durable per-ID checkpoints, and resumption only for IDs not yet durably processed. Do not call the provider twice per source ID just to collect a second receipt. Avoid a duplicate entire source import for idempotence; the existing repo already has prior crosswalk replay proof. A targeted read-only database query establishes uniqueness and source coverage.
5. **763 operator-approved YES:** Resolve `plasticos_transaction.legacy_erp_contact_<CT_ID>` to exactly one imported eligible ERP person before an approved link writes. Attach source ID through existing `plasticos.crm.external.ref` as `res.partner`; enrich only by the approved precedence rules (ERP names/relationships/primary contact data win, CRM only supplements approved phones/notes/events). Do not create a duplicate person or unnecessary CRM lead. If an approved target is excluded under active-only ERP policy, do not activate/import it or reassign the ID elsewhere; record the provider ContactID as processed-but-held for identity, with the actual reason. Any decision to create a standalone CRM lead for such an approved-but-unresolvable source is **not** implicit authorization to bypass the locked identity rule.
6. **18 operator NO:** Never link to the rejected ERP CT_ID. Process through the current source-identity-based normal CRM lead path only if it does not guess an ERP partner; report results separately.
7. **4,095 PENDING:** These are NOT approved ERP matches and are NOT pre-certified new real-world people. Their VanillaSoft provider IDs may be represented as Odoo `crm.lead` source records in the existing normal CRM path, but must not be auto-consolidated into an existing `res.partner` or promoted into an approved ERP link by name/email/phone/company. Preserve review status and provenance.
8. CRM cohort is **all 4,876 Flagged=True**, not a status-sliced sample. Include the 1,000 historically Unqualified, 139 Do Not Call and other ordinary source statuses; preserve DNC restrictions and the raw status. Never reclassify "Currently Working With" as Won without its own evidence. Apply Odoo native `crm.stage` only when the exact stage mapping is approved and installed; the supplied `STAGE REVIEW` is a proposal, not authorization. Use existing safe stage handling while retaining the source status. Do not add new stage values/configuration to force coverage.
9. Apply **locked** Contact Owner email-to-existing-active-`res.users` mappings from `OWNER CROSSWALK`, including verified aliases/blank-owner disposition. Verify current user records and do not infer from prospect email or fuzzy name matches. Preserve distinct direct/mobile and extra phone channels. Append CRM notes without erasing ERP notes. Equipment excluded. For materials, use one `plasticos.material.profile.polymer_id` from the approved mappings and current existing masters; no invented polymer/form combinations, no guessed attributes or `OTHER` fallback. Preserve ambiguous material strings for review without creating invalid profiles.
10. Calls, source custom tables, phone lines, notes and provenance must use existing provider-aware behavior. Do not synthesize historical call events from the frozen export's "Last Call Date/Result" summary. Record the actual API coverage for call history and any server/API limit separately from the contact-import census. Current live additions/deletions compared with the frozen 4,876 snapshot are explicit deltas, not silent changes to the target cohort.

**Gate C passes when:** for **every one of the 4,876** frozen Flagged ContactIDs, the persisted clone contains exactly one valid provider-ID target (approved person ref or normal unapproved CRM lead) **or** a named, source-supported held/rejected outcome. Total `bound + created_lead + updated_lead + unchanged + held + genuine_failed` reconciles to 4,876 with each source ID once. `held` and `genuine_failed` are NOT counted as imported. The CRM was initially blank; demonstrate actual new CRM writes.

## 4. Gate D: acceptance and reconciliation

Perform independent **read-only** final inventories, joining the frozen source ContactID set, matrix decisions and Odoo's own source refs, leads, people and call events. Compare preimport vs post-ERP vs post-CRM values. Record separately:

- **ERP coverage:** eligible active companies, active contacts, grouped real people, special nonperson/site routing, aliases, excluded inactive and invalid parents. No leaked inactive CTID record or enrichment.
- **Full CRM coverage:** `4876 = approved(763) + NO(18) + pending(4095)` and separately `4876 = successfully imported/bound + intentionally held + failed`, no duplicate or lost ContactIDs. Report real `crm.lead` count instead of assuming it must equal 4,876: approved existing-person links intentionally do not need lead records.
- **Approved identity:** 763 decisions, 716 distinct CTID targets, 45 intentionally shared ERP people / 92 source IDs; exact bound/held/error counts, no wrong partner or inadvertent new person. Compare previous 735 bound/28 failed baseline but do not force a better percentage by importing inactive records.
- **CRM field completeness:** Contact Owner resolution, native stage/source meaning and review holds, emails and phone/mobile precedence, ERP + CRM note preservation, call events and per-contact source payload outcome, DNC flags, approved polymer/form mapping and 451 multi-material/form records requiring careful disposition. Do not call unknown attributes mapped.
- **History:** clearly separate (a) frozen-source ID census coverage, (b) IDs fetched successfully from current API, (c) any live-provider full-census proof, (d) historical call completeness, (e) Odoo writes. API restrictions and old records unavailable by ID must remain explicitly `PARTIAL` or `BLOCKED`.
- **Integrity:** unique provider ContactID and partner references; no fuzzy crosswalk and no unintended duplicate `res.partner` or duplicate `crm.lead`; only the one disposable DB changed. If a field/owner/stage mapping is pending, retain original value and flag the unmapped field, not whole-contact loss where the existing safe importer supports partial records.

Use actual targeted import/identity checks, no extra full provider replay. Full history acceptance requires source-level coverage evidence; a green CI job or the existence of a sync method is not proof the database is populated.

## 5. Deliverables and publication

Save a sanitized report pack to **`docs/reports/evidence/erp-then-vanillasoft-full-crm-<actual-run-date>/`**:

- `README.md`: complete report using `REPORT_TEMPLATE.md`, actual code SHA, fixture and clone receipts, execution ordering, before/after database counts, source and mapping SHA256s, scope, exact import results, known limitations and verdict.
- `receipt.json`: machine-readable actual run results in the supplied format, with explicit statuses `PASS/PARTIAL/BLOCKED/FAIL/NOT_RUN`; no invented values.
- `erp_active_census.csv`: aggregate disjoint source eligibility and importer dispositions (no customer PII).
- `crm_4876_disposition.csv`: source ContactID, operator decision (YES/NO/PENDING), actual Odoo destination type/ID or hold/error class, provider fetch result, no names/emails/notes.
- `approved_763_link_results.csv`: approved source ContactID and CTID, target status, exact link receipt/error, no names/emails/notes.
- `crm_field_coverage.csv`: mapped/unmapped/held counts by source field, CRM stage and material classification.
- `run_manifest.json`: code + input digests, sanitized command names, execution stage timestamps, exit codes, evidence file checksums and module/fixture identity. Keep raw API payloads/source CSV/operator workbook out of GitHub.

Minimal necessary source fix only: if changed, use repository `make pr` to create **one scoped PR to Staging** containing code and SANITIZED evidence. Do not merge/deploy. If no source change is necessary, produce the local report + receipt without a pointless PR. If any required input/permission/API path is genuinely unavailable, finish a **BLOCKED** report rather than falsely closing the migration.

## Acceptance rules (hard)

1. One verified Enterprise Docker clone used for both **ordered** imports. CRM initial baseline absent/empty is proven before either stage.
2. Applied ERP **partners-only** import covers all eligible active rows; **zero inactive people/companies imported** and **zero financial transactions imported**.
3. Applied full VanillaSoft CRM import attempts all **4,876 Flagged=True source ContactIDs** through the existing provider identity path. It is NOT satisfied by binding 763 IDs only, importing just 30 days, or producing a dry-run mapping matrix.
4. All 4,876 have exactly one classified, evidence-backed outcome; only bound/created/updated/unchanged with valid persisted references count as imported. Held/failed are visible and subtract from the accepted import coverage.
5. 763 approved existing-ERP links remain operator-confirmed; the 18 rejected candidate links never attach; 4,095 pending contacts do not receive guessed ERP identities; approved shared targets never mint duplicates.
6. ERP wins overlap, contact emails/phones and notes preserved by accepted rules, existing Odoo-native stages only, no polymer/master invention; report field-level gaps truthfully.
7. No writes outside the owned clone and no customer PII/source exports in GitHub. One detailed report, one receipt, source-backed exception classification, optional narrowly scoped PR only when essential.

**Agent final message:** a concise table of observed ERP source/import counts; observed CRM 4,876 cohort outcomes; approved/NO/pending breakdown; whether the CRM really started empty and ended populated; genuine blockers and PR URL (if any); location of the report and receipt. Do not claim execution before it happens.

## Repository coordinates to inspect, not blindly invoke

- `scripts/test_env.sh`, `config/test_env_fixture.conf`, `Makefile`
- `plasticos_partner_import/erp_extracted_data/10_counterparty.sql`, `12_contact.sql`, `plasticos_partner_import/erp/source_index.py`, `plasticos_partner_import/models/erp_import_service.py`
- `plasticos_crm_sync/services/approved_identity.py`, `plasticos_crm_sync/services/orchestrator.py`, `plasticos_crm_sync/adapters/vanillasoft/adapter.py`, `plasticos_crm_sync/scripts/import_vanillasoft_shell.py`
- `docs/reports/evidence/crm-erp-approved-identity-2026-10-18/README.md` and `receipt.json`

All code references must be verified at the **current checkout SHA** before implementation or execution. The reference commit above is an observation, not a frozen override.
