import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Backfill company_role on existing res.partner records.

    supplier_rank > 0  ->  supplier  (primary business is buying from suppliers)
    customer_rank > 0  ->  buyer
    is_company = TRUE  ->  prospect
    person contacts    ->  NULL

    Idempotent: only touches rows where company_role IS NULL.
    """
    _logger.info("[5.0.0 migration] Backfilling company_role on res.partner")

    cr.execute("""
        UPDATE res_partner
        SET company_role = CASE
            WHEN supplier_rank > 0  THEN 'supplier'
            WHEN customer_rank > 0  THEN 'buyer'
            WHEN is_company = TRUE  THEN 'prospect'
            ELSE NULL
        END
        WHERE company_role IS NULL
    """)

    cr.execute("SELECT COUNT(*) FROM res_partner WHERE company_role IS NOT NULL")
    total = cr.fetchone()[0]
    _logger.info("[5.0.0 migration] company_role backfill complete: %d partners populated", total)
