# Documents + AI | Scoped capability contract (architecture, not activation)

**Question:** How can PlasticOS let intelligent assistants understand relationships across documents, orders, loads and parties, find missing fields, reason about contradictions and propose the next action while Odoo retains business authority?

## Evidence to action graph (no new engine)

1. **Capture:** native `mail.message` / original MIME and native Enterprise Documents/`ir.attachment` retain real original and timestamps. Attachments and message receipt do not verify their business content. No external native Documents invitations.
2. **Extract:** if installed and entitled, native Odoo Documents AI / bounded parse classifies booking, scale ticket, Receiving Report and correspondence; returns typed **candidate facts** with source document identity, field coordinates, exact value, currency/unit, date-only vs instant, timezone, and confidence/uncertainty. Manual classification remains a valid basic path; AI subscription is not an MVP hard dependency.
3. **Relate:** Documents evidence owner matches candidates to exact existing company, PO, SO, load/picking, physical units, party, purpose and revision. No recency/name-only binding, fabricated links or duplicate originals. Multi-link cardinality is a capability seam, not presumed installed.
4. **Reason:** combine accepted facts, source provenance, current status, applicable BRS and downstream consumers. Useful agent outputs: missing proof by operation, source-to-source value contradiction, booking amendment candidate, affected-not-affected obligation set, candidate physical/booking links, next safe action with explanation. Unknowns remain unknown; never classify a port destination as the buyer by inference.
5. **Propose:** emit candidate-action contracts with `{action_type, subject_ref, company, party, source_refs, source_revisions, precondition_refs, proposed_change, conflict_refs, affected_scope, confidence, status}`. This is a conceptual interface shape **only**; no API/schema or Odoo model is authorized here.
6. **Decide/act:** existing authoritative Odoo domain owner validates current preconditions, verified evidence, access rights, actor identity and approval (if needed) and executes its native operation. Documents compliance checks are observational; native AI server actions cannot bypass owner commands. Linda alone coordinates authorized external messages.
7. **Observe/reconcile:** separate accepted intent, queued transport, provider accepted, delivered/acknowledged, human/business accepted, posted/settled, and source revision changed. No implicit retries, no provider failure transformed into success.

## Distinct AI authority surfaces

| Surface | Role | Does not own |
|---|---|---|
| Native Documents AI | extraction, sorting, candidate type/fields | verified, accepted order/booking, dispatch, posting |
| Deterministic reply interpretation | recognized constrained standard text as a candidate | sender authentication, readiness decision |
| EIE | enrichment/inference/evidence and missing-field priority via governed Gate | Odoo native file verification or native state changes |
| CEG | graph reasoning, eligibility, scoring/decision proposals via governed Gate | PDF storage, Odoo authoritative record mutation |
| Odoo native/domain modules | fact owners, role/access rules, documented command execution | new second AI transport or shadow matcher |

## Required falsifying probes (all NOT_RUN)

- An AI model labels a current PDF `verified`; classification may be visible but authoritative `verified` stays unchanged absent authorized verification.
- AI extracts conflicting ERDs from two documents; neither overrides without revision/identity/source proof. Preserve both values and identify which load/obligation actually depends on that ERD.
- A PDF names a supplier and booking but no exact company/PO; keep it in review rather than attach to newest partner transaction.
- Supplier says READY in a forwarded old message; do not update load, book carrier, or send without exact current Linda request and authorized party authentication.
- Two loads share a PO, only one verified Receiving Report; the other load's invoice/close gate remains unsatisfied where applicable.
- A new shipping revision does not automatically resend a prior issued PO, invent a new booking, or erase a verified pickup.
- Gate/EIE/CEG failure yields an explicit classified error; local work does not impersonate canonical external inference.
- A native Documents AI service is absent/unlicensed; manual file intake and operator verification remain possible, no unauthorized paid API call.
- Native Requests/email are internal only until explicit per-recipient external-send authorization; no public document-sharing URLs.
- Document compliance readback triggers zero `account.move.action_post`, mail sends, stock moves or order state writes.

## Discovery-only proof gates

Source-level current Odoo Enterprise version/entitlements, `documents.document`/AI server-action API, ACLs, native internal Requests, version/shortcut semantics, MIME custody and action side effects must be inspected on the **actual installed** database and bound to an isolated fixture when a future authorized proof occurs. No claim of actual AI execution, live email behavior or production readiness follows from this design.
