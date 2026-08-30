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

## Outgoing Web Lead (VanillaSoft Admin)

1. Integration → Outgoing Web Lead → enable JSON (or form) post.
2. Posting URL:

   `https://<odoo-host>/plasticos/crm_sync/vanillasoft/weblead?token=<webhook_token>`

3. Expected success response body: `OK`
4. Map ContactID (required) plus any result codes you use for resulted contacts.

Webhook fetches the full contact via API, upserts `crm.lead`, and pulls custom tables for that id.

## Contact history limits

Contacts list API allows `modified_after` **≤ 31 days**. v1 does rolling catch-up + webhook; it does **not** claim a full historical contact census via list API. Call history is windowed by `start`/`end` and is fully backfillable.

## CSV deprecation

CRM / PlasticOS menus for “Import CRM Leads (VanillaSoft)” are **removed**. Prefer **Settings → PlasticOS CRM Sync → Run VanillaSoft API Sync**. The CSV wizard remains only for emergency Technical access (no menu). Legacy ERP partner CSV import is unchanged (ADR-003).

## UI fallback

If VerifyKey returns 401/403 after endpoint normalization, use `l9-ui-operator` / Playwright only to recover Admin key access — API remains the primary path.
