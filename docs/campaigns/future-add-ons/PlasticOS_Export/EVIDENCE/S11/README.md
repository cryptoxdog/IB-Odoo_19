# S11 evidence: journey-fact corrections, Linda approval, sweep cursor

Contract `PLASTICOS-EXPORT-C12-S11-FACT-CORRECTIONS-LINDA-APPROVAL` (sha256 `431dec88…`), re-frozen by coordinator C12-SCOPE-2 as `d7ec40a9…` (the binding digest). Base `e71599d5` (the accepted S10 head); nothing to merge. Operator decisions 2026-11-12: journey facts may be corrected with a mandatory reason; no second approver for people; every Linda edge case needs an Operations Manager; clean up the Linda sweep cursor. This folder holds no Odoo logs and no real data.

| File | Contents |
|---|---|
| `S11_RULE_WITNESSES.csv` | Every S11 obligation and its positive and negative witness (`file::Class::method`) |

## What changed

| Effect | Owner | Summary |
|---|---|---|
| OP11-E01 corrections | `plasticos.iso.journey.fact.action_correct_fact` | Revision `n + 1` with `supersedes_id`, required `correction_reason`, `corrected_by`, `corrected_at`, `operation_key`. The superseded row is never written. `UNIQUE(journey_id, fact_kind, revision)` replaces the S9 `UNIQUE(journey_id, fact_kind)`; `UNIQUE(journey_id, operation_key)`; a `CHECK` ties revision 1 to no correction fields and revision > 1 to all of them. Same guards as the first record. Empty reason, unchanged value, stale revision and reused key are refused. |
| OP11-E01 read path | `plasticos.iso.journey.current_facts(kinds=None)` / `current_fact(kind)` | `{kind: highest revision}` with the caller's rights. |
| OP11-E02 Linda approval | `plasticos.linda.approval`, `plasticos_logistics.user_linda` | See below. |
| OP11-E03 sweep cursor (F6) | `plasticos.linda.sweep.cursor` | One row per lane (`ack`, `chase`) and company. The sweep writes no `ir.config_parameter`. |
| OP11-E04 module page | none | No manifest change (operator decision, coordinator correction superseding C12-SCOPE-2 item 3): Odoo 19 renders `static/description/index.html`, then the manifest `description`, then the README (`README.rst` before `README.md`); `plasticos_logistics/README.rst` already renders cleanly. S12 witnesses the page after the merge. |

`plasticos_logistics` 19.0.1.14.23 → 19.0.1.14.24; `plasticos_security_base` 19.0.1.2.26 → 19.0.1.2.27 (ACL rows for `plasticos.linda.approval`, and the Logistics grant to Linda in `security/record_rules.xml`, because the business groups are defined in that module, which loads after Logistics).

## Migration 19.0.1.14.24

* `pre-migrate.py`: adds `revision`, sets it to 1 on every fact recorded before this version, drops `plasticos_iso_journey_fact_one_fact_per_kind`. No fact value is read, rewritten or deleted.
* `post-migrate.py`: copies each `plasticos_logistics.linda_load_sweep_cursor.<lane>` parameter once into the cursor row of the sweep company (the `plasticos_base.user_system_cron` company, else the main company), then deletes the parameter. A non-numeric value restarts the lane at 0, as the old code did.

Both reruns change nothing (`TestLindaSweepCursor::test_migration_moves_a_stored_parameter_once`, `test_fact_migration_rerun_changes_nothing`). The upgrade from the S10 head with a fact present before the upgrade is a runtime obligation: **PENDING_COORDINATOR**.

## Linda (OP11-E02, C12-SCOPE-2)

`plasticos_logistics.user_linda` (`data/linda_user.xml`, `noupdate`): active, internal, no password, main company, `base.group_user` plus `plasticos_security_base.group_logistics` and nothing else. No `ir.cron` `user_id` was changed.

A gated command run by Linda returns `{"status": "pending", "approval_id": …, "reason": …}` and files one `plasticos.linda.approval` row (idempotent per company, command and operation key while pending) in these edge cases:

| Edge case | Command | Held when |
|---|---|---|
| `correction` | `action_correct_fact` | always (after validation; a plain refusal stays a refusal) |
| `unverified_linda_reply` | `action_propose_shipment_event` | it cites a Linda reply with disposition `identity_unverified` or `unresolved`; the proposal is first validated in a rolled-back savepoint, so an invalid one is refused |
| `acceptance` | `action_accept` | always |
| `value_conflict` | `action_record_*` | a current revision of that kind exists with a different value; approval supersedes it |
| `out_of_sequence` | `action_record_*`, `action_correct_fact` | departure without or before gate-in; gate-in after departure |
| `unit_mismatch` | `action_record_*`, `action_correct_fact` | missing weight unit, or a unit that is not a weight |
| `evidence_unverified` | `action_record_*`, `action_correct_fact` | original missing, not readable by Linda (refusal names nothing), not on the journey, in another company, or the Documents VGM verdict missing, unreadable or not about the journey |
| `refusal_retry` | any gated command | the same operation key was rejected, or its approved run was refused, before |

