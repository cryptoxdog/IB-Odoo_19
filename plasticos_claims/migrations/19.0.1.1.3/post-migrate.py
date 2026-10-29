"""Restore snapshotted claim.load_id values and refuse a sibling rewrite."""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    cr.execute("SELECT to_regclass('public.plasticos_claim_load_link_preserve')")
    if cr.fetchone()[0] is None:
        return
    cr.execute(
        """
        UPDATE plasticos_claim AS c
           SET load_id = s.load_id
          FROM plasticos_claim_load_link_preserve AS s
         WHERE c.id = s.claim_id
           AND c.load_id IS DISTINCT FROM s.load_id
        """
    )
    restored = cr.rowcount
    cr.execute(
        """
        SELECT c.id, s.load_id, c.load_id
          FROM plasticos_claim c
          JOIN plasticos_claim_load_link_preserve s ON s.claim_id = c.id
         WHERE c.load_id IS DISTINCT FROM s.load_id
         ORDER BY c.id
        """
    )
    drifted = cr.fetchall()
    if drifted:
        raise RuntimeError(f"plasticos claim load links changed during upgrade: {drifted}")
    cr.execute(
        """
        SELECT c.id, c.load_id, c.transaction_id, l.transaction_id
          FROM plasticos_claim c
          JOIN plasticos_claim_load_link_preserve s ON s.claim_id = c.id
          LEFT JOIN plasticos_load l ON l.id = c.load_id
         WHERE s.load_id IS NOT NULL
           AND (l.id IS NULL OR l.transaction_id IS DISTINCT FROM c.transaction_id)
         ORDER BY c.id
        """
    )
    invalid = cr.fetchall()
    if invalid:
        raise RuntimeError(f"plasticos claim load links no longer match their transaction: {invalid}")
    cr.execute("DROP TABLE plasticos_claim_load_link_preserve")
    _logger.info("plasticos_claims post-migrate restored %s claim load links", restored)
