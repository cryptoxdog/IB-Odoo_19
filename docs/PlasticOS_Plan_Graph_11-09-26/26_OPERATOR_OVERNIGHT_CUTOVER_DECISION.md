# Operator Production/testing/Export decision | 2026-11-09

**Accepted intent, not evidence of execution:** Production should be running the appropriate code with all eligible ERP/CRM contacts/transaction history imported and ready for thorough testing today. This is a **testable Product**, not final financial-system ownership or a claim of no bugs.

**Operational order:** pin and inspect actual Odoo.sh Production -> establish complete read-only source/target import reconciliation -> access Admin and dashboards with authorized account -> run safe basic feature smoke for web lead qualification, logistics automations and Documents automations -> sweep all installed interactive UI actions with real logs -> triage and eliminate unnecessary duplicate surface within actual scope -> begin separately authorized Export implementation integrating existing domains.

**Critical boundaries:** No CEG matching, no EIE enrichment or elective AI activation during basic test phase. No live outbound mail, posting, payment or stock movement merely because a QA operator clicked an action. The historical ERP archive, QuickBooks opening trial balance and go-live financial writer change require their own evidence/authorization.

**Admin:** Code has root Admin menu guarded by `group_system_admin`; `plasticos_admin_dashboard` is not auto-installed. Verify actual module/user entitlement in Production. The 'all loads' dashboard claim is currently contradicted by its SQL filter for old closed loads, so make a scoped existing-owner correction or formally redefine the displayed population.

**Next Export:** May be designed after core Production QA but may not be written/deployed automatically by this plan ZIP. Preserve existing Export BRS 111/history as reference rather than making old donor drafts canonical.
