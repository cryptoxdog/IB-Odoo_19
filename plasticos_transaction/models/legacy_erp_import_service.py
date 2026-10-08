"""Historical ERP import must not realize deals on the transaction object.

Commercial documents belong on ``sale.order``, ``purchase.order``, and
``account.move``. This hook stays registered so the partner importer has one
extension point, and it writes nothing.
"""

from __future__ import annotations

from odoo import models


class PlasticosLegacyErpImport(models.AbstractModel):
    """Does not write historical worksheets onto the transaction object."""

    _inherit = "plasticos.erp.import"

    def _extend_historical_import(self, index, report, partner_by_cp, limit, commit, dry_run) -> bool:
        """Refuse the retired one-transaction-per-worksheet import."""
        return False
