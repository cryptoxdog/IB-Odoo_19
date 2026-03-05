"""Post-install hooks for plasticos_enrichment module."""

import logging

_logger = logging.getLogger(__name__)


def post_init_hook(env):
    """
    Assign enrichment manager group to system_cron user for ACL-safe cron execution.

    Odoo 19 approach: groups assigned via Python post-install hook.
    """
    _logger.info("plasticos_enrichment post_init_hook: Configuring cron user groups")

    cron_user = env.ref("plasticos_base.user_system_cron", raise_if_not_found=False)
    if not cron_user:
        _logger.warning("user_system_cron not found, skipping group assignment")
        return

    enrichment_group = env.ref("plasticos_enrichment.group_enrichment_manager", raise_if_not_found=False)
    if enrichment_group:
        # Odoo 19: Add user to group via group.users (not user.groups_id)
        enrichment_group.sudo().write({"users": [(4, cron_user.id)]})
        _logger.info(
            "Added system_cron user to group_enrichment_manager (id=%d)",
            enrichment_group.id,
        )
    else:
        _logger.warning("group_enrichment_manager not found")
