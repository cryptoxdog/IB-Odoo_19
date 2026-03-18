# GMP-Report-001-Logistics-Bug-Fixes

**ID:** GMP-001
**Task:** Fix 11 confirmed bugs in plasticos_logistics module (security, state machine, validation, performance, hygiene)
**Tier:** RUNTIME_TIER
**Date:** 2026-03-18
**Status:** ✅ COMPLETE

---

## PLAN

| ID | File | Lines | Action | Status |
|---|---|---|---|---|
| T1 | `plasticos_logistics/security/ir.model.access.csv` | L9-11 | DELETE | ✅ |
| T2 | `plasticos_logistics/services/state_machine.py` | L1-30 | REPLACE | ✅ |
| T3 | `plasticos_logistics/models/load.py` | L1-10 | REPLACE | ✅ |
| T4 | `plasticos_logistics/models/load.py` | L135-150 | REPLACE | ✅ |
| T5 | `plasticos_logistics/models/load.py` | L213-226 | REPLACE | ✅ |
| T6 | `plasticos_logistics/models/load.py` | L234-252 | REPLACE | ✅ |
| T7 | `plasticos_logistics/models/load.py` | L171-179 | REPLACE | ✅ |
| T8 | `plasticos_logistics/models/dispatch.py` | L14 | REPLACE | ✅ |
| T9 | `plasticos_logistics/views/load_views.xml` | L173-188 | REPLACE | ✅ |
| T10 | `plasticos_logistics/views/load_views.xml` | L287 | REPLACE | ✅ |

**Hash:** `10 TODOs | ACL, state_machine, load.py, dispatch.py, load_views.xml`

---

## CHANGES

| File | Lines | Action | Description |
|---|---|---|---|
| `ir.model.access.csv` | 9-11 | DELETE | Removed 3 duplicate ACL rows with `perm_unlink=1` (access_load_all, access_rate_memory_all, access_dispatch_all) |
| `state_machine.py` | 1-30 | REPLACE | Added `new_correlation_id()` function; added `exception` state transitions; added `closed: []` terminal; added `ALLOWED_TRANSITIONS` for dispatch |
| `load.py` | 1-10 | REPLACE | Module-level import of `VALID_TRANSITIONS` and `new_correlation_id` from state_machine.py; removed local `uuid` import and duplicate function |
| `load.py` | 135-150 | REPLACE | Added `cycle_time_hours`, `sla_breached`, `message_ids`, `message_follower_ids` to `write()` allowed set (fixes deadlock) |
| `load.py` | 213-226 | REPLACE | Tightened `action_dispatch()` to only accept `scheduled` state; added carrier/location/datetime pre-condition checks |
| `load.py` | 234-252 | REPLACE | Enforced state machine in `_transition()` with `VALID_TRANSITIONS` validation |
| `load.py` | 171-179 | REPLACE | Batched `_compute_transaction_id()` with `@api.depends("id")` to fix N+1 query |
| `dispatch.py` | 14 | REPLACE | Added `index=True` to `load_id` Many2one field |
| `load_views.xml` | 173-188 | REPLACE | Added `invisible="state in ('draft', 'awaiting_ready', 'ready_confirmed')"` to all 4 email stat buttons |
| `load_views.xml` | 287 | REPLACE | Added `readonly="1"` to `sla_breached` field |

---

## TODO → CHANGE MAP

| TODO | File | Change |
|---|---|---|
| T1 | `ir.model.access.csv` | Deleted 3 overly-permissive ACL rows granting `perm_unlink=1` to `base.group_user` |
| T2 | `state_machine.py` | Added `exception` state, `closed: []` terminal, centralized `new_correlation_id()` |
| T3 | `load.py` | Module-level import from state_machine.py instead of local function |
| T4 | `load.py` | Fixed `write()` deadlock by adding computed/cron fields to allowed set |
| T5 | `load.py` | Tightened `action_dispatch()` pre-conditions |
| T6 | `load.py` | Enforced state machine validation in `_transition()` |
| T7 | `load.py` | Batched `_compute_transaction_id()` to fix N+1 query |
| T8 | `dispatch.py` | Added index to `load_id` FK |
| T9 | `load_views.xml` | Hidden email buttons on early states |
| T10 | `load_views.xml` | Made `sla_breached` readonly |

---

## VALIDATION

| Gate | Result |
|---|---|
| py_compile | ✅ |
| import test | ✅ |
| linter (ruff) | ✅ No errors |
| XML syntax | ✅ Valid |

---

## PRE-EXISTING FIXES CONFIRMED

The following items from the plan were already implemented in previous sessions:

| Item | Status | Notes |
|---|---|---|
| `action_confirm_ready()` auth | ✅ Already fixed | Uses `self.env.user.name` |
| `action_confirm_rate()` guard | ✅ Already fixed | Guards `_store_rate_memory()` call |
| Date constraint | ✅ Already exists | `_check_datetime_order()` method |
| Wizard SQL bypass | ✅ Already fixed | Uses ORM `_transition()` pattern |
| PDF files | ✅ Already removed | `.gitignore` exists with `*.pdf` |

---

## SECURITY IMPACT

| Before | After |
|---|---|
| `base.group_user` could delete loads | Only `base.group_system` can delete |
| `base.group_user` could delete rate memory | Only `base.group_system` can delete |
| `base.group_user` could delete dispatches | Only `base.group_system` can delete |

---

## STATE MACHINE ENFORCEMENT

| Transition | Before | After |
|---|---|---|
| `draft` → `awaiting_ready` | ✅ Allowed | ✅ Allowed |
| `scheduled` → `dispatched` | ✅ Allowed | ✅ Allowed (only valid path) |
| `rate_confirmed` → `dispatched` | ✅ Allowed (skip) | ❌ Blocked (must go through `scheduled`) |
| `closed` → any | ✅ Allowed (no guard) | ❌ Blocked (terminal state) |
| any → `exception` | ❌ Not possible | ✅ Allowed (escape hatch) |
| `exception` → `draft` | ❌ Not possible | ✅ Allowed (recovery path) |

---

## DEPLOYMENT

```bash
odoo-bin -u plasticos_logistics -d plasticos --stop-after-init
```

---

## DECLARATION

Phases 0-6 complete. No assumptions. No drift.

All changes verified against live codebase. Security ACL cleanup removes dangerous `perm_unlink=1` grants. State machine now enforced at `_transition()` level. Performance fix batches N+1 query. Hygiene fixes improve UX.

Changes committed locally. Ready to push on explicit request.
