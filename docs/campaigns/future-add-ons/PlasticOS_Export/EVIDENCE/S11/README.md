# S11 evidence: journey-fact corrections, Linda approval, sweep cursor

Contract `PLASTICOS-EXPORT-C12-S11-FACT-CORRECTIONS-LINDA-APPROVAL` (sha256 `431dec88…`), re-frozen by coordinator C12-SCOPE-2 as `d7ec40a9…` and C12-SCOPE-3 (review closure of #498 at `0beb2eb4`) as `176a9624…` (the binding digest). Base `e71599d5` (the accepted S10 head); nothing to merge. Operator decisions 2026-11-12: journey facts may be corrected with a mandatory reason; no second approver for people; every Linda edge case needs an Operations Manager; clean up the Linda sweep cursor. This folder holds no Odoo logs and no real data.

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

`plasticos_logistics.user_linda` (`data/linda_user.xml`, deliberately not `noupdate`): active, internal, no password and no API key, main company, `base.group_user` plus `plasticos_security_base.group_logistics` and nothing else. The Logistics grant is `(4, group_logistics)` in `plasticos_security_base/security/record_rules.xml`; the record is updatable so the grant applies on upgrade as well as install (coordinator runtime B1 at `0beb2eb4`: under `noupdate` the grant was skipped on upgrade and Linda had no Logistics rights), and the Logistics file only ever adds groups, so a Logistics-only upgrade keeps the grant. No `ir.cron` `user_id` was changed.

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
| `refusal_retry` | any gated command | Linda's last decided call of the same command on the same subject (journey + fact kind, proposal, or load) was refused, rejected, or approved and then refused by the owner, under any operation key (C12-SCOPE-3 (2)) |
| `acceptance` | `plasticos.load.action_confirm_ready` | always, unless the load's state is already `ready_confirmed` (round 2, R1: readiness is the state, not the timestamp). A load with no company answers `blocked` (R6) |
| `correction` / `out_of_sequence` / `evidence_unverified` | `plasticos.load.action_record_actual_event` | a value differing from the recorded one (a correction without a reason is refused and recorded, not held: round 2, R5); delivery before pickup; evidence missing, not on the load, in another company or not readable by Linda (neutral reason; only the attachment read check maps an `AccessError` to this class, while `_require_freight_operator` keeps its own refusal: round 2 R2, round 3 N4). A straight-through first record applies; a plain refusal is returned as `blocked` (C12-SCOPE-3 (1)) |

Filing is idempotent per company, command and key, including a concurrent filing that loses the pending index (it answers the winning approval). Every refusal of a Linda command with a known subject (`blocked` / `not_available`) is recorded as a ledger row with state `refused`; that is what makes a retry detectable under a new key. Linda creates shipment event proposals only through `action_propose_shipment_event` (a module-private create token; a person may still create one from the form). Approval runs Linda with `allowed_company_ids` set to the approval's company only, so a multi-company manager's own company selection never reaches her run. An approved `value_conflict` stores the revision it conflicted with (`conflict_fact_id`) and is refused as stale when that revision is no longer current. A Linda correction that changes nothing, names a stale revision or fails a plain guard is refused (and recorded), not held. A held key re-used with different arguments is refused. Only a `group_operations_manager` user who is not Linda can approve or reject (`AccessError` otherwise). Approval runs the held command as Linda under an object-identity context token that RPC cannot carry, so the owner guards still run and the fact, proposal or decision keeps Linda as its author; the approval row records the approver, time, note and the command's answer. A straight-through Linda outcome and every person's command apply at once; a person needs no second approver, which also settles N9 for people.

### Linda write-path inventory (e71599d5 + S11)

No automated path reaches a gated command today. Linda's automated writes touch only her own evidence and mail:

| Path | Entry | Trigger / actor | Writes |
|---|---|---|---|
| Inbound reply on PO/SO | `data/linda_inbound_ai.xml` → `plasticos.logistics.response._record_incoming` | `base.automation` on inbound email, sudo | `plasticos.logistics.response` (binding, disposition: the source of `identity_unverified` / `unresolved`) |
| Inbound reply on Export booking | `plasticos_export/data/linda_booking_inbound.xml` → same | `base.automation`, sudo | `plasticos.logistics.response` (`source_kind=booking`) |
| Dispatch-acknowledgement sweep | `data/cron.xml` `cron_dispatch_acknowledgment` → `plasticos.load._cron_check_dispatch_acknowledgments` → `plasticos.logistics.request._run_load_obligations` | cron user `plasticos_base.user_system_cron`, sudo | `plasticos.logistics.request` (ack notice, escalation, document chase), `mail.mail`, the sweep cursor row, one escalation activity per load per day |
| Mail send guard / claim / post-send | `models/mail_mail_inherit.py` | mail queue, sudo | `mail.mail` state, request state, `plasticos.load.dispatch_sent` |
| Order issue / cancel / material change | `purchase_order_inherit.py`, `sale_order_inherit.py` → `linda_request` | person, RPC, or the hourly `cron_auto_create_do` (`plasticos_transaction` `po.button_confirm()`) | `po_issue` / `so_issue` / cancel requests and mail |
| Raw load create/write | `plasticos.load.create` / `write` | Linda through RPC or any code running as her | refused with `AccessError` for `state`, `ready_confirmed_at`, `ready_confirmed_by` and the actual-event fields unless the call runs inside her gate or an approval (round 2, R1). Because state is refused, her ungated straight-through load transitions (dispatch, schedule, cancel and the like, which write `state`) are refused as `AccessError` too. Other load fields follow the ordinary Logistics rights. No automated path runs as Linda |
| Booking correspondence | `plasticos_export` `action_request_booking_notice` → `request_booking_correspondence` | person / RPC | booking issue, amend or cancel request and mail |

Gated commands are called only by people or RPC: `action_propose_shipment_event` (the only place a Linda reply is cited), `action_accept`, the five `action_record_*` fact commands, `action_correct_fact`, and the load owner commands `action_confirm_ready` and `action_record_actual_event` (reached by a person, the actual-event wizard, or an accepted proposal). `TestLindaGateReach` shows it statically: every `ir.cron`, `base.automation` and `ir.actions.server` declared in PlasticOS XML (47 at this head) is followed through a name-based call graph of all PlasticOS Python except `tests/`, `migrations/` and the operator shell `scripts/`, with `getattr` dispatch by literal prefix followed conservatively; none reaches a gated command. Planted cron → helper → `action_correct_fact` and cron → `getattr(…, f"action_record_{kind}")` paths are detected. Its stated limits (in `plasticos_logistics/tests/linda_gate_reach.py`): implicit ORM dispatch, `getattr` with no literal prefix, DB-only or non-PlasticOS entry points, CSV and `<function>` entries, and RPC/controller/mail-gateway calls. Every call is followed by name, builtin-looking ones included, so a `self.write(...)` that reaches a PlasticOS `write` override is followed (planted witness). The 27 false paths seen while building it came only from scanning the operator `scripts/` (an `open` classmethod there collided by name); with `scripts/` excluded and no builtin filter the scan finds 0 paths (round 2, R4). `python3 -I plasticos_logistics/tests/linda_gate_reach.py .` reproduces it outside Odoo.

### Originals Linda cannot see (round 3, R8)

`ir.attachment.check_access("read")` can pass for an attachment whose record Linda cannot read (another company's load or journey), so the coordinator's runtime at `652b650a` saw the actual-event refusal "Evidence <name> is not attached to load …" stored in her ledger. `linda_approval.original_hidden()` now treats an original as hidden when the attachment, its company or the record it is attached to is not readable by the actor, and both Linda gates (`load._linda_actual_event_gate`, `iso_journey_fact._preconditions`) hold it as `evidence_unverified` with a neutral reason before any refusal text is built. No reason, edge or ledger text stored for Linda names such an original; hold arguments carry attachment ids only. A person keeps today's behaviour.

### Kill switch (round 2, R3)

The operator stops Linda by archiving `user_linda`. `data/linda_user.xml` does not set `active`, so a module upgrade never reactivates her, and the `plasticos_security_base` grant stays. While she is archived:

* every gated command she runs (correction, fact record, proposal, acceptance, confirm-ready, actual event) answers `{"status": "blocked", "reason": "Linda is archived (operator stop); nothing was recorded"}` before any validation, ledger row or write;
* approving one of her held commands is refused (`UserError`) and the approval stays pending;
* archiving **pauses** her; it is not a mode change (round 3, R7): `_linda_mode()` is unchanged, so she keeps owning order issuance and the legacy PO/SO sender never takes over; issue, cancellation and stale-cancel obligations and their notices still queue; inbound replies are still recorded as evidence (the recorder runs as the gateway user under sudo, never as Linda, and applies no gated change); her outgoing mail is withheld from the send batch untouched by `_guard_mails_before_send` and released on reactivation;
* a typed request answers `blocked` (`linda_stopped`), and the load-obligation sweep returns `blocked` without moving its cursor.

Removing her Logistics group is not a supported stop: her commands would raise `AccessError` instead of answering, and the next `plasticos_security_base` upgrade grants it again.

### Remaining risks (recorded, not fixed here)

* Carried to the final audit (coordinator round 3): an archived Linda is not stopped on a proposal `action_reject` or on raw writes to ungated load fields (she has no login, so only in-process callers can act as her) (N3); withheld Linda mail stays in the outgoing queue and counts against the mail batch size until she is reactivated (N5).
* Carried to the final audit (coordinator round 2): refusal rows are unbounded (indexed); a database that ran `0beb2eb4` keeps `user_linda` as `noupdate=True` (fixtures only); the actual-event probe leaves a post-commit bus notification and sequence gaps; an approved replay that answers `rejected` counts as cleared for refusal-retry.
* The approval form shows `decision_note` in its Decision section, but the form is read-only and its Approve/Reject buttons pass no note; a note is stored only when `action_approve(note)` / `action_reject(note)` is called with one (review N6). A note-entry dialog would need a new transient model.
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
| `pytest tests/` at `38881b0d` (SCOPE-3 code head) | 3076 passed, 49 skipped, 0 failed |
| `pre-commit run --from-ref e71599d5 --to-ref 38881b0d` | all hooks passed |
| `make audit-baseline` at `38881b0d` | no new finding |
| `python3 -I plasticos_logistics/tests/linda_gate_reach.py .` at `38881b0d` | 47 entry points, 0 gated paths |
| Round 2 code head `f3353f85`: `pytest tests/`, pre-commit `e71599d5..f3353f85`, `make audit-baseline`, gate-reach scan | 3076 passed / 0 failed; all hooks passed; no new finding; 47 entry points, 0 gated paths |
| Coordinator runtime at `fb257cb2` (fresh template clone) | 754 run, 0 failed, 0 errors; install-smoke PASSED; rerun on the round 2 head PENDING_COORDINATOR |
| Coordinator migration proof at `0beb2eb4` (S10 clone with gate_in + container_tare facts and two cursor parameters) | Passed (revision 1, unique key, cursors moved, correction appends revision 2, idempotent rerun) |
| Coordinator runtime at `0beb2eb4` | 732 run, 1 failed, 15 errors in test_s11_linda_approval (Linda grant skipped on upgrade under noupdate; fixed in `49c366ab`); rerun on the final head PENDING_COORDINATOR |
| `pytest tests/test_phantom_enum_values.py tests/test_repo_dependency_integrity.py` at the E02 head | 63 passed |
| Static gate-reach scan (run outside Odoo) | 47 entry points, 0 gated paths; planted path detected |
| Enterprise runtime `m=plasticos_logistics,plasticos_export,plasticos_documents,plasticos_security_base` | **PENDING_COORDINATOR** (C12-SCOPE-2: this session's fixture needs an operator rebuild, not authorized; the coordinator runs it on its admitted fixture) |
| Migration from the S10 head with a fact present | **PENDING_COORDINATOR** |


## Not in scope

Native Documents AI and any external AI call; `plasticos_security_base` load rules; changing any `ir.cron` `user_id` or scheduled action; Export's read path (S12).
