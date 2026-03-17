"""Post-install hooks for plasticos_base module."""

import logging

_logger = logging.getLogger(__name__)


def post_init_hook(env):
    """
    Assign required groups to system_cron user for ACL-safe cron execution.

    This is the Odoo 19 recommended approach - groups are assigned via Python
    post-install hook rather than groups_id in XML (which is deprecated).

    Groups needed for cron jobs:
    - plasticos_enrichment.group_enrichment_manager (for enrichment crons)
    - plasticos_documents.group_documents_manager (for document crons)
    - plasticos_claims.group_claims_manager (for claims crons)
    """
    _logger.info("plasticos_base post_init_hook: Configuring system_cron user groups")

    # Grant full admin groups to both admin users (idempotent on every rebuild)
    # Uses raise_if_not_found=False so missing modules don't break the hook
    admin_groups = [
        # ═══════════════════════════════════════════════════════════════════
        # ODOO CORE / ENTERPRISE GROUPS
        # ═══════════════════════════════════════════════════════════════════
        "base.group_system",  # Settings / Technical Features
        "base.group_erp_manager",  # Access Rights
        "base.group_user",  # Internal User
        "base.group_partner_manager",  # Contact Creation
        # Sales & Purchase
        "sales_team.group_sale_manager",  # Sales Manager
        "purchase.group_purchase_manager",  # Purchase Manager
        "purchase.group_purchase_user",  # Purchase User
        # Accounting
        "account.group_account_manager",  # Invoicing Manager
        "account.group_account_user",  # Invoicing User
        # Inventory
        "stock.group_stock_manager",  # Inventory Manager
        "stock.group_stock_user",  # Inventory User
        # Documents (Enterprise)
        "documents.group_documents_manager",  # Documents Manager
        "documents.group_documents_user",  # Documents User
        # HR & Recruitment (Enterprise)
        "hr.group_hr_manager",  # HR Manager
        "hr.group_hr_user",  # HR User
        "hr_recruitment.group_hr_recruitment_manager",  # Recruitment Manager
        "hr_expense.group_hr_expense_manager",  # Expense Manager
        "hr_timesheet.group_timesheet_manager",  # Timesheet Manager
        # Helpdesk (Enterprise)
        "helpdesk.group_helpdesk_manager",  # Helpdesk Manager
        "helpdesk.group_helpdesk_user",  # Helpdesk User
        # Sign (Enterprise)
        "sign.group_sign_manager",  # Sign Manager
        "sign.group_sign_user",  # Sign User
        # Planning (Enterprise)
        "planning.group_planning_manager",  # Planning Manager
        # Manufacturing
        "mrp.group_mrp_manager",  # MRP Manager
        # Quality (Enterprise)
        "quality.group_quality_manager",  # Quality Manager
        # Maintenance
        "maintenance.group_equipment_manager",  # Equipment Manager
        # CRM
        "crm.group_use_lead",  # Use Leads
        # Project
        "project.group_project_user",  # Project User (top level)
        # Approvals (Enterprise)
        "approvals.group_approval_user",  # Approvals User
        # ═══════════════════════════════════════════════════════════════════
        # PLASTICOS CUSTOM GROUPS
        # ═══════════════════════════════════════════════════════════════════
        "plasticos_security_base.group_system_admin",  # Plasticos System Admin
        "plasticos_security_base.group_operations_manager",  # Operations Manager
        "plasticos_security_base.group_qc_manager",  # QC Manager
        "plasticos_enrichment.group_enrichment_manager",  # Enrichment Manager
        "plasticos_documents.group_documents_manager",  # Plasticos Documents Manager
        "plasticos_claims.group_claims_manager",  # Claims Manager
        "plasticos_automation.group_plasticos_automation_manager",  # Automation Manager
        "plasticos_automation.group_logistics_automation_manager",  # Logistics Automation
        "plasticos_transaction.group_plasticos_manager",  # Transaction Manager
        "plasticos_transaction.group_plasticos_commission_manager",  # Commission Manager
    ]

    for admin_login in ("ib@scrapmanagement.com", "ab@scrapmanagement.com"):
        admin_user = env["res.users"].search([("login", "=", admin_login)], limit=1)
        if admin_user:
            for group_xmlid in admin_groups:
                try:
                    group = env.ref(group_xmlid, raise_if_not_found=False)
                    if group:
                        env.cr.execute(
                            """
                            INSERT INTO res_groups_users_rel (gid, uid)
                            VALUES (%s, %s)
                            ON CONFLICT DO NOTHING
                            """,
                            (group.id, admin_user.id),
                        )
                except Exception as e:
                    _logger.warning("Could not grant %s: %s", group_xmlid, e)
            _logger.info("Granted admin groups to %s", admin_login)

    cron_user = env.ref("plasticos_base.user_system_cron", raise_if_not_found=False)
    if not cron_user:
        _logger.warning("user_system_cron not found, skipping group assignment")
        return

    groups_to_add = []

    # Enrichment manager group (if module installed)
    enrichment_group = env.ref("plasticos_enrichment.group_enrichment_manager", raise_if_not_found=False)
    if enrichment_group:
        groups_to_add.append(enrichment_group.id)

    # Documents manager group (if module installed)
    documents_group = env.ref("plasticos_documents.group_documents_manager", raise_if_not_found=False)
    if documents_group:
        groups_to_add.append(documents_group.id)

    # Claims manager group (if module installed)
    claims_group = env.ref("plasticos_claims.group_claims_manager", raise_if_not_found=False)
    if claims_group:
        groups_to_add.append(claims_group.id)

    if groups_to_add:
        # Odoo 19: Use direct SQL for user-group assignment during module loading
        for gid in groups_to_add:
            env.cr.execute(
                """
                INSERT INTO res_groups_users_rel (gid, uid)
                VALUES (%s, %s)
                ON CONFLICT DO NOTHING
                """,
                (gid, cron_user.id),
            )
        _logger.info(
            "Added system_cron user to %d groups: %s",
            len(groups_to_add),
            groups_to_add,
        )
    else:
        _logger.info("No additional groups found to add to system_cron user")
