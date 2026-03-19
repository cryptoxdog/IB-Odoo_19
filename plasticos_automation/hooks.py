import logging

_logger = logging.getLogger(__name__)


def _merge_automation_groups_into_settings(env):
    """Settings / Admin users should imply automation groups (was XML on base.group_system)."""
    sys_group = env.ref("base.group_system", raise_if_not_found=False)
    if not sys_group:
        return
    g_mgr = env.ref(
        "plasticos_automation.group_plasticos_automation_manager",
        raise_if_not_found=False,
    )
    g_log = env.ref(
        "plasticos_automation.group_logistics_automation_manager",
        raise_if_not_found=False,
    )
    if not g_mgr or not g_log:
        _logger.warning(
            "post_init_hook [plasticos_automation]: automation groups not found — skip Settings merge",
        )
        return
    extra = g_mgr | g_log
    missing = extra - sys_group.implied_ids
    if missing:
        # sudo: writing implied_ids on base.group_system is restricted for normal users
        sys_group.sudo().write({"implied_ids": [(4, g.id) for g in missing]})
        _logger.info(
            "post_init_hook [plasticos_automation]: merged groups into base.group_system: %s",
            missing.mapped("full_name"),
        )


def post_init_hook(env):
    """Assign cron-job users to this module's security groups.

    Without this, scheduled actions may run as OdooBot (or another user)
    that lacks the ACL grants defined by the module, causing
    ``AccessError`` at runtime.
    """
    _merge_automation_groups_into_settings(env)

    _module = "plasticos_automation"

    # ── discover crons owned by this module ──────────────────────────
    cron_data = (
        env["ir.model.data"]
        .sudo()
        .search(
            [
                ("module", "=", _module),
                ("model", "=", "ir.cron"),
            ]
        )
    )
    if not cron_data:
        _logger.info(
            "post_init_hook [%s]: no ir.cron records found – nothing to do.",
            _module,
        )
        return

    crons = env["ir.cron"].sudo().browse(cron_data.mapped("res_id")).exists()

    # ── discover security groups owned by this module ────────────────
    group_data = (
        env["ir.model.data"]
        .sudo()
        .search(
            [
                ("module", "=", _module),
                ("model", "=", "res.groups"),
            ]
        )
    )
    groups = env["res.groups"].sudo().browse(group_data.mapped("res_id")).exists()
    if not groups:
        _logger.info(
            "post_init_hook [%s]: no security groups defined – skipping.",
            _module,
        )
        return

    # ── ensure every cron user belongs to every module group ─────────
    for cron in crons:
        user = cron.user_id
        if not user:
            continue
        missing = groups - user.group_ids
        if missing:
            # Odoo 19: Use direct SQL for user-group assignment during module loading
            for g in missing:
                env.cr.execute(
                    """
                    INSERT INTO res_groups_users_rel (gid, uid)
                    VALUES (%s, %s)
                    ON CONFLICT DO NOTHING
                    """,
                    (g.id, user.id),
                )
            _logger.info(
                "post_init_hook [%s]: granted groups %s to cron user %s (cron: %s).",
                _module,
                missing.mapped("full_name"),
                user.login,
                cron.name,
            )
