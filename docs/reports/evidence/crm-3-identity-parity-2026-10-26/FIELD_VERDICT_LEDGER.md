# CRM-3 contact field verdict ledger

PII-free. Synthetic fixtures only. A skipped private file is not acceptance.

| Item | Value |
| --- | --- |
| Behavior SHA | `7a2414c662408955c84118068cfaebad1ba0545e` |
| Module | `plasticos_crm_sync` `19.0.1.9.6` |
| Parent of this repair | `9e0ad87c68edaad484c6d6f7caab03edb2e37ec5` |
| #311 ancestor | `db03f21bdd3db2fcabc26e12536763b7bd3120ae` |
| Staging | `e22eb6c0c34d9ea124ae4a04715f7948c3316d86` |
| Migration | `19.0.1.9.4` upgrade script kept; no new migration folder |

## Enterprise receipt

Command: `make test-module m=plasticos_crm_sync`  
Database: `odoo_test_w618609580b` (clone of the admitted template, not a new template)  
Template: `odoo_test_tpl_ee_c9e8a81f52f23680`  
Fingerprint: `c9e8a81f52f23680595b63d3f5ce3730f95db97195384243ef2fd10b35156c30`  
Postgres: 15.19 (image `postgres:15`)  
Head: `7a2414c662408955c84118068cfaebad1ba0545e`  
Dirty: false  
Tests: 63 run, 0 failed, 0 errors, exit 0  
Scope: `plasticos_crm_sync`  
Upgraded roster: the 25 declared PlasticOS modules, including `plasticos_crm_sync`

The new readbacks that ran in that receipt are `test_shared_person_attributes_colliding_notes_and_keeps_erp_text`, `test_approved_person_keeps_the_erp_phone_and_drops_disabled_numbers`, and the name/city assertions in `test_observed_aliases_land_on_native_lead_fields`.

## Ordinary lead path (`crm.lead`)

| Source | Destination | Verdict | Evidence |
| --- | --- | --- | --- |
| Company | `partner_name`, lead `name` | PASS | `test_observed_aliases_land_on_native_lead_fields` |
| First Name + Last Name | `contact_name`, lead `name` | PASS | same test |
| Address 1 | `street` | PASS | same test (`address1`) and `test_excluded_source_columns_stay_out_of_every_persisted_path` (`Address 1`) |
| City | `city` | PASS | alias test |
| State | `state_id` | PASS | alias test and `test_extra_numbers_and_notes_persist_in_the_description_and_replay` |
| Zip / postal_code | `zip` | PASS | alias test |
| Zip Code (literal key) | `zip` | BLOCKED | exclusion test sends `Zip Code` `19103` beside `zip` `19019` and reads `19019`. The adapter does not map the literal `Zip Code` key. Not claimed imported. |
| Country | `country_id` | PASS | alias test, code `US` |
| Email | `email_from` | PASS | exclusion test |
| Direct | `phone` | PASS | alias, extra-number, and exclusion tests |
| Mobile 1 (US 10-digit) | `mobile` | PASS | alias and extra-number tests |
| International mobile | description, not `mobile` | PASS | extra-number test |
| Lead Source | `source_id` | PASS | alias test; unmapped text stays in the description (`test_unmapped_source_falls_back_to_other_and_keeps_the_source_text`) |
| Contact Owner | `user_id` via email-to-login map | PASS | `test_locked_owner_emails_persist_on_the_lead_and_replay`, blank owner, unresolved owner does not clear the existing user |
| Notes | `description`, ContactID label | PASS | extra-number test; human paragraph equal to the note is kept and labelled (pure `test_human_paragraph_equal_to_the_note_is_kept_and_still_labelled`) |
| Last Result Code / Last Call Date | `description`, ContactID label, not a call event | PASS | exclusion test reads the result-code line; call-summary pure test covers the date. Neither creates `plasticos.crm.call.event`. |
| Notes (MRP/LDPE/HDPE/PP) | `description`, ContactID label | PASS on the pure lead harness | `test_contact_section_notes_are_labelled_and_pps_notes_stay_off_the_contact`. The Enterprise readback of these four lines is on the approved-person comment, below. |
| Notes (PPS) | material profile, not the contact | NOT IMPORTED | token absent from the contact. CRM-4. |
| Historic unlabelled `VanillaSoft Notes:` on a lead | left unchanged | PASS | `test_historic_unlabelled_note_is_not_copied_with_a_contact_id` |

## Approved ERP person path (`res.partner`, no new lead)

| Source | Destination | Verdict | Evidence |
| --- | --- | --- | --- |
| Binding | existing ERP person via XMLID | PASS | shared-person test; lead count unchanged |
| Name, company parent, email, phone, street, city, ZIP | unchanged ERP values | PASS | shared-person test |
| Notes colliding with an ERP paragraph | ERP paragraph kept; `VanillaSoft ContactID <id> Notes:` added | PASS | shared-person test and pure `test_erp_authored_paragraph_is_not_this_contacts_imported_note` |
| Second ContactID, same note text, legacy unlabelled line present | both ContactID lines stored; unlabelled line not rewritten | PASS | pure `test_legacy_generic_note_does_not_hide_a_second_contact`; Enterprise shared-person test stores both ContactID lines |
| Replay | no second copy | PASS | both tests |
| Notes (MRP/LDPE/HDPE/PP), Last Result Code, Last Call Date | `comment`, ContactID label | PASS | shared-person test |
| Notes (PPS) | not the person comment | NOT IMPORTED | `PPS-PROFILE-ONLY` absent. CRM-4. |
| Direct already on `phone` | not duplicated; `phone` not overwritten | PASS | phone-line test |
| Mobile 1 | `plasticos.partner.phone` label `mobile` | PASS | phone-line test |
| Same digits as fax | separate `fax` line | PASS | phone-line test |
| Disabled Home | omitted | PASS | phone-line test |
| Call events | provider-stable `plasticos.crm.call.event` | PASS | `test_orphan_call_resolves_after_contact`, `test_replayed_calls_create_no_duplicate_call_event` |
| Archived person / contradictory ref | no new lead, no rebind | PASS | `test_persisted_person_ref_is_kept_when_the_crosswalk_is_unset` and the pure duplicate-ref tests |
| FCFS / `delivery_term` | untouched | PASS | exclusion test sets `fcfs` and reads it back after replay |

## Explicitly not PASS

| Item | Verdict |
| --- | --- |
| Private crosswalk `f22c707a7b6fceba40a20fa393e0c8887e3f05a8d183865ca28f0ccfc16fede2`, 763 ContactIDs to 716 ERP persons | BLOCKED_PRIVATE_CROSSWALK. `test_operator_crosswalk_file_matches_the_pinned_census` skips when the file is absent. The skip is not business acceptance. |
| Literal source key `Zip Code` | BLOCKED. No live provider payload in this run maps that key. |
| `build_run_summary` error `category` vs `contracts/schemas/draft/import-run-summary.schema.json` | Inherited upstream blocker. Probe on this tree: `final_status` `partial`, validator `summary.errors[0]: unexpected field: category`. Not patched here. |
| Material profile, PP Supersacs notes, Buyer/Supplier tags, stage policy | CRM-4 / CRM-5. Not claimed by this ledger. |