Filing is idempotent per company, command and key, including a concurrent filing that loses the pending index (it answers the winning approval). Only a `group_operations_manager` user who is not Linda can approve or reject (`AccessError` otherwise). Approval runs the held command as Linda under an object-identity context token that RPC cannot carry, so the owner guards still run and the fact, proposal or decision keeps Linda as its author; the approval row records the approver, time, note and the command's answer. A straight-through Linda outcome and every person's command apply at once; a person needs no second approver, which also settles N9 for people.

### Linda write-path inventory (e71599d5 + S11)

No automated path reaches a gated command today. Linda's automated writes touch only her own evidence and mail:

| Path | Entry | Trigger / actor | Writes |
|---|---|---|---|
| Inbound reply on PO/SO | `data/linda_inbound_ai.xml` → `plasticos.logistics.response._record_incoming` | `base.automation` on inbound email, sudo | `plasticos.logistics.response` (binding, disposition: the source of `identity_unverified` / `unresolved`) |
| Inbound reply on Export booking | `plasticos_export/data/linda_booking_inbound.xml` → same | `base.automation`, sudo | `plasticos.logistics.response` (`source_kind=booking`) |
| Dispatch-acknowledgement sweep | `data/cron.xml` `cron_dispatch_acknowledgment` → `plasticos.load._cron_check_dispatch_acknowledgments` → `plasticos.logistics.request._run_load_obligations` | cron user `plasticos_base.user_system_cron`, sudo | `plasticos.logistics.request` (ack notice, escalation, document chase), `mail.mail`, the sweep cursor row, one escalation activity per load per day |
| Mail send guard / claim / post-send | `models/mail_mail_inherit.py` | mail queue, sudo | `mail.mail` state, request state, `plasticos.load.dispatch_sent` |
| Order issue / cancel / material change | `purchase_order_inherit.py`, `sale_order_inherit.py` → `linda_request` | person, RPC, or the hourly `cron_auto_create_do` (`plasticos_transaction` `po.button_confirm()`) | `po_issue` / `so_issue` / cancel requests and mail |
| Booking correspondence | `plasticos_export` `action_request_booking_notice` → `request_booking_correspondence` | person / RPC | booking issue, amend or cancel request and mail |

Gated commands are called only by people or RPC: `action_propose_shipment_event` (the only place a Linda reply is cited), `action_accept`, the five `action_record_*` fact commands and `action_correct_fact`. `TestLindaGateReach` proves it statically: every `ir.cron`, `base.automation` and `ir.actions.server` declared in PlasticOS XML (47 at this head) is followed through a name-based call graph of all non-test PlasticOS Python, and none reaches a gated command; a planted cron → helper → `action_correct_fact` path is detected.

### Remaining risks (recorded, not fixed here)

* `_require_logistics_actor` passes silently for a superuser or `sudo()` caller, and `_require_freight_operator` for the superuser uid. A future automated caller under sudo would not run as Linda, so it would not be gated, and it would be stamped as the cron or superuser user.
* The hourly `cron_auto_create_do` (`plasticos_transaction` `transaction.py`, `po.button_confirm()`) issues a live Linda purchase-order mail with no person in the loop; the 6-hour supplier-confirmation cron sends template mail outside Linda's mode and evidence controls.
* No quantity-tolerance check exists anywhere in Logistics or Export, so that edge-case class has no code to hold; the unit check exists only for journey tare and VGM.
* Export `plasticos_export/models/owner_facts.py` `_journey_facts` reads facts by id order instead of `current_facts()`; it shows the current value only because a correction always has a higher id. The coordinator assigned that change to S12.

## Validation

| Check | Result |
|---|---|
| `pytest tests/` (pure Python) at `ec9b3704` | 3076 passed, 49 skipped, 0 failed |
| `pytest tests/` (pure Python) at `fabb7900` (final code head) | 3076 passed, 49 skipped, 0 failed |
| `pre-commit run --from-ref e71599d5 --to-ref fabb7900` | all hooks passed |
| `make audit-baseline` at `fabb7900` | no new finding (comprehensive and extended) |
| `pytest tests/test_phantom_enum_values.py tests/test_repo_dependency_integrity.py` at the E02 head | 63 passed |
| Static gate-reach scan (run outside Odoo) | 47 entry points, 0 gated paths; planted path detected |
| Enterprise runtime `m=plasticos_logistics,plasticos_export,plasticos_documents,plasticos_security_base` | **PENDING_COORDINATOR** (C12-SCOPE-2: this session's fixture needs an operator rebuild, not authorized; the coordinator runs it on its admitted fixture) |
| Migration from the S10 head with a fact present | **PENDING_COORDINATOR** |


## Not in scope

Native Documents AI and any external AI call; `plasticos_security_base` load rules; changing any `ir.cron` `user_id` or scheduled action; Export's read path (S12).
