"""Historical rows keep their subjects. Unproven links stay review and are not re-accepted."""

import logging

_logger = logging.getLogger(__name__)

_SUBJECTS = (
    "plasticos.transaction",
    "plasticos.load",
    "purchase.order",
    "sale.order",
    "stock.picking",
)


def migrate(cr, version):
    cr.execute(
        """
        SELECT 1
          FROM information_schema.columns
         WHERE table_name = 'plasticos_document'
           AND column_name = 'association_state'
        """
    )
    if not cr.fetchone():
        return
    cr.execute(
        """
        UPDATE plasticos_document
           SET association_state = 'accepted'
         WHERE association_state = 'pending'
           AND associated_by IS NULL
           AND (verified OR override)
           AND evidence_digest IS NOT NULL
           AND res_model IN %s
        """,
        (tuple(_SUBJECTS),),
    )
    accepted = cr.rowcount
    cr.execute(
        """
        UPDATE plasticos_document
           SET association_state = 'review',
               association_review_required = true
         WHERE association_state = 'pending'
           AND associated_by IS NULL
           AND res_model IN %s
        """,
        (tuple(_SUBJECTS),),
    )
    _logger.info(
        "Document association migration kept %s proven rows and marked %s unproven rows for review.",
        accepted,
        cr.rowcount,
    )
