"""Post-install hooks for plasticos_claims module."""

import logging

_logger = logging.getLogger(__name__)


def post_init_hook(env):
    """
    Assign claims manager group to system_cron user for ACL-safe cron execution.

    Odoo 19 approach: groups assigned via Python post-install hook.
    """
    _logger.info("plasticos_claims post_init_hook: Configuring cron user groups")

    cron_user = env.ref("plasticos_base.user_system_cron", raise_if_not_found=False)
    if not cron_user:
        _logger.warning("user_system_cron not found, skipping group assignment")
        return

    claims_group = env.ref("plasticos_claims.group_claims_manager", raise_if_not_found=False)
    if claims_group:
        cron_user.sudo().write({"groups_id": [(4, claims_group.id)]})
        _logger.info(
            "Added group_claims_manager (id=%d) to system_cron user",
            claims_group.id,
        )
    else:
        _logger.warning("group_claims_manager not found")
