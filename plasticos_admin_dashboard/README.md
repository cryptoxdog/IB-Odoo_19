---
auto_generated: false
authority: derived-index
component_id: plasticos_admin_dashboard
component_name: PlasticOS Admin Dashboard
module_version: 19.0.1.1.4
layer: 3
installable: true
auto_install: false
application: false
depends:
  - plasticos_base
  - plasticos_intake
  - plasticos_offer
  - plasticos_transaction
  - plasticos_logistics
  - plasticos_commission
  - plasticos_web_leads
  - plasticos_security_base
  - plasticos_crm_bridge
models_owned:
  - plasticos.admin.kpi
  - plasticos.rep.performance
models_extended: []
crons:
  - cron_refresh_admin_kpi
---

# PlasticOS Admin Dashboard

The front matter above is a derived index. `__manifest__.py` and the `_name` / `_inherit` lines in `models/` win on any conflict.

## What it does

A single-screen RevOps command center for admins. One form view shows pipeline health, urgency alerts, rep performance by week, month and year, and web-lead triage statistics. Each alert has a button that opens the matching list.

## How it works

- `plasticos.admin.kpi` is a singleton. `_get_or_create()` returns the first record and creates one when none exists.
- Its KPI fields are non-stored computes (`_compute_kpis`, `_compute_ai_config`) that read live counts with SQL. `_compute_kpis` fills these groups: intakes, offers, transactions, financials, web leads, and AI stats (web-lead normalization, vision, HOT/COLD decisions, auto-created intakes, manual overrides, pending review).
- `_compute_ai_config` reports whether web-lead AI, vision, and an OpenAI key are configured. It reads `plasticos.web.lead.config` only when that model is installed.
- `action_refresh()` recomputes both groups and stamps `last_refresh`. Cron `cron_refresh_admin_kpi` calls it every 15 minutes as `plasticos_base.user_system_cron`.
- The `action_open_*` methods return pre-filtered window actions: sales and logistics dashboards, negative margin, supplier not ready, stalled follow-up, delivered but not invoiced, missing documents, expiring offers, unlocked commission, lead errors, and AI pending review.
- `plasticos.rep.performance` is a read-only SQL view (`_auto = False`) rebuilt in `init()`. It has one row per salesperson per period (WTD, MTD, YTD) built from `plasticos_transaction`, `res_users`, and `res_partner`.

## Models

| Model                       | Kind             | File                        |
| --------------------------- | ---------------- | --------------------------- |
| `plasticos.admin.kpi`       | owned, singleton | `models/admin_dashboard.py` |
| `plasticos.rep.performance` | owned, SQL view  | `models/admin_dashboard.py` |

## Runtime

- Cron: `cron_refresh_admin_kpi`, every 15 minutes, `active` true in `data/cron_refresh_dashboard.xml` (`noupdate="1"`).
- Views: `views/admin_dashboard_views.xml`. Access: `security/ir.model.access.csv`.
- `auto_install` is false. Install it by name.

## Boundaries

- Read-only reporting. It writes no business record except the KPI singleton's `last_refresh`.
- It does not own any counted model. The source tables come from the modules in `depends`.
- The view is rebuilt from SQL in `init()`. A column added to `plasticos.transaction` reaches the view only after this module is upgraded.

## Read next

- [`models/admin_dashboard.py`](models/admin_dashboard.py)
- [`tests/test_rep_performance_view.py`](tests/test_rep_performance_view.py)
- [`../AGENTS.md`](../AGENTS.md)
