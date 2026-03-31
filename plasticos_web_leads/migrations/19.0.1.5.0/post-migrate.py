"""Migration 19.0.1.5.0 — safe default for missing perplexity_api_key.

This post-migration ensures the plasticos_web_lead_config table does not
have NULL in the api_key column for records where it was never set.
It also back-fills the perplexity_api_key ICP parameter with an empty
string sentinel so code that calls get_param() does not get None back
and fail a truthiness check unexpectedly.

Safe to run multiple times (idempotent).
"""
from __future__ import annotations

import logging

_logger = logging.getLogger(__name__)

_ICP_PERPLEXITY_KEY = "plasticos.inference.perplexity_api_key"
_SENTINEL = ""  # empty string — signals "not configured" without NULL chaos


def migrate(cr, version):
    """Apply safe defaults for missing perplexity_api_key."""
    _logger.info("plasticos_web_leads 19.0.1.5.0 post-migrate: patching perplexity_api_key default")

    # 1. ICP table: insert sentinel if missing (do not overwrite existing value)
    cr.execute(
        """
        INSERT INTO ir_config_parameter (key, value, create_date, write_date, create_uid, write_uid)
        SELECT
            %(key)s,
            %(val)s,
            NOW(),
            NOW(),
            1,
            1
        WHERE NOT EXISTS (
            SELECT 1 FROM ir_config_parameter WHERE key = %(key)s
        )
        """,
        {"key": _ICP_PERPLEXITY_KEY, "val": _SENTINEL},
    )

    # 2. web lead config table: ensure api_key is never NULL (breaks controller auth check)
    #    Only update rows where api_key IS NULL — do not touch rows that have a real key.
    cr.execute(
        """
        UPDATE plasticos_web_lead_config
        SET api_key = ''
        WHERE api_key IS NULL
        """
    )

    _logger.info(
        "plasticos_web_leads 19.0.1.5.0 post-migrate: complete (ICP sentinel + api_key NULL guard)"
    )
