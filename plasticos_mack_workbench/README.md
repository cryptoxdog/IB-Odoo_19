# PlasticOS Mack Workbench

`plasticos_mack_workbench` is the **Odoo-native internal-review boundary** for Mack 5.0. It creates a durable, idempotent review request against the canonical `plasticos.intake` created from a **HOT** web lead. The request is routed only through the active internal user configured in `plasticos.web.lead.config.hot_intake_reviewer_id`.

## Scope

A request binds the Odoo intake, CWI reference and revision, decision-snapshot hash, candidate action, reason, bounded risk codes, evidence references, deadline, and idempotency key. The module creates one standard Odoo activity on the intake and writes one internal chatter audit note. The request itself is immutable and retained for audit.

This module is deliberately **not an approval engine**. It does not grant Mack authority, create a PO or SO, send an external email, invoke matching, call Cognitive Engine Graphs, submit to Constellation Gate, mutate a Commercial Work Item, or dispatch freight. A later, separately reviewed slice must define the actual approval decision, user roles, execution receipt, and any Odoo-to-Mack command contract.

## Delivery Constraint

The code creates a native Odoo activity and does not call Odoo mail-send APIs. Odoo instance notification preferences may still be capable of generating email from an activity; production activation must therefore prove that the assigned reviewer receives an **in-app-only** notification under the intended Odoo mail configuration. That configuration verification is intentionally outside this module and remains a release gate.

## Prerequisites

1. Install `plasticos_web_leads` with the explicit HOT reviewer routing feature active.
2. Configure an active, internal `HOT Intake Reviewer` in Web Lead Configuration.
3. Grant the appropriate internal users the `Mack Workbench Operator` role.
4. Run the module’s Odoo database regression test and the production in-app-only notification proof before enabling any service that creates requests.
