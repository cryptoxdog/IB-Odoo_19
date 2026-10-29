# Native Odoo field-by-field review: exact design contract

## Existing execution path (observed, not necessarily deployed)

`plasticos.enrichment.run` (requires `res.partner`) -> `action_execute` -> `plasticos_gate.build_converge_request` -> `send_converge_action` -> `map_converge_response` -> `partner_writeback_from_converge` -> `run.gate_proposal` (mapped final_fields, proposed_partner_fields, EIE run-level evidence) -> `state=review` under current OFF dual flags -> `action_inject` -> `_apply_converge_writeback` -> `res.partner.write` + committed provenance. The existing Inject applies the entire stored allowlisted proposal, not field choices. Existing legacy non-Gate `validated` run can take a different local material-inject path. Both paths require safe transition controls.

## New native record placement

Keep models `plasticos.enrichment.run`, `.source`, `.extraction`, `.provenance`, and `res.partner`. Add only `plasticos.enrichment.proposal.line` within the existing addon. Do not duplicate Odoo CRM or material profile entities. Proposal line fields are a **candidate implementation contract** and will be accepted against Odoo 19 Enterprise installed registry:

- `run_id` (required Many2one, restrict deletion), `partner_id` (stored reference for filtering), `company_id` (native `res.company` source policy; conflict if unresolvable).
- `target_field` (server-validated Char in exact current eight-field allowlist). `target_model` constant `res.partner`; no arbitrary model extension.
- `source_packet_id`, `source_run_attempt`, `source_digest`, `response_field_key`, `proposed_value` and captured typed original value with explicit present/missing state. Unique exact `(run_id, target_field)` per received Gate response; a materially different response uses a new run, not a replaced approval.
- `eie_run_confidence`, `eie_kb_hash`, `inference_version`, and available source fragment IDs are labeled **run-level**. `field_source_kind` is `eie_bound`, `eie_run_only`, `operator_attested`, or `unknown`; no invented URLs or confidence 1.0.
- `review_decision` distinct from execution state: `pending`, `approved`, `rejected`, `skipped`, `requires_evidence`, `conflict`; `apply_state`: `unapplied`, `applied`, `blocked`, with reviewer, date, reason, and resulting provenance ID where applicable.
- `reviewer_attestation_source_url`/notes are optional native Odoo fields subject to policy, clearly **operator verified**, not EIE supplied. High-risk data requires source evidence or explicit verified operator attestation before Apply Approved.

`plasticos.enrichment.provenance` stays an *applied-write* audit record, not a pending suggestion. Add a nullable proposal-line backlink to new effects only if audit/retention checks justify it; never rewrite old provenance rows to indicate approval.

## Form UI

The existing Enrichment Run form gets a **Proposed Changes** one2many section: Field | Current | Suggested | Evidence Kind | Run Confidence | Decision | Conflict/Reason. It shows native tabs Sources, Extractions, Applied Provenance, Issues and mail.thread as before. A user may approve/reject/skip per field, or mark unverified. A separate **Apply Approved** button operates only on approved eligible lines, never all JSON. The existing Inject method remains guarded backwards-compatible routing or is replaced with a clear instruction to use review, but never bulk implicit acceptance. Contact's Enrichment tab shows review count plus native action to open the run list; no portal or website.

## Required state machine

- New run `draft`; Execute only if trusted partner, company, permissions, Gate availability and rate policy all pass.
- Completed Gate return with some allowlisted fields -> `review`, lines pending. Absolutely no partner write under any runtime ICP setting in this scoped code path.
- Completed Gate return with no writable fields -> explicit `no_action`/evidence-only status (new status requires admitted enum/view/tests), retain bounded response; no fabricated Gate error or injected state.
- Review decisions can change while not applied; after Apply Approved, approved lines become `applied`, others remain rejected/skipped/conflict with audit. Run may become `partially_applied` when not all eligible lines are written, or `injected` only when actual approved writes commit. Never claim injected on zero writes.
- Stale/conflicting values become `conflict`, user must explicitly refresh/review with source evidence; a race never downgrades the source record.
- Terminal or historical `engine_used=local` records are immutable evidence; attempts to inject local material profiles fail closed.
- Retries of Gate failure create a new logical operation attempt, preserving old audit; same completed Gate result cannot silently be applied twice or reset review on a different run.

## Data/field boundaries

The accepted allowlist is exactly `name`, `website`, `city`, `zip`, `street`, `street2`, `email`, `phone`. Those are Odoo Char/text-targeted fields, not blanket material/quality/buyer fields. Validate native field type and length, legitimate target, missingness and company. Treat `False`, `None`, `0`, `""` and valid nonempty values distinctly by declared field schema; do not make global truthiness a proxy for missing. Existing nonempty verified data is never overwritten. Non-allowlisted final_fields may be retained as protected response evidence but do not produce writable proposal lines.

## Idempotency

Source run + returned packet + field + typed proposed value + target record/source snapshot is the logical proposal identity, with a unique current `(run_id, target_field)` and versioned immutable evidence digest. Server-side write locks the target partner and proposal rows, rechecks actual ACL/rule, original snapshot, final allowed field and explicit reviewer. `res.partner.write` and creation of exactly one corresponding provenance per applied field occur atomically in the same native transaction. No manual `env.cr.commit` in an ordinary approval RPC. Duplicate clicks, retries and concurrent reviewers return the existing receipt or clear conflict.

## When EIE lacks field-level source evidence

Never label a KB fragment list as the citation for an individual proposed field unless the source contract binds it. Display **"Only run-level EIE provenance; no field citation"**. An authorized human may supplement a field with an auditable source and attest verification, subject to the field's category policy. Otherwise the field stays evidence-only or `requires_evidence` and cannot write. This makes the workflow useful without requiring any EIE/CEG change and without inventing certainty.
