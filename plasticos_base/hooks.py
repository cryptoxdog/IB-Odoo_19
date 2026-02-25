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
        # Use (4, id) to add without removing existing groups
        cron_user.sudo().write({"groups_id": [(4, gid) for gid in groups_to_add]})
        _logger.info(
            "Added %d groups to system_cron user: %s",
            len(groups_to_add),
            groups_to_add,
        )
    else:
        _logger.info("No additional groups found to add to system_cron user")
