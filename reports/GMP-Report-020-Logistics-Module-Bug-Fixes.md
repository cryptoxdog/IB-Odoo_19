# GMP-Report-020-Logistics-Module-Bug-Fixes

**ID:** GMP-020
**Task:** Fix 15 bugs in plasticos_logistics module (security, validation, performance, hygiene)
**Tier:** RUNTIME_TIER
**Date:** 2026-03-18
**Time:** 14:49 EST
**Status:** ✅ COMPLETE

---

## PLAN

| ID  | File | Lines | Action | Status |
| --- | ---- | ----- | ------ | ------ |
| T1  | security/ir.model.access.csv | L9-11 | DELETE | ✅ |
| T2  | services/state_machine.py | L1-30 | REPLACE | ✅ |
| T3  | models/load.py | L1-342 | REPLACE | ✅ |
| T4  | wizards/load_bulk_update_wizard.py | L1-99 | REPLACE | ✅ |
| T5  | models/dispatch.py | L1-50 | REPLACE | ✅ |
| T6  | views/load_views.xml | L173-184, L283 | INSERT | ✅ |
| T7  | .gitignore | L1 | CREATE | ✅ |

**Hash:** `15 TODOs | ACL, state_machine, load.py, wizard, dispatch, views, gitignore`

---

## CHANGES

| File | Lines | Action | Description |
| ---- | ----- | ------ | ----------- |
| `security/ir.model.access.csv` | 9-11 | DELETE | Removed 3 duplicate ACL rows (`access_load_all`, `access_rate_memory_all`, `access_dispatch_all`) that granted delete permissions to all users |
| `services/state_machine.py` | 1-30 | REPLACE | Added `exception` state to `VALID_TRANSITIONS`, added `ALLOWED_TRANSITIONS` for dispatch, moved `new_correlation_id()` function here |
| `models/load.py` | 130-145 | REPLACE | Expanded `write()` allowed set: added `cycle_time_hours`, `sla_breached`, `message_ids`, `message_follower_ids` |
| `models/load.py` | 165-175 | REPLACE | Batched `_compute_transaction_id()` to fix N+1 query problem |
| `models/load.py` | 177-182 | REPLACE | Fixed `action_confirm_ready()` to use `self.env.user` instead of accepting arbitrary string |
| `models/load.py` | 184-200 | REPLACE | Added rate memory guard in `action_confirm_rate()` to prevent bad lane keys |
| `models/load.py` | 206-218 | REPLACE | Added dispatch pre-conditions: carrier, pickup/delivery locations, pickup datetime required |
| `models/load.py` | 224-245 | REPLACE | Wired `VALID_TRANSITIONS` into `_transition()` with inline import to prevent circular imports |
| `models/load.py` | 260-268 | INSERT | Added `@api.constrains` for pickup/delivery datetime order validation |
| `models/load.py` | 1-10 | DELETE | Removed duplicate `new_correlation_id()` function (now imported from state_machine) |
| `wizards/load_bulk_update_wizard.py` | 7 | REPLACE | Added `ValidationError` to imports |
| `wizards/load_bulk_update_wizard.py` | 61-99 | REPLACE | Replaced raw SQL bypass with `_transition()` call that enforces state machine |
| `models/dispatch.py` | 14 | INSERT | Added `load_id` FK field (nullable, no `required=True`) |
| `models/dispatch.py` | 28-48 | REPLACE | Updated `action_transition()` to use inline import from state_machine |
| `views/load_views.xml` | 173-184 | INSERT | Added `invisible="state == 'draft'"` to 4 email send buttons |
| `views/load_views.xml` | 283 | INSERT | Added `readonly="1"` to `sla_breached` field |
| `.gitignore` | 1 | CREATE | Created with `*.pdf` entry to prevent PDF artifacts |

---

## TODO → CHANGE MAP

| TODO | File | Change |
| ---- | ---- | ------ |
| acl-fix | security/ir.model.access.csv | Deleted 3 duplicate ACL rows granting delete to all users |
| state-machine | models/load.py | Wired VALID_TRANSITIONS into _transition() with validation |
| state-machine-exception | services/state_machine.py | Added exception state + ALLOWED_TRANSITIONS + new_correlation_id() |
| bulk-wizard-sql | wizards/load_bulk_update_wizard.py | Replaced SQL bypass with _transition() + added ValidationError import |
| write-guard-fix | models/load.py | Added cycle_time_hours, sla_breached, message_ids, message_follower_ids to allowed set |
| dispatch-validation | models/load.py | Added carrier/location/date validation to action_dispatch() |
| auth-fix | models/load.py | Fixed action_confirm_ready() to use self.env.user |
| rate-memory-guard | models/load.py | Guarded _store_rate_memory() against bad lane keys |
| dispatch-load-link | models/dispatch.py | Added load_id FK (nullable) |
| batch-compute | models/load.py | Batched _compute_transaction_id to fix N+1 |
| correlation-id | services/state_machine.py | Extracted new_correlation_id() to shared module |
| button-visibility | views/load_views.xml | Hidden email buttons on draft state |
| sla-readonly | views/load_views.xml | Made sla_breached readonly |
| date-constraint | models/load.py | Added pickup/delivery datetime constraint |
| remove-pdfs | .gitignore | Created .gitignore with *.pdf |

---

## VALIDATION

| Gate | Result |
| ---- | ------ |
| py_compile | ✅ |
| import test | ✅ |
| linter | ✅ No errors |
| odoo -u plasticos_logistics | ✅ Exit 0 |
| odoo -u all (27 modules) | ✅ Exit 0 |

---

## SECURITY IMPACT

| Issue | Severity | Resolution |
| ----- | -------- | ---------- |
| ACL duplicate rows allowed any user to delete loads/rates/dispatches | CRITICAL | Removed 3 `_all` ACL rows |
| Bulk wizard SQL bypass allowed illegal state transitions | CRITICAL | Replaced with _transition() enforcement |
| No state machine validation in _transition() | CRITICAL | Wired VALID_TRANSITIONS with validation |
| action_confirm_ready() accepted arbitrary user string | HIGH | Now captures authenticated self.env.user |
| Rate memory poisoned with "False-False" lane keys | HIGH | Added guard before _store_rate_memory() |

---

## DECLARATION

Phases 0-6 complete. No assumptions. No drift.

All 15 bugs from the audit have been fixed:
- 3 CRITICAL security issues resolved
- 4 HIGH validation issues resolved
- 1 MEDIUM performance issue resolved
- 4 HYGIENE items resolved
- 3 reviewer additions incorporated (write guard expansion, inline imports, nullable FK)

Deployment verified with `docker compose -p odoo19 run --rm odoo -u plasticos_logistics --stop-after-init` (exit 0).
Full module reload verified with all 27 plasticos modules (exit 0).
