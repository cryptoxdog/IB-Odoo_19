"""Pre/Post-install hooks for plasticos_base module."""

import logging

_logger = logging.getLogger(__name__)


def pre_init_hook(env):
    """Clean up duplicate utm.source records before Odoo's utm module loads.

    The utm module creates a native "Referral" record (utm.utm_source_referral).
    If a "Referral" record already exists from a previous migration or manual
    creation, the unique constraint on utm_source.name will fail.

    This hook runs BEFORE utm module loads (plasticos_base doesn't depend on utm),
    so we can safely rename any conflicting records.

    Note: Odoo 19 passes env to pre_init_hook, not raw cursor.
    """
    cr = env.cr
    # Check if utm_source table exists (might not on fresh install)
    cr.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_name = 'utm_source'
        )
    """)
    if not cr.fetchone()[0]:
        _logger.info("pre_init_hook: utm_source table doesn't exist yet, skipping")
        return

    # Check for duplicate "Referral" that would conflict with Odoo's native record
    cr.execute("SELECT id FROM utm_source WHERE name = 'Referral'")
    existing = cr.fetchone()
    if existing:
        # Rename to avoid conflict — Odoo will create its own "Referral"
        cr.execute("UPDATE utm_source SET name = 'Referral (legacy)' WHERE id = %s", (existing[0],))
        _logger.warning(
            "pre_init_hook: Renamed existing 'Referral' utm.source (id=%d) to 'Referral (legacy)' "
            "to avoid conflict with Odoo's native utm.utm_source_referral",
            existing[0],
        )
    else:
        _logger.info("pre_init_hook: No duplicate 'Referral' utm.source found")


def post_init_hook(env):
    """
    Assign required groups to admin users and system_cron user.

    Uses raw SQL on ``res_groups_users_rel`` because Odoo 19 ``res.users`` no
    longer exposes ``groups_id`` for ORM writes; ``group_ids`` in XML still
    applies on create.

    Runs on *module install* only. Upgrades also run
    ``migrations/19.0.1.1.3/post-migrate.py`` which calls this same hook so
    ib@/ab@ keep Settings + Apps access after every ``-u plasticos_base``.
    """
    _logger.info("plasticos_base post_init_hook: Configuring admin and cron user groups")

    # ═══════════════════════════════════════════════════════════════════
    # STEP 1: ALWAYS grant core Odoo groups to admin users (no guard)
    # This ensures ib@ and ab@ can always access Settings
    # ═══════════════════════════════════════════════════════════════════
    core_admin_groups = [
        # Base / System
        "base.group_system",  # Settings / Technical Features
        "base.group_erp_manager",  # Access Rights
        "base.group_user",  # Internal User
        "base.group_partner_manager",  # Contact Creation
        "base.group_no_one",  # Technical Features (for debugging)
        # Sales
        "sales_team.group_sale_manager",  # Sales Manager
        "sales_team.group_sale_salesman_all_leads",  # See All Leads
        "sale.group_sale_order_dates",  # Delivery Date on SO
        # Purchase (all levels for full PO access)
        "purchase.group_purchase_manager",  # Purchase Manager
        "purchase.group_purchase_user",  # Purchase User
        # Accounting (required for PO line access per error message)
        "account.group_account_manager",  # Invoicing Manager
        "account.group_account_user",  # Invoicing User
        "account.group_account_invoice",  # Billing
        "account.group_account_readonly",  # Show Accounting Features - Readonly
        # Inventory (required for PO line access per error message)
        "stock.group_stock_manager",  # Inventory Manager
        "stock.group_stock_user",  # Inventory User
        # CRM
        "crm.group_use_lead",  # Use Leads
    ]

    for admin_login in ("ib@scrapmanagement.com", "ab@scrapmanagement.com"):
        admin_user = env["res.users"].search([("login", "=", admin_login)], limit=1)
        if admin_user:
            for group_xmlid in core_admin_groups:
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
                    _logger.warning("Could not grant %s to %s: %s", group_xmlid, admin_login, e)
            _logger.info("Granted core admin groups to %s", admin_login)

    # ═══════════════════════════════════════════════════════════════════
    # STEP 2: Grant extended groups (Enterprise + Plasticos) - best effort
    # These use raise_if_not_found=False so missing modules don't break
    # ═══════════════════════════════════════════════════════════════════
    extended_admin_groups = [
        # Enterprise modules (may not be installed)
        "documents.group_documents_manager",
        "documents.group_documents_user",
        "hr.group_hr_manager",
        "hr.group_hr_user",
        "hr_recruitment.group_hr_recruitment_manager",
        "hr_expense.group_hr_expense_manager",
        "hr_timesheet.group_timesheet_manager",
        "helpdesk.group_helpdesk_manager",
        "helpdesk.group_helpdesk_user",
        "sign.group_sign_manager",
        "sign.group_sign_user",
        "planning.group_planning_manager",
        "mrp.group_mrp_manager",
        "quality.group_quality_manager",
        "maintenance.group_equipment_manager",
        "project.group_project_user",
        "approvals.group_approval_user",
        # Plasticos custom groups (may not be installed yet)
        "plasticos_security_base.group_system_admin",
        "plasticos_security_base.group_operations_manager",
        "plasticos_security_base.group_qc_manager",
        "plasticos_enrichment.group_enrichment_manager",
        "plasticos_documents.group_documents_manager",
        "plasticos_claims.group_claims_manager",
        "plasticos_automation.group_plasticos_automation_manager",
        "plasticos_automation.group_logistics_automation_manager",
        "plasticos_transaction.group_plasticos_manager",
        "plasticos_transaction.group_plasticos_commission_manager",
    ]

    for admin_login in ("ib@scrapmanagement.com", "ab@scrapmanagement.com"):
        admin_user = env["res.users"].search([("login", "=", admin_login)], limit=1)
        if admin_user:
            for group_xmlid in extended_admin_groups:
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
                    _logger.debug("Could not grant %s to %s: %s", group_xmlid, admin_login, e)
            _logger.info("Granted extended admin groups to %s", admin_login)

    # ═══════════════════════════════════════════════════════════════════
    # STEP 3: Configure system_cron user
    # ═══════════════════════════════════════════════════════════════════
    cron_user = env.ref("plasticos_base.user_system_cron", raise_if_not_found=False)
    if not cron_user:
        _logger.warning("user_system_cron not found, skipping group assignment")
        return

    # Groups needed for cron jobs to access models
    cron_groups = [
        # Core Odoo groups for model access
        "base.group_user",  # Internal User
        "sales_team.group_sale_manager",  # Sales Manager (for sale.order)
        "purchase.group_purchase_manager",  # Purchase Manager (for purchase.order)
        "stock.group_stock_manager",  # Inventory Manager (for stock.picking)
        "account.group_account_manager",  # Invoicing Manager (for account.move)
        # Plasticos custom groups
        "plasticos_enrichment.group_enrichment_manager",
        "plasticos_documents.group_documents_manager",
        "plasticos_claims.group_claims_manager",
        "plasticos_automation.group_plasticos_automation_manager",
        "plasticos_automation.group_logistics_automation_manager",
        "plasticos_transaction.group_plasticos_manager",
    ]

    groups_added = 0
    for group_xmlid in cron_groups:
        try:
            group = env.ref(group_xmlid, raise_if_not_found=False)
            if group:
                env.cr.execute(
                    """
                    INSERT INTO res_groups_users_rel (gid, uid)
                    VALUES (%s, %s)
                    ON CONFLICT DO NOTHING
                    """,
                    (group.id, cron_user.id),
                )
                groups_added += 1
        except Exception as e:
            _logger.warning("Could not grant %s to system_cron: %s", group_xmlid, e)

    _logger.info("Added system_cron user to %d groups", groups_added)
