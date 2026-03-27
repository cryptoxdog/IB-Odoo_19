import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Backfill company_role on existing res.partner records.

    Logic mirrors _derive_company_role() in partner_import_service:
      supplier_rank > 0 AND customer_rank > 0  ->  both
      supplier_rank > 0                         ->  supplier
      customer_rank > 0                         ->  buyer
      is_company = TRUE, both 0                 ->  prospect
      is_company = FALSE                        ->  NULL (person contact, no role)

    Idempotent: only touches rows where company_role IS NULL.
    """
    _logger.info("[5.0.0 migration] Backfilling company_role on res.partner")

    cr.execute("""
        UPDATE res_partner
        SET company_role = CASE
            WHEN supplier_rank > 0 AND customer_rank > 0 THEN 'both'
            WHEN supplier_rank > 0                        THEN 'supplier'
            WHEN customer_rank > 0                        THEN 'buyer'
            WHEN is_company = TRUE                        THEN 'prospect'
            ELSE NULL
        END
        WHERE company_role IS NULL
    """)

    cr.execute("SELECT COUNT(*) FROM res_partner WHERE company_role IS NOT NULL")
    total = cr.fetchone()[0]
    _logger.info("[5.0.0 migration] company_role backfill complete: %d partners populated", total)
