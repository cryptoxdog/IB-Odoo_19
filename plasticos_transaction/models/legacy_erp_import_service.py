"""Historical ERP commercial documents on native Odoo records.

The partner importer calls ``_extend_historical_import`` after the partner
stages. This writes ``sale.order``, ``purchase.order``, and ``account.move``
from the source index. It does not create a transaction record: confirming
the sale order is what compiles one.
"""

from odoo import models


class PlasticosLegacyErpImport(models.AbstractModel):
    _inherit = "plasticos.erp.import"

    def _extend_historical_import(self, index, report, partner_by_cp, limit, commit, dry_run) -> bool:
        """Realize native commercial documents and own the commit."""
        from . import native_document_import  # noqa: PLC0415 - loaded with the extension, not at install of the base

        return native_document_import.realize(self, index, report, partner_by_cp, limit, commit, dry_run)
