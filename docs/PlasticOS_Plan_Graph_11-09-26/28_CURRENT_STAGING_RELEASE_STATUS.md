# GitHub checkpoint and required hosted Production receipts | 2026-11-09

- GitHub Production head: `729d3ab0b7cd7a0cb1058528e7c0e28cdcc08b56` (the Nov 8 PR #408 merged tree). GitHub Staging head: `bdc222246fbfb647e8e008046b759eecd60a2028`. Staging has newer changes; PR #418 was open in this snapshot.
- GitHub PR #408: CODE MERGE COMPLETE, **not proof of Odoo.sh hosting**. Native module installation, Admin auto_install=False requirement, and database state still need checks.
- Admin root menu / Command Center in `plasticos_admin_dashboard/views/admin_dashboard_views.xml`: SOURCE OBSERVED, LIVE USER ACCESS UNKNOWN. Admin action opens `plasticos.load.dashboard` as a list; legacy closed load rows older than current month are absent by SQL VIEW `WHERE` (current source mismatch with all-load promise).
- ERP/CRM import code and historical lifecycle are in merged source. Full eligible ERP + CRM + transaction population imported to Production: **UNKNOWN** until read-only census. Nov 8 seven-gate rehearsal is not full-volume evidence.
- Documents delegate verification, and transaction `load_ids` exists. Source implementation present; Production interactive proof pending.
- Functional QA not run in this update. Matching/enrichment explicitly excluded; Export next after acceptance.

**Accept test-ready Production** when exact build + module list, source-vs-target import counts, Admin access and baseline critical navigation are attested. **Accept Export start** only after web-lead/logistics/Documents core smoke and full UI sweep with P0/P1 findings disposed. No unrelated refactors to satisfy generic 'bloat' targets.
