---
auto_generated: false
authority: derived-index
component_id: plasticos_ops_dashboard
component_name: PlasticOS Operations Manager Workbench
module_version: 19.0.1.0.0
installable: true
auto_install: false
application: false
depends:
  - mail
  - account
  - plasticos_security_base
  - plasticos_documents
  - plasticos_documents_native
  - plasticos_logistics
  - plasticos_claims
  - plasticos_commission
models_owned:
  - plasticos.ops.workbench
  - plasticos.ops.request.correction
models_extended:
  - mail.activity
crons: []
---

# PlasticOS Operations Manager Workbench

The front matter above is a derived index. `__manifest__.py` and the `_name` / `_inherit` lines in `models/` win on any conflict.

## What it does

The Operations Manager's inbox (DEC-004, TASK-040). It is presentation and workflow only: it stores no queue,
copies no business record, ranks nothing and runs no AI. Every item it shows already exists.

| Queue | Source | Domain owner |
| --- | --- | --- |
| Mine, Team, Unassigned, Escalated | `mail.activity` of the `plasticos_documents` exception types (DEC-012) | `plasticos.ops.workbench._kpi_domain` |
| Classification Reviews, Document Gaps, Held Vendor Bills | the same activities, by exception class | same |
| Linda Approvals for Operations | pending `plasticos.linda.approval` of the DEC-011 Operations classes | same |
| Escalated or Overdue Claims | open `plasticos.claim`, company from the transaction's sale order (DEC-008) | same |

Team, Escalated and Document Gaps show only activities owned by an Operations Manager, so Logistics-owned work
(DEC-010) is never duplicated here.

## How it works

- Each queue is declared once (`WORKBENCH_KPIS` + `_kpi_domain`). `kpi_values()` counts with `search_count` on the
  same domain `action_open_kpi()` opens, so a count always equals its drill (DEC-007).
- Company scope comes from the records' own rules: `mail.activity` hides activities whose record the user cannot read,
  and Linda approvals and claims are filtered to the user's companies.
- The review surface is a form on the activity itself: original file, candidate facts (labelled as not verified;
  UNKNOWN stays UNKNOWN), the linked record's current values, the discrepancy (the activity note), owner and due date.
  Every value is read with the reviewer's own access, never through sudo.
- Buttons call existing commands: Confirm Classification opens the original's Correct Classification command
  (TASK-070, DEC-015); `action_open_document` opens the original or AP/AR record, where the association command and
  the record's own actions live. Return to Logistics (`action_plasticos_return_to_logistics`) reassigns the
  one activity to the Logistics owner chosen by the DEC-010 router; it refuses Operations-only classes, non-Operations
  users and a company with no Logistics owner. The router re-evaluates the activity the next time its writer runs.
- Request Correction (`plasticos.ops.request.correction`, transient) takes a required reason, posts an internal note
  on the record and adds the reason to the same activity, due today, with the same routed owner. It sends nothing
  outside the company (Linda stays the only external chase sender) and does not edit the document or its evidence.

## Security

- Menus and server actions: `plasticos_security_base.group_operations_manager` only (DEC-005 b).
- `plasticos.claim`: read-only ACL for the Operations Manager (DEC-005 a). No write.

## Models

| Model | Kind | File |
| --- | --- | --- |
| `plasticos.ops.workbench` | owned, abstract | `models/ops_workbench.py` |
| `mail.activity` | extended (non-stored review fields, Return to Logistics) | `models/mail_activity.py` |
| `plasticos.ops.request.correction` | owned, transient (one-click reason) | `models/request_correction.py` |

## Runtime

- No cron. `auto_install` is false: install it by name.
- Views and menus: `views/ops_workbench_views.xml`. Access: `security/ir.model.access.csv`.
