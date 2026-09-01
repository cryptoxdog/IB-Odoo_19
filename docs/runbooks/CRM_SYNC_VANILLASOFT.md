# Runbook — VanillaSoft CRM Sync (`plasticos_crm_sync`)

## Purpose

Live API sync from VanillaSoft (Scrap Management, ProjectID `139705`) into Odoo `crm.lead`, plus call history and custom table rows. HubSpot / Salesforce / Zoho adapters are stubs only.

## Secrets (never commit)

| ICP key | Purpose |
|---|---|
| `plasticos_crm_sync.vanillasoft_api_key` | Project Integration Key |
| `plasticos_crm_sync.vanillasoft_root_endpoint` | e.g. `https://vanillasoft.net` |
| `plasticos_crm_sync.vanillasoft_project_id` | `139705` |
| `plasticos_crm_sync.webhook_token` | Shared secret for Outgoing Web Lead URL |

Configure via **Settings → PlasticOS CRM Sync** or ICP. Rotate any key that was pasted into chat before go-live.

## Install / upgrade

```bash
make update m=plasticos_crm_sync,plasticos_partner_import
```

## Enable sync

1. Set API key + root endpoint + project id in **Settings → PlasticOS CRM Sync**.
2. For a one-shot / manual pull: click **Run VanillaSoft API Sync** (creates the VanillaSoft connection if missing, then runs the same path as Sync Now). Large first runs may be slow.
3. For ongoing sync: CRM → CRM Sync → Connections → enable the VanillaSoft connection, **Test Connection**, then activate cron `PlasticOS CRM Sync (VanillaSoft)` (default `active=False`) or use **Sync Now** on the connection form.
4. Optionally set **Call Backfill Floor (UTC)** on the connection for historical calls.
5. For the initial population of a fresh database, run the manual full import below **first**.

## Outgoing Web Lead (VanillaSoft Admin)

1. Integration → Outgoing Web Lead → enable JSON (or form) post.
2. Posting URL:

   `https://<odoo-host>/plasticos/crm_sync/vanillasoft/weblead?token=<webhook_token>`

3. Expected success response body: `OK`
4. Map ContactID (required) plus any result codes you use for resulted contacts.

Webhook fetches the full contact via API, upserts `crm.lead`, and pulls custom tables for that id.

## Initial population — manual full import (Odoo shell)

> End-to-end test procedure before you run this against real data: [`CRM_SYNC_FULL_IMPORT_E2E.md`](CRM_SYNC_FULL_IMPORT_E2E.md).

`run_connection` is a rolling catch-up: contacts are clamped to the list API's
30-day lookback and calls to a 7-day window. On a fresh database that produces a
partial CRM, not a populated one. `SyncOrchestrator.run_full_import` is the
explicit one-shot bootstrap an operator runs first, from an Odoo shell. There is
no UI, button, menu or cron for it — by design.

```bash
odoo shell -d <database>            # or: docker compose exec web odoo shell -d <database>
```

```python
from odoo.addons.plasticos_crm_sync.services.orchestrator import SyncOrchestrator

connection = env["plasticos.crm.connection"].search(
    [("provider", "=", "vanillasoft")], limit=1
)

# One full import. Both floors are explicit — there is no safe default, so an
# absent, unparseable or future value fails BEFORE any import work begins.
run = SyncOrchestrator(env).run_full_import(
    connection,
    call_history_floor="2019-01-01T00:00:00Z",   # earliest call history to pull
    contact_modified_floor="2019-01-01T00:00:00Z",  # optional; defaults to the call floor
)
print(run.status, run.contacts_upserted, run.calls_upserted, run.error_excerpt)
env.cr.commit()

# Then the ordinary incremental sync — safe and idempotent immediately after.
replay = SyncOrchestrator(env).run_connection(connection)
print(replay.status, replay.contacts_upserted, replay.calls_upserted)
env.cr.commit()
```

Phases, all inside one advisory lock and one `plasticos.crm.sync.run` audit row:

1. a UTC catch-up boundary is captured **before** enumeration;
2. contacts from `contact_modified_floor`, unclamped;
3. call history from `call_history_floor` to that boundary;
4. the ordinary incremental logic, closing the boundary→now window with a
   5-minute overlap so a record mutated during the bootstrap cannot fall into a
   seam.

On success the watermarks are left exactly where `run_connection` resumes.
Every write is keyed on provider identity (`plasticos.crm.external.ref` for
leads, `(provider, external_id)` for calls), so re-running either command
creates no duplicates.

### `status == "partial"` — the census could not be proven

The Contacts list endpoint documents a **31-day** maximum on `modified_after`.
The full import asks for the operator's older floor anyway, because the two
provider behaviours differ sharply: a rejected bound raises and fails the run
with no watermark moved, while a *silently clamped* bound would return only the
last 31 days under a claim of completeness.

The run therefore reports `success` only when it saw at least one contact
modified before that 31-day horizon — proof the older floor was served. When it
did not, the result is genuinely ambiguous (the dataset may hold no contact that
old), so the run is recorded as **`partial`** with the reason in
`run.error_excerpt` and `connection.last_error`, never as `success`.

On `partial`: reconcile the imported lead count against VanillaSoft's own
project contact count before treating the CRM as complete. Contacts untouched
since the horizon may be missing, and no repeat of the command will surface them
through this endpoint.

## Contact history limits

Contacts list API allows `modified_after` **≤ 31 days**. Ongoing sync
(`run_connection`) does rolling catch-up + webhook within that window. Full
historical population is `run_full_import` above, with the completeness caveat
it states. Call history is windowed by `start`/`end` and is fully backfillable.

## CSV deprecation

CRM / PlasticOS menus for “Import CRM Leads (VanillaSoft)” are **removed**. Prefer **Settings → PlasticOS CRM Sync → Run VanillaSoft API Sync**. The CSV wizard remains only for emergency Technical access (no menu). Legacy ERP partner CSV import is unchanged (ADR-003).

## UI fallback

If VerifyKey returns 401/403 after endpoint normalization, use `l9-ui-operator` / Playwright only to recover Admin key access — API remains the primary path.
