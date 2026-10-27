# CRM-3 contact field verdict ledger

Synthetic fixtures only. A `PASS_ENTERPRISE_SYNTHETIC` row is one disposable Odoo readback. It is not the private 763:716 census, a live provider payload, or the 96-field acceptance.

## Revisions

| Role | SHA | What it proves |
| --- | --- | --- |
| Code tested by the receipt below | `6ec2d8e6506784a15a6fe57d926d8af73f413a70` | Person-only call witness and ERP mobile/state/country readback. `dirty=false`. |
| Earlier note-collision behavior | `7a2414c662408955c84118068cfaebad1ba0545e` | 63 Enterprise tests, 0 failed. That receipt does not include the person-only call witness. |
| Docs-only parent of that receipt | `75d20dbfd1fdedf5ab4a45e8fed93a6ab9669e34` | Ledger text only. It did not re-prove the 63 tests. |
| Note-collision fix | `3952de6bff10f4326f7af58ee52f130532a76a7c` | `ALREADY_CLOSED`. No further provenance change in this remediation. |

Module `plasticos_crm_sync` remains `19.0.1.9.6`. No new migration. Staging base `e22eb6c0c34d9ea124ae4a04715f7948c3316d86`. #310 and #311 are already in that base.

A later docs-only commit of this file does not move the code-tested SHA above.

## Enterprise receipt for `6ec2d8e6`

Inspected from `.l9/runtime/test-env/odoo_test_w618609580b.test-receipt.json` after `make test-module m=plasticos_crm_sync`.

| Field | Value |
| --- | --- |
| Database | `odoo_test_w618609580b` |
| Template | `odoo_test_tpl_ee_c9e8a81f52f23680` |
| Fingerprint | `c9e8a81f52f23680595b63d3f5ce3730f95db97195384243ef2fd10b35156c30` |
| Head | `6ec2d8e6506784a15a6fe57d926d8af73f413a70` |
| Dirty | false |
| Tests | 64 run, 0 failed, 0 errors, exit 0 |
| Postgres | 15.19, image `postgres:15` |

The admitted fixture is PostgreSQL 15.19. The broader platform note says PostgreSQL 16. This remediation does not replace the fixture.

GitHub CI is not recorded in this file. Read the checks on the published head.

The new witness in that log is `test_approved_person_without_a_lead_keeps_provider_calls`. `test_orphan_call_resolves_after_contact` and `test_replayed_calls_create_no_duplicate_call_event` attach calls to a **lead**. They are not this person-only proof.

## Ordinary lead path

| Source | Destination | Verdict | Evidence |
| --- | --- | --- | --- |
| Company, First Name, Last Name | `partner_name`, `contact_name`, `name` | PASS_ENTERPRISE_SYNTHETIC | `test_observed_aliases_land_on_native_lead_fields` |
| Address 1 | `street` | PASS_ENTERPRISE_SYNTHETIC | alias test and `test_excluded_source_columns_stay_out_of_every_persisted_path` |
| City, State, Country | `city`, `state_id`, `country_id` | PASS_ENTERPRISE_SYNTHETIC | alias test |
| `zip` / `postal_code` | `zip` | PASS_ENTERPRISE_SYNTHETIC | alias test |
| Literal key `Zip Code` | `zip` | BLOCKED_API_SHAPE | exclusion test sends `Zip Code` `19103` beside `zip` `19019` and reads `19019`. No live provider payload. |
| Email, Direct, US Mobile 1 | `email_from`, `phone`, `mobile` | PASS_ENTERPRISE_SYNTHETIC | exclusion and extra-number tests |
| International mobile | description, not `mobile` | PASS_ENTERPRISE_SYNTHETIC | `test_extra_numbers_and_notes_persist_in_the_description_and_replay` |
| Lead Source | `source_id` | PASS_ENTERPRISE_SYNTHETIC | alias test. Lead path only. |
| Contact Owner | `user_id` via the email-to-login map | PASS_ENTERPRISE_SYNTHETIC | `test_locked_owner_emails_persist_on_the_lead_and_replay`. Lead path only. |
| Notes | ContactID-labelled `description` | PASS_ENTERPRISE_SYNTHETIC | extra-number test |
| Human paragraph equal to the note | paragraph kept, ContactID line added | PASS_PURE_SYNTHETIC | `test_human_paragraph_equal_to_the_note_is_kept_and_still_labelled` |
| Historic unlabelled `VanillaSoft Notes:` | left unchanged | PRESERVED_UNATTRIBUTED | `test_historic_unlabelled_note_is_not_copied_with_a_contact_id`. Not a new ContactID import. |
| Last Result Code | labelled description, not a call | PASS_ENTERPRISE_SYNTHETIC | exclusion test |
| Last Call Date | labelled description, not a call | PASS_PURE_SYNTHETIC | `test_call_and_load_context_is_kept_as_labelled_notes_only_when_present` |
| Notes (MRP/LDPE/HDPE/PP) on a lead | labelled description | PASS_PURE_SYNTHETIC | `test_contact_section_notes_are_labelled_and_pps_notes_stay_off_the_contact` |
| Notes (PPS) | material profile | DEFERRED_CRM4 | absent from the contact |
| Lead-linked call and orphan replay | `plasticos.crm.call.event.lead_id` | PASS_ENTERPRISE_SYNTHETIC | `test_orphan_call_resolves_after_contact`, `test_replayed_calls_create_no_duplicate_call_event`. Not an approved-person proof. |

