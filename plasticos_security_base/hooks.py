import logging

_logger = logging.getLogger(__name__)

_MODULE = "plasticos_security_base"

_SUPERADMIN_GROUPS = [
    "base.group_system",
    "base.group_no_one",
    "plasticos_security_base.group_system_admin",
]

_OPS_MANAGER_GROUPS = [
    "base.group_user",
    "plasticos_security_base.group_sales_rep",
    "plasticos_security_base.group_operations_manager",
]

_SALES_REP_GROUPS = [
    "base.group_user",
    "plasticos_security_base.group_sales_rep",
]

_USER_GROUPS = {
    "plasticos_base.user_sales_rep_ib": _SUPERADMIN_GROUPS,
    "plasticos_base.user_sales_rep_ab": _OPS_MANAGER_GROUPS,
    "plasticos_base.user_sales_rep_lm": _SALES_REP_GROUPS,
    "plasticos_base.user_sales_rep_rp": _SALES_REP_GROUPS,
    "plasticos_base.user_sales_rep_aa": _SALES_REP_GROUPS,
    "plasticos_base.user_sales_rep_tw": _SALES_REP_GROUPS,
}


def post_init_hook(env):
    """Assign security groups to users via SQL.

    Odoo 19 removed groups_id from res.users XML create, so group
    membership must be written directly to the relation table.
    """
    for full_xml_id, group_refs in _USER_GROUPS.items():
        user = env.ref(full_xml_id, raise_if_not_found=False)
        if not user:
            _logger.warning(
                "post_init_hook [%s]: user %s not found – skipping.",
                _MODULE,
                full_xml_id,
            )
            continue

        for gref in group_refs:
            group = env.ref(gref, raise_if_not_found=False)
            if not group:
                _logger.warning(
                    "post_init_hook [%s]: group %s not found – skipping.",
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
            "post_init_hook [%s]: granted groups %s to user %s.",
            _MODULE,
            group_refs,
            full_xml_id,
        )
