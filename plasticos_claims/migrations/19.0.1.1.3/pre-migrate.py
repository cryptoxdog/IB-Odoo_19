"""Snapshot claim.load_id and refuse a load that is not the claim's transaction."""

import logging

_logger = logging.getLogger(__name__)


def _has_column(cr, table, column):
    cr.execute(
        """
        SELECT 1
          FROM information_schema.columns
         WHERE table_name = %s
           AND column_name = %s
        """,
        (table, column),
    )
    return cr.fetchone() is not None


def migrate(cr, version):
    if not version:
        return
    cr.execute("SELECT to_regclass('public.plasticos_claim')")
    if cr.fetchone()[0] is None or not _has_column(cr, "plasticos_claim", "load_id"):
        return
    if _has_column(cr, "plasticos_load", "transaction_id"):
        cr.execute(
            """
            SELECT c.id, c.transaction_id, c.load_id, l.transaction_id
              FROM plasticos_claim c
              JOIN plasticos_load l ON l.id = c.load_id
             WHERE c.load_id IS NOT NULL
               AND l.transaction_id IS DISTINCT FROM c.transaction_id
             ORDER BY c.id
            """
        )
    else:
        cr.execute(
            """
            SELECT c.id, c.transaction_id, c.load_id, t.load_id
              FROM plasticos_claim c
              JOIN plasticos_transaction t ON t.id = c.transaction_id
             WHERE c.load_id IS NOT NULL
               AND t.load_id IS DISTINCT FROM c.load_id
             ORDER BY c.id
            """
        )
    conflicts = cr.fetchall()
    cr.execute(
        """
        SELECT c.id, c.load_id
          FROM plasticos_claim c
         WHERE c.load_id IS NOT NULL
           AND NOT EXISTS (SELECT 1 FROM plasticos_load l WHERE l.id = c.load_id)
         ORDER BY c.id
        """
    )
    conflicts.extend(cr.fetchall())
    if conflicts:
        raise RuntimeError(
            f"plasticos claim load migration refused. Resolve these claim rows before upgrading: {conflicts}"
        )
    cr.execute(
        """
        CREATE TABLE IF NOT EXISTS plasticos_claim_load_link_preserve (
            claim_id integer PRIMARY KEY,
            load_id integer,
            transaction_id integer NOT NULL
        )
        """
    )
    cr.execute(
        """
        INSERT INTO plasticos_claim_load_link_preserve (claim_id, load_id, transaction_id)
        SELECT c.id, c.load_id, c.transaction_id
          FROM plasticos_claim c
         WHERE c.transaction_id IS NOT NULL
        ON CONFLICT (claim_id) DO NOTHING
        """
    )
    _logger.info("plasticos_claims pre-migrate snapshotted claim load links")
