# GMP Report 414: Same As Last deal ownership and VanillaSoft field fidelity

PR #414 (`feat/sal-deal-copy-vanillasoft-fields` → `Staging`). Remediation of the
revision-bound focused audit of head `47a8d0c`. Merge is not authorized by this run.

## Phase 0: scope

| Finding | Disposition |
| --- | --- |
| F-001 README versions out of sync (CI red) | Fixed. `module_version` in both READMEs now matches the manifests. |
| F-002 Same As Last makes no transaction | Fixed. See below. |
| F-003 `Fixes #183` unsupported | Fixed in the PR description: `Refs #183`. The freight resolver still refuses a candidate with no booking fingerprint; #183's cold-start decision stays open. |
| F-004 contradictory phone extension silently dropped | Fixed. Raises `CrmAdapterError`, the same per-record failure path as the strict `disabled` parser. |
| F-005 website/function written without #299 evidence | Fixed by deferral. No native write. Values stay ContactID-labelled source text. `#299` is referenced, not closed. |
| F-006 three PET/HDPE aliases unauthorized | Not removed: they are required. The aliases already exist in `material_normalizer._CRM_ALIASES` on `Staging` (#383). `plasticos_crm_sync/tests/test_material_mapping_map.py::test_every_importer_phrase_is_in_the_map` requires each to appear in the map or matrix, and none does on `Staging`. The rows repair that Odoo test. |
| F-007 dedupe and cardinality | Fixed. Open-copy refusal, re-copy after cancel, every PO, every load, zero loads, and a source-row lock. |
| F-008 file inventory in the PR description | Fixed: the description is rewritten from `.l9/pr/pr-intent.json` through `make pr`. |

## Phase 2: implementation

### Same As Last (`plasticos_logistics/models/transaction_inherit.py`)

- One new draft `plasticos.transaction` owns the copy. Its base values come from
  the existing compiler, `sale.order._transaction_vals`. Supplier, carrier,
  product, quantity, unit price, freight rate and delivery term come from the source.
- The copied sale order's `transaction_id` is the new transaction. Before this
  change it kept the source's value (`transaction_id` has no `copy=False`), so a
  later `action_confirm` compiled no transaction for the copy.
- Every source purchase order is copied, with the copied sale order's name as
  `origin`, which is the key `purchase.order.button_confirm` uses.
- One draft load per source load, created with the new transaction as parent:
  same carrier, rate and currency, and no freight provenance.
- `plasticos_automation`'s `approved` flag is reset on the copy when installed.
- An open copy refuses another copy of the same source. A cancelled or completed
  copy does not. The source row is locked and bumped through
  `plasticos.load._touch_membership_epoch`, so concurrent copies serialize.
- The latest completed deal is found with one `limit=1` search instead of a loop.

### VanillaSoft (`plasticos_crm_sync`)

- `compose_phone_number` raises on a contradictory extension. `read_phones`
  keeps disabled entries excluded under both their composed and bare spellings.
- `address2` and the separate extension and country-code folding stay as they were.
- Website and Title are queued as `VanillaSoft ContactID <id> Website|Title: …`
  provenance on the lead and on the approved ERP person. They are idempotent across replays.

## Phase 4: validation

| Check | Result |
| --- | --- |
| `pytest tests/` (pure Python, the CI `pure-python-tests` scope) | 2796 passed, 48 skipped |
| `make audit-baseline` | no new findings |
| `scripts/check_module_wiring.py`, `ci/check_odoo19_xml.py`, `ci/check_circular_deps.py` | pass |
| `ruff check` / `ruff format --check` | pass |
| `plasticos_logistics/tests/test_same_as_last.py` (Odoo `TransactionCase`) | **not run**: this container has no Odoo image, Enterprise checkout or `odoo_test_tpl_ee_c9e8a81f52f23680` fixture |
| `plasticos_crm_sync/tests/test_material_mapping_map.py` (Odoo) | **not run**, same reason |
| Concurrency of two real cursors | **not proven at runtime**. The mechanism is the existing load membership epoch. |

## Residual risk

- Odoo runtime evidence for Same As Last is outstanding. `make runtime-test m=plasticos_logistics`
  on the Enterprise fixture is the proof step.
- #183 and #299 remain open. #299 still needs a redacted live payload census before any native mapping.
