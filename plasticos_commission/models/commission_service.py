import logging

from odoo import models

_logger = logging.getLogger(__name__)


class PlasticosCommissionService(models.AbstractModel):
    """Commission calculation service.

    Priority order:
      1. commission_locked       → return locked amount, no recalc
      2. commission_override_pct → gross_margin * override fraction
      3. commission_rule_id      → rule engine (tiered / fixed / percentage)
      4. ICP default rate        → plasticos.commission.default_rate
      5. 0.0                     → no commission configured
    """

    _name = "plasticos.commission.service"
    _description = "Commission Calculation Service"

    def compute_commission(self, record):
        """Compute commission amount for a plasticos.transaction record.

        Args:
            record: plasticos.transaction record

        Returns:
            float: Commission amount, always >= 0, rounded to 2dp
        """
        if not record:
            return 0.0

        # 1. Locked — never recalculate
        if getattr(record, "commission_locked", False):
            return record.commission_locked_amount or 0.0

        gross_margin = getattr(record, "gross_margin", 0.0) or 0.0
        if gross_margin <= 0:
            return 0.0

        # 2. Admin override (fraction 0.0–1.0 stored on transaction)
        override = getattr(record, "commission_override_pct", 0.0) or 0.0
        if override > 0:
            amount = gross_margin * override
            _logger.debug(
                "Commission override on %s: %.4f × %.2f = %.2f",
                record.name,
                override,
                gross_margin,
                amount,
            )
            return round(amount, 2)

        # 3. Rule engine
        rule = getattr(record, "commission_rule_id", False)
        if rule:
            transaction_date = getattr(record, "create_date", None)
            if transaction_date:
                transaction_date = transaction_date.date()
            product = getattr(record, "product_id", False)
            partner = getattr(record, "supplier_id", False)
            revenue = getattr(record, "revenue_total", 0.0) or 0.0

            if rule.is_applicable(
                transaction_date=transaction_date,
                transaction_amount=revenue,
                product=product,
                partner=partner,
            ):
                amount = rule.calculate_commission(
                    gross_margin=gross_margin,
                    transaction_amount=revenue,
                )
                _logger.debug(
                    "Commission rule '%s' on %s: %.2f",
                    rule.name,
                    record.name,
                    amount,
                )
                return round(max(amount, 0.0), 2)
            else:
                _logger.debug(
                    "Commission rule '%s' not applicable for %s — falling through",
                    rule.name,
                    record.name,
                )

        # 4. ICP default rate fallback
        try:
            icp = record.env["ir.config_parameter"].sudo()
            default_rate = float(icp.get_param("plasticos.commission.default_rate", "0.0"))
            if default_rate > 0:
                amount = gross_margin * default_rate
                _logger.debug(
                    "Commission ICP default rate %.4f on %s: %.2f",
                    default_rate,
                    record.name,
                    amount,
                )
                return round(amount, 2)
        except Exception:
            _logger.warning("Failed to read ICP commission default rate", exc_info=True)

        # 5. No config → 0
        return 0.0
