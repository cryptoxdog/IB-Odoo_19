# GMP Report C1-C — order delivery default and enrichment ranks

Campaign C1 (contacts / ERP sync realignment), lane C. Branch `feat/c1-order-defaults-enrichment-ranks`, from `origin/Staging` `42db406`.

## Phase 0 — Plan

| # | File | Action | Expected behavior |
|---|---|---|---|
| 1 | `plasticos_logistics/models/delivery_address_default.py` (new) | Insert | Odoo-free selection: newest prior order per customer; use its delivery address only when active, same commercial partner, compatible company |
| 2 | `plasticos_logistics/models/sale_order_inherit.py` | Insert override | `_compute_partner_shipping_id`: `super()` first, then one batch search of non-cancelled history ordered `date_order desc, id desc` |
| 3 | `plasticos_logistics/models/__init__.py` | Insert import | Wire the helper |
| 4 | `plasticos_enrichment/models/enrichment_service.py` | Replace | Entity type from commercial partner `customer_rank > 0` (buyer) else supplier |
| 5 | Manifests + README `module_version` | Bump | logistics 19.0.1.14.26 → 19.0.1.14.27; enrichment 19.0.2.7.0 → 19.0.2.7.1 |
| 6 | `tests/test_c1_order_defaults_enrichment_ranks.py` (new) | Insert | Pure pytest |

## Phase 1 — Baseline

Odoo 19 `sale/models/sale_order.py` (branch `19.0`): `partner_shipping_id` is `store=True, readonly=False, required=True, precompute=True, check_company=True`; `_compute_partner_shipping_id` is `@api.depends('partner_id')` and sets `partner_id.address_get(['delivery'])['delivery']`.

## Phase 2 — Implement

- The override keeps the native single trigger `partner_id`, so an explicit value at create (including the Opportunity hand-off) or a user's later choice is never recomputed.
- Only the most recent other order counts. Archived address, another commercial partner, or another company than the new order → native default.
- One `search_fetch` per batch, `limit=1` when the batch has one customer. The order being edited is excluded through `_origin`.
- Added beyond the brief: the company check, so a last-used address of another company cannot trip `check_company`.
- Enrichment: module-level `_entity_type_from_ranks(partner)`; `run_inference_on_profile` calls it in place of the tag-name rule. Nothing else in the method changed. Note: that method raises `UserError` (mothball M4) before reaching this line, so at runtime the change is dormant until the method is reactivated.

## Phase 3–4 — Enforce / Validate

- `ruff 0.16.0` format + check: clean on all changed Python.
- `pytest tests/test_c1_order_defaults_enrichment_ranks.py tests/test_enrichment_degraded_mode.py`: 24 passed.
- Not run: Odoo runtime / Enterprise install-smoke (owned by Cursor lane T).

## Phase 5 — Recursive verify

Diff touches only the files in the Phase 0 table plus this report. No new field, model, ACL or XML.

## Phase 6 — Finalize

Published with `make pr-nosmoke reason="C1 lane C: Enterprise smoke runs in Cursor lane T"`.
