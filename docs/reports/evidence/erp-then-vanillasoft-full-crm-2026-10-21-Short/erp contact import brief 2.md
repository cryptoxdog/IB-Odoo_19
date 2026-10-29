The partners-only import on `odoo_test_day1021` finished in 21 seconds. The crosswalk is the process still running after that log.

The lines before the payload are startup, not a failure. `Initiating shutdown` is the shell process stopping its HTTP server because this run is `--no-http`. The two `tracking` warnings are existing logistics fields (`plasticos.freight.estimate.status` and `plasticos.freight.quote.selected`) that Odoo 19 does not treat as a real field parameter. They print on every registry load.

**What was read.** One read-only pass of `erp_SM`: 1,300 companies, 2,968 addresses, 4,084 contacts, 3,108 role rows, 1,058 salesperson rows. That is 12,518 source rows.

**The count closes.** 12,518 seen = 7,679 created + 2,115 updated + 1,432 unchanged + 1,292 rejected. Duplicates are 0. `partial` means those 1,292 rows were refused, not that the arithmetic failed. All five layer validators passed. No sale orders, purchase orders, invoices, or transactions were created. `res.partner` went from 13 seed rows to 5,194. Company markers: 1,300. Contact markers: 3,734.

| Layer | Source | Created | Updated | Unchanged | Refused outside those buckets |
| --- | ---: | ---: | ---: | ---: | ---: |
| Companies | 1,300 | 1,300 | 0 | 0 | 0 |
| Addresses | 2,968 | 1,266 child locations | 1,297 folded onto the company and filled a blank remit field | 39 folded on and changed nothing | 366 |
| Contacts | 4,084 | 2,615 people | 0 | 1,116 | 353 |
| Roles | 3,108 | 2,498 | 0 | 180 | 430 |
| Salespeople | 1,058 | 0 | 818 companies got their default rep | 97 | 143 |

Unchanged contacts are extra `CT_ID`s for a person already created, plus titles that are a phone number or a site mailbox. Those last ones are written onto the company or location and do not become a person. Unchanged addresses are a second remit row for a company whose street, city, zip, phone, and email were already filled.

**The 1,292 refusals are rows whose parent was not in the active company set.** The summary file keeps 1,000 messages and drops the other 292.

| Reason | Stored |
| --- | ---: |
| Address whose company was not active | 366 |
| Contact whose company was not active | 332 |
| Salesperson row whose company was not active | 142 |
| Role whose contact was not imported | 135 |
| Contact with a blank company key | 19 |
| Role with an unresolved rep | 4 |
| Inactive contact, no person created | 2 |

The 366 addresses and all 353 contact refusals are in that file. The 292 messages that were cut off are the rest of the role and salesperson refusals (291 roles and 1 salesperson). The two inactive contacts are `CT_ID` `12250001` and `85100001`.

The three lines naming a person, a contact URL, and a company are the contact validator passing. It found the expected person and confirmed a phone-number title was not stored as a partner.

The partners import did what this pack asks. `partial` is the intended status when source rows are refused and the run itself did not fail.

Every source row is in one bucket. 12,518 seen = 7,679 created + 2,115 updated + 1,432 unchanged + 1,292 rejected, and duplicates are 0. All 1,300 active companies were created. The 1,292 refusals are children of companies that were not in that active set: an inactive or placeholder company, a blank company key, or a role whose contact was not imported. Those rows were not written. The two inactive contacts, `12250001` and `85100001`, have no contact marker. Sale orders, purchase orders, invoices, transactions, and CRM leads are still 0. All five validators passed. The person name and the “has no partner named …” lines are that contact check passing, not a failure.

The two `tracking` warnings are logistics fields Odoo 19 does not accept as a field parameter. They print when the registry loads and they are not part of this import.

The one thin spot is the summary file, not the import. `records_rejected` is the full 1,292. The `errors` list is capped at 1,000 by the shared import-summary contract, so 292 role and salesperson refusal messages are not in the file. The rows are still counted.
