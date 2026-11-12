# S9 evidence: Logistics facts for the deferred Export rules

Contract `PLASTICOS-EXPORT-C10-S9-LOGISTICS-FEATURES` (sha256 `5b18a582…`), amended by coordinator C10-SCOPE-2 (`6ba954c8…`) and C10-SCOPE-3 (`a5fe52cf…`), C10-STACK-BIND (`63a0e3c2…`) and C10-SCOPE-4 / C10-Q2 (`48f12428…`, the binding digest). Base `6c7789ef` (the accepted S8 head, C10-STACK-BIND); the branch was started at `ff42df2d`. Predecessor `feat/plasticos-export-s8-coverage` merged in with merge commits (no conflicts): `3fda2e04`, then the accepted head `6c7789ef`. This folder holds no Odoo logs and no real data.

| File | Contents |
|---|---|
| `S9_RULE_WITNESSES.csv` | Every S9 rule and each positive and negative witness (`file::Class::method`) |

## Ownership decisions

| Fact | Owner | Why |
|---|---|---|
| Domestic road equipment (53 ft, 48 ft, flatbed, more as data) | `plasticos.road.equipment.type`; the load names it in `road_equipment_type_id` and states the actual move in `road_equipment_requirements` | One Logistics catalog (BRS-EXP-07-R002). It is not `plasticos.equipment.type` (facility processing equipment) and not J1 `equipment_class`. Nothing is inferred from it. |
| Gate-in, departure, customs filer, delivery partner, container tare, VGM weight | `plasticos.iso.journey.fact`, an append-only Logistics ledger beside J1: one row per (journey, kind), written only by its record commands from verified evidence | J1 is the physical container cycle, independent of any sale order or buyer, so a resale cannot reach these facts (BRS-EXP-08-R007). Putting the fields on J1 itself would break the locked S2 witness `test_iso_journey.py::TestIsoJourney::test_registration_records_no_booking_or_milestone` and the frozen J1 shape, so J1 stays identity only (coordinator-approved amendment). This is a Logistics extension beside J1/J2, not a change to the Export six-model contract. |
| Typed shipment events (supplier ready, loaded, gate accepted, sailed) | `plasticos.shipment.event.proposal`: an immutable candidate. Accepting it runs the owner command | `supplier_ready` → `plasticos.load.action_confirm_ready`; `loaded` → `plasticos.load.action_record_actual_event('pickup')`; `gate_accepted` / `sailed` → `plasticos.iso.journey.fact.action_record_gate_in` / `action_record_departure` (BRS-EXP-09-R007, BRS-EXP-11-R010). A supplier report cannot attest a gate-in or a sailing. |

The Documents VGM basis calls the frozen facade `plasticos.document.get_scoped_evidence_verdict` as a soft reference (Documents depends on Logistics). It stores `verified_document_id` only when that row exists and is about the same J1 in its company. Without Documents the answer is `not_available`.

## Migration

Every new column is nullable and every new table starts empty, so no backfill and no migration script are needed. `plasticos_logistics` 19.0.1.14.22 → 19.0.1.14.23 and `plasticos_security_base` 19.0.1.2.25 → 19.0.1.2.26. Both modules are byte-identical between `ff42df2d` and the S8 head, so upgrading the pinned fixture (admitted from `ff42df2d`) to the merged head is the upgrade from the S8 state for them; the runtime test runs that upgrade on each clone.

## Runtime

Fixture `odoo_test_tpl_ee_c9e8a81f52f23680` (fingerprint `f44b9807`), Enterprise clone `Quantum-L9/odoo-enterprise@3225e0e8`. Receipts stay in the gitignored `.l9/runtime/test-env/`.

| Head | Command | Result |
|---|---|---|
| `cd10a57f` (pre-merge) | `make runtime-test m=plasticos_logistics,plasticos_security_base` | 472 run, 0 failed, 0 errors |
| `8e1a20f6` (S8 `3fda2e04` merged) | `make runtime-test m=plasticos_logistics,plasticos_export,plasticos_documents,plasticos_security_base` | 649 run, 0 failed, 0 errors (documents 128, export 101, logistics 337, security_base 215 incl. post-install) |

| `4b360072` (accepted S8 `6c7789ef` merged) | same four modules | 652 run, 0 failed, 0 errors (documents 128, export 104, logistics 337, security_base 215); `pytest tests/` 3076 passed, 0 failed; pre-commit `6c7789ef..HEAD` clean; `make audit-baseline` no new finding |

No S9 fixture needed repair for the S8 08-R006 allocation guard: S9 tests create no Export allocation.

## Not in scope

Native Documents AI stays held. The Export cargo-link variant of the AC-EXP-08-007 resale witness belongs to S10 (coordinator ruling Q2).
