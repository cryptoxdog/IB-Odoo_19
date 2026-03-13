import logging

_logger = logging.getLogger(__name__)

_MODULE = "plasticos_security_base"

_USER_GROUPS = {
    "user_igor": [
        "base.group_system",
        "base.group_no_one",
        "plasticos_security_base.group_system_admin",
    ],
    "user_arthur": [
        "base.group_user",
        "plasticos_security_base.group_sales_rep",
    ],
}


def post_init_hook(env):
    """Assign security groups to admin/test users via SQL.

    Odoo 19 removed groups_id from res.users XML create, so group
    membership must be written directly to the relation table.
    """
    for xml_id, group_refs in _USER_GROUPS.items():
        user_data = env["ir.model.data"].sudo().search(
            [("module", "=", _MODULE), ("name", "=", xml_id)], limit=1
        )
        if not user_data:
            _logger.warning(
                "post_init_hook [%s]: user %s not found – skipping.",
                _MODULE, xml_id,
            )
            continue

        uid = user_data.res_id

        for gref in group_refs:
            group = env.ref(gref, raise_if_not_found=False)
            if not group:
                _logger.warning(
                    "post_init_hook [%s]: group %s not found – skipping.",
                    _MODULE, gref,
                )
                continue
            env.cr.execute(
                """
                INSERT INTO res_groups_users_rel (gid, uid)
                VALUES (%s, %s)
                ON CONFLICT DO NOTHING
                """,
                (group.id, uid),
            )

        _logger.info(
            "post_init_hook [%s]: granted groups %s to user %s.",
            _MODULE, group_refs, xml_id,
        )
