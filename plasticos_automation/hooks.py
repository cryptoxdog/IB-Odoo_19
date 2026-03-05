import logging

_logger = logging.getLogger(__name__)


def post_init_hook(env):
    """Assign cron-job users to this module's security groups.

    Without this, scheduled actions may run as OdooBot (or another user)
    that lacks the ACL grants defined by the module, causing
    ``AccessError`` at runtime.
    """
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
