import logging
from odoo import models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class PlasticosPartnerImportValidation(models.AbstractModel):
    _name = "plasticos.partner.import.validation"
    _description = "Partner Import Validation"

    def validate_reference_integrity(self):
        """Ensure foundation models exist before import."""
        required = [
            "res.country",
            "res.country.state",
            "res.users",
            "account.payment.term",
            "res.partner.category",
            "ir.sequence",
            "account.account",
        ]

        for model in required:
            if model not in self.env:
                _logger.error("Reference integrity check failed: %s not in registry", model)
                raise ValidationError(f"BLOCKER: FOUNDATION_INCOMPLETE ({model})")

        _logger.info("Reference integrity validated: %d models confirmed", len(required))
        return True

    def validate_partner_graph(self):
        """
        Validate Plasticos partner hierarchy:
        - Corporates: company_type=company, parent_id=False
        - Facilities: company_type=company, parent_id set, x_facility_role set
        - Contacts: company_type=person, parent_id set, is_company=False
        """
        partners = self.env["res.partner"].search([
            "|",
            ("company_type", "=", "company"),
            ("company_type", "=", "person"),
        ])

        errors = []
        for p in partners:
            # Corporate validation: no parent
            if p.company_type == "company" and not p.parent_id:
                # This is a corporate - valid
                continue

            # Facility validation: company with parent must have facility role
            if p.company_type == "company" and p.parent_id:
                if not p.x_facility_role:
                    errors.append(f"Facility '{p.name}' (id={p.id}) missing x_facility_role")
                continue

            # Contact validation: person must have parent and not be company
            if p.company_type == "person":
                if not p.parent_id:
                    errors.append(f"Contact '{p.name}' (id={p.id}) missing parent_id")
                if p.is_company:
                    errors.append(f"Contact '{p.name}' (id={p.id}) has is_company=True")
                continue

        if errors:
            _logger.error("Graph validation failed with %d errors", len(errors))
            for err in errors[:10]:  # Log first 10
                _logger.error("  - %s", err)
            raise ValidationError(f"BLOCKER: GRAPH_VALIDATION_FAILURE ({len(errors)} errors)")

        _logger.info("Partner graph validated: %d partners checked", len(partners))
        return True
