# PlasticOS Mack Workbench

`plasticos_mack_workbench` provides two narrow Odoo-native primitives for Mack 5.0: immutable chat-intent receipts and internal-review requests. It is not the whole workbench, a second CRM, a chat service, a KB, a matching engine, or an approval/execution engine.

The internal-review primitive creates a durable, idempotent review request on a canonical `plasticos.intake`. The request is routed only through the active internal user selected by the company-scoped `plasticos.mack.workbench.config` policy. Request callers cannot choose the reviewer, company, policy key, or policy revision. The chat-intent primitive is described in its own section below.

## Relationship to the locked workbench architecture

Native Odoo Discuss and chatter remain the intended human workbench. A human must be able to ask Mack for cited knowledge and offer insight without delegating the offer; a CWI may be created or revised from chat, a web-lead handoff, an Odoo event, or a human work session. This module does not limit those flows to HOT leads and does not implement their chat adapter, KB retrieval, CWI persistence, matching request, or reasoning response.

## Native chat-intent receipts

An authenticated internal Odoo user may call `record_intent_from_source_message` for their own native chatter comment on a canonical intake. Odoo resolves the user, active company, intake access, source-message thread binding, optional message attachment references, and observed intake write timestamp on the server. It stores an immutable receipt and exposes a read-only intake smart button. It does not copy attachment bytes, post an additional message, schedule an activity, call Mack, invoke Gate/CEG, mutate a CWI, execute a commercial action, or send email.

The current `plasticos.intake` model has no canonical company field. To avoid asserting a tenant boundary that the target cannot prove, this primitive rejects multi-company Odoo contexts until an explicit intake company scope and record rule exist. The captured `canonical_write_date` is an observation only; it is not a compare-and-set revision and cannot authorize a later mutation.

A verified HOT web lead is one important **automatic ingress** to the larger workbench: Odoo triages it, creates the canonical intake, and may later invoke this generic review primitive. It is not the sole eligible source of human consultation or review. The Odoo HOT-routing module retains its own specialized reviewer behavior; this module does not borrow that configuration or rely on `plasticos_web_leads`.

## Scope

A review request binds the canonical intake, CWI reference and revision, decision-snapshot hash, candidate action, reason, bounded risk codes and evidence references, deadline, company scope, reviewer-routing policy revision, and idempotency key. It creates one standard Odoo activity on the intake and one internal chatter audit note. The request is immutable and retained for audit.

This module is deliberately **not an approval engine**. It does not grant Mack authority, create or edit a PO/SO or offer, send external email, invoke matching, call Cognitive Engine Graphs, submit to Constellation Gate, mutate a CWI, or dispatch freight. A review request is attention and audit—not an approval, mandate, or authority grant.

## Supervisor decisions and sanctioned retries

A supervisor may use their existing Odoo permissions to update an authoritative Odoo offer or other canonical record. Mack must subsequently rehydrate from the resulting Odoo receipt or revision; this review request never makes a human edit authoritative to Mack on its own.

A supervisor may eventually authorize a **sanctioned retry**, but that requires a separate governed review-outcome capability. That future capability must bind the immutable review request, exact CWI revision, decision-snapshot hash, reviewer identity and authorization, explicit outcome, allowed retry action, expected canonical Odoo revision, expiry, idempotency key, and authoritative Odoo receipt. It is not implemented by this module, and no retry can be inferred from an activity completion, chatter message, or an edited offer.

## Delivery constraint

The code creates a native Odoo activity and does not call Odoo mail-send APIs. Odoo instance notification preferences may still be capable of generating email from an activity; production activation must therefore prove that the assigned reviewer receives an **in-app-only** notification under the intended Odoo mail configuration. That configuration verification is intentionally outside this module and remains a release gate.

## Prerequisites

1. Install `plasticos_intake`.
2. Create exactly one active **Mack Workbench Routing** record for every company that may receive a request, with an active internal Odoo reviewer.
3. Grant appropriate users the `Mack Workbench Operator` or `Mack Workbench Manager` role.
4. Run the module’s Odoo database regression test and the production in-app-only notification proof before enabling any service that creates requests.
