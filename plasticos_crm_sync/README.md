# plasticos_crm_sync

VanillaSoft is the live CRM provider. Approved contacts stay on the ERP person they already are. Call history has to show on that person after the import, not only sit in a table.

## Operator intent

The ERP import realizes companies, locations, and people as `res.partner`. The approved crosswalk then binds a VanillaSoft contact id to the existing ERP person through `plasticos.crm.external.ref`. That bind does not create another person, a child, a company, or a `crm.lead`.

A `crm.lead` is a pursuit. Unmatched VanillaSoft contacts become leads. When a pursuit already exists for an approved id, `crm.lead.partner_id` points at the same ERP person. Facilities stay on the location through `plasticos.facility.profile`. Supplier status stays `supplier_rank` on the partner.

Every call the provider returns for a contact is stored. A contact with hundreds of logged calls gets one `plasticos.crm.call.event` per call: date, duration, salesperson name, result, and that call's comment. The single VanillaSoft Notes value is appended to `res.partner.comment`. Per-call comments stay on the call rows.

Those rows have to be readable on the ERP person after sync. Storing them without a link the contact form can open does not meet that requirement. The company form does not receive a copy of a child person's calls. Open the person.

## Progress

Module version `19.0.1.9.2` is the code for that link. `19.0.1.9.0` added the person link. `19.0.1.9.1` keeps the exception text on a custom-table warning. `19.0.1.9.2` does not import a second VanillaSoft id for a person the crosswalk already approves, and a crosswalk id whose ERP person was not imported becomes a `crm.lead` with no ERP partner.

In this version:

- `plasticos.crm.call.event.partner_id` and `plasticos.crm.external.table.row.partner_id` point at the ERP person named by the external ref. `lead_id` stays empty on those rows.
- The contact form page **CRM Sync** lists the calls, including the comment, and the custom-table rows.
- **CRM → CRM Sync → Call Events** lists the contact and the comment.
- `migrations/19.0.1.9.0/post-migrate.py` sets `partner_id` on rows already imported, from the external ref. It does not create partners or leads.
- `tests/test_crm_sync_full_import.py` covers a person-bound call and custom-table row, and a lead-only call that stays on the lead.
- A custom-table list or fetch failure logs the `CrmAdapterError` text. The warning is not a substitute for the rows, and the text is not dropped.
- A single-contact bind that does not admit the person keeps the reason on the warning, even when no outcome counter is open. A missing ERP person names the marker, `plasticos_transaction.legacy_erp_contact_<CT_ID>`, and is imported as a `crm.lead` instead of being attached to that missing partner. Four VanillaSoft ids that repeat an already approved active person are dropped before fetch: `1045036935`, `1179868294`, `584402429`, and `585278462`.

The running import is still on the previous code, so the rows it writes have no `partner_id` until this module is upgraded. After that import releases the database:

```bash
make update m=plasticos_crm_sync
```

That upgrade adds the column, loads the contact page, and runs the backfill. Until then the contact form does not show this history.