## Approved ERP person, no lead

CRM values in the synthetic DTO that differ from the ERP person were not written onto the person. The readback is the ERP value.

| Source | Destination | Verdict | Evidence |
| --- | --- | --- | --- |
| Binding | existing `res.partner` via ERP XMLID | PASS_ENTERPRISE_SYNTHETIC | shared-person test; lead count unchanged |
| Name, company `parent_id`, email, phone, street, city, ZIP | unchanged ERP values | PASS_ENTERPRISE_SYNTHETIC | `test_shared_person_attributes_colliding_notes_and_keeps_erp_text` |
| Mobile, `state_id`, `country_id` | unchanged ERP values (`215-555-0140`, Pennsylvania, US) | PASS_ENTERPRISE_SYNTHETIC | same test, against a DTO mobile, NY, and CA |
| Contact Owner | none on this route | BLOCKED_DESTINATION | no person field and no comment substitute. Lead `user_id` remains the approved destination. |
| Lead Source | none on this route | BLOCKED_DESTINATION | no person field and no comment substitute. Lead `source_id` remains the approved destination. |
| Notes, equal text, two ContactIDs | both ContactID lines; ERP paragraph kept | PASS_ENTERPRISE_SYNTHETIC | shared-person test |
| Legacy unlabelled note plus a second ContactID | both labelled; unlabelled line kept | PASS_PURE_SYNTHETIC | `test_legacy_generic_note_does_not_hide_a_second_contact` |
| Section notes and call summaries | ContactID-labelled `comment` | PASS_ENTERPRISE_SYNTHETIC | shared-person test |
| Notes (PPS) | not the person comment | DEFERRED_CRM4 | `PPS-PROFILE-ONLY` absent |
| Enabled mobile and same-digits fax | `plasticos.partner.phone` | PASS_ENTERPRISE_SYNTHETIC | `test_approved_person_keeps_the_erp_phone_and_drops_disabled_numbers` |
| Disabled number | omitted | PASS_ENTERPRISE_SYNTHETIC | same test |
| Provider call before the bind | orphan, then `partner_id` = ERP person, empty `lead_id` | PASS_ENTERPRISE_SYNTHETIC | `test_approved_person_without_a_lead_keeps_provider_calls` |
| Provider call after the bind | same person, empty `lead_id` | PASS_ENTERPRISE_SYNTHETIC | same test |
| Call replay | two events, same comment and phone | PASS_ENTERPRISE_SYNTHETIC | same test |
| Archived or contradictory person ref | no new lead | PASS_ENTERPRISE_SYNTHETIC | `test_persisted_person_ref_is_kept_when_the_crosswalk_is_unset` |
| FCFS / `delivery_term` | untouched | PASS_ENTERPRISE_SYNTHETIC | exclusion test |

## Not accepted

| Item | Verdict |
| --- | --- |
| Private crosswalk `f22c707a…fede2`, 763 ContactIDs to 716 ERP persons | BLOCKED_PRIVATE_CROSSWALK. `test_operator_crosswalk_file_matches_the_pinned_census` skips. The skip is not a pass. |
| Literal `Zip Code` key | BLOCKED_API_SHAPE |
| `errors[].category` versus `contracts/schemas/draft/import-run-summary.schema.json` | Inherited. Not edited. Validator still reports `summary.errors[0]: unexpected field: category`. |
| Material profiles, company tags, lead stages | DEFERRED_CRM4 / CRM-5 |
