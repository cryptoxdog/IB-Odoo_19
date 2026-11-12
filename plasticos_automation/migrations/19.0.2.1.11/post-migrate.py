"""Backfill the derived account.move.transaction_id (operator decision 2026-11-12).

``account.move.transaction_id`` is now a stored projection of the links
``plasticos.transaction`` owns (``customer_invoice_id``, ``vendor_bill_ids``,
``freight_bill_ids``). The column already existed, so the ORM does not compute
it for existing rows on upgrade.

Set-based SQL on purpose: a move linked by exactly one transaction gets it,
every other move is emptied, and the dependent stored ``commission_amount``
follows. No ORM write happens, so no automation rule fires and no penalty is
calculated for historical invoices by this upgrade.
"""

import logging

_logger = logging.getLogger(__name__)

# Moves linked by exactly one transaction; shared by both statements below.
_OWNERS = """
    WITH links AS (
        SELECT customer_invoice_id AS move_id, id AS transaction_id
          FROM plasticos_transaction
         WHERE customer_invoice_id IS NOT NULL
        UNION
        SELECT account_move_id, plasticos_transaction_id FROM plasticos_tx_vendor_rel
        UNION
        SELECT account_move_id, plasticos_transaction_id FROM plasticos_tx_freight_rel
    ),
    owners AS (
        SELECT move_id, MIN(transaction_id) AS transaction_id
          FROM links
         GROUP BY move_id
        HAVING COUNT(DISTINCT transaction_id) = 1
    )
"""

_CLEAR = (
    _OWNERS
    + """
    UPDATE account_move move
       SET transaction_id = NULL, commission_amount = 0
     WHERE move.transaction_id IS NOT NULL
       AND NOT EXISTS (
           SELECT 1 FROM owners
            WHERE owners.move_id = move.id AND owners.transaction_id = move.transaction_id
       )
"""
)

_SET = (
    _OWNERS
    + """
    UPDATE account_move move
       SET transaction_id = owners.transaction_id,
           commission_amount = COALESCE(tx.commission_amount, 0)
      FROM owners
      JOIN plasticos_transaction tx ON tx.id = owners.transaction_id
     WHERE owners.move_id = move.id
       AND (
           move.transaction_id IS DISTINCT FROM owners.transaction_id
           OR move.commission_amount IS DISTINCT FROM COALESCE(tx.commission_amount, 0)
       )
"""
)


def migrate(cr, version):
    cr.execute(_CLEAR)
    cleared = cr.rowcount
    cr.execute(_SET)
    _logger.info(
        "plasticos_automation 19.0.2.1.11: account.move.transaction_id backfilled: set=%s cleared=%s",
        cr.rowcount,
        cleared,
    )
