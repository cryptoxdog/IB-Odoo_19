import logging

_logger = logging.getLogger(__name__)

_MODULE = "plasticos_security_base"

# Full platform access for both seed admins in admin_users.xml (ib@ + ab@).
# Keep them identical: previously ib had only “superadmin” triple and ab had
# sales_rep + operations_manager — divergency caused confusing Settings/Apps UX.
_COFOUNDER_SEED_ADMIN_GROUPS = [
    "base.group_system",
    "base.group_no_one",
    "base.group_erp_manager",
    "base.group_user",
    "base.group_partner_manager",
    "plasticos_security_base.group_system_admin",
    "plasticos_security_base.group_sales_rep",
    "plasticos_security_base.group_operations_manager",
]

_SALES_REP_GROUPS = [
    "base.group_user",
    "plasticos_security_base.group_sales_rep",
]

# XML IDs must match plasticos_base/data/admin_users.xml (user_admin_*)
# and plasticos_base/data/sales_reps.xml (user_sales_rep_*).
_USER_GROUPS = {
    "plasticos_base.user_admin_ib": _COFOUNDER_SEED_ADMIN_GROUPS,
    "plasticos_base.user_admin_ab": _COFOUNDER_SEED_ADMIN_GROUPS,
    "plasticos_base.user_sales_rep_lm": _SALES_REP_GROUPS,
    "plasticos_base.user_sales_rep_rp": _SALES_REP_GROUPS,
    "plasticos_base.user_sales_rep_aa": _SALES_REP_GROUPS,
    "plasticos_base.user_sales_rep_tw": _SALES_REP_GROUPS,
}


def grant_seed_user_groups(env):
    """Assign security groups to PlasticOS seed users via SQL (Odoo 19-safe)."""
    for full_xml_id, group_refs in _USER_GROUPS.items():
        user = env.ref(full_xml_id, raise_if_not_found=False)
        if not user:
            _logger.warning(
                "grant_seed_user_groups [%s]: user %s not found – skipping.",
                _MODULE,
                full_xml_id,
            )
            continue

        for gref in group_refs:
            group = env.ref(gref, raise_if_not_found=False)
            if not group:
                _logger.warning(
                    "grant_seed_user_groups [%s]: group %s not found – skipping.",
                    _MODULE,
                    gref,
                )
                continue
            env.cr.execute(
                """
                INSERT INTO res_groups_users_rel (gid, uid)
                VALUES (%s, %s)
                ON CONFLICT DO NOTHING
                """,
                (group.id, user.id),
            )

        _logger.info(
            "grant_seed_user_groups [%s]: granted groups %s to user %s.",
            _MODULE,
            group_refs,
            full_xml_id,
        )


def post_init_hook(env):
    """Assign security groups to users via SQL.

    Odoo 19 removed groups_id from res.users XML create, so group
    membership must be written directly to the relation table.
    """
    grant_seed_user_groups(env)
