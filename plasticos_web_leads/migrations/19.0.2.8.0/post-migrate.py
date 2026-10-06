"""Backfill provider identity for leads admitted before the inbound port."""

from __future__ import annotations

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Set the historical provider on rows that predate provider_key."""
    cr.execute(
        """
        UPDATE plasticos_web_lead
           SET provider_key = 'cognito'
         WHERE provider_key IS NULL
        """
    )
    cr.execute(
        """
        UPDATE plasticos_web_lead_config
           SET inbound_default_provider_key = COALESCE(NULLIF(inbound_default_provider_key, ''), 'cognito')
        """
    )
    _logger.info("plasticos_web_leads 19.0.2.8.0 post-migrate: inbound provider keys backfilled")
