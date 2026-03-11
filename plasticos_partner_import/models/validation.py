import logging

from odoo import models
from odoo.exceptions import ValidationError

RES_PARTNER = "res.partner"
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

    @staticmethod
    def _collect_partner_graph_errors(partners):
        """Collect hierarchy violation messages for all partners in the set."""
        errors = []
        for p in partners:
            if p.company_type == "company" and not p.parent_id:
                continue  # Corporate — valid
            if p.company_type == "company" and p.parent_id:
                if not p.facility_role:
                    errors.append(f"Facility '{p.name}' (id={p.id}) missing facility_role")
                continue
            if p.company_type == "person":
                if not p.parent_id:
                    errors.append(f"Contact '{p.name}' (id={p.id}) missing parent_id")
                if p.is_company:
                    errors.append(f"Contact '{p.name}' (id={p.id}) has is_company=True")
        return errors

    def validate_partner_graph(self):
        """
        Validate Plasticos partner hierarchy:
        - Corporates: company_type=company, parent_id=False
        - Facilities: company_type=company, parent_id set, facility_role set
        - Contacts: company_type=person, parent_id set, is_company=False
        """
        partners = self.env[RES_PARTNER].search(
            ["|", ("company_type", "=", "company"), ("company_type", "=", "person")]
        )

        errors = self._collect_partner_graph_errors(partners)

        if errors:
            _logger.error("Graph validation failed with %d errors", len(errors))
            for err in errors[:10]:  # Log first 10
                _logger.error("  - %s", err)
            raise ValidationError(f"BLOCKER: GRAPH_VALIDATION_FAILURE ({len(errors)} errors)")

        _logger.info("Partner graph validated: %d partners checked", len(partners))
        return True

    def audit_import_integrity(self):
        """
        Report possible issues after a partial or incorrect import.
        Does not raise; returns a dict of findings for display or repair.

        Returns:
            dict with keys: old_external_ids, facilities_missing_role,
            contacts_missing_parent, duplicate_external_ids, summary
        """
        IrModelData = self.env["ir.model.data"]
        Partner = self.env[RES_PARTNER]

        # 1. Partners with old external ID module (plasticos_import instead of plasticos_partner_import)
        old_data = IrModelData.search(
            [
                ("module", "=", "plasticos_import"),
                ("model", "=", RES_PARTNER),
                ("res_id", "!=", 0),
            ]
        )
        old_external_ids = [
            {"xmlid": f"{d.module}.{d.name}", "res_id": d.res_id, "partner": Partner.browse(d.res_id).name}
            for d in old_data
            if Partner.browse(d.res_id).exists()
        ]

        # 2. Facility companies (company + parent) missing facility_role
        facilities = Partner.search(
            [
                ("company_type", "=", "company"),
                ("parent_id", "!=", False),
            ]
        )
        facilities_missing_role = [
            {"id": p.id, "name": p.name, "parent": p.parent_id.name} for p in facilities if not p.facility_role
        ]

        # 3. Contacts (person) with no parent
        contacts_no_parent = Partner.search(
            [
                ("company_type", "=", "person"),
                ("parent_id", "=", False),
            ]
        )
        contacts_missing_parent = [{"id": p.id, "name": p.name} for p in contacts_no_parent]

        # 4. Duplicate external ID names (same name under old and new module)
        new_module_data = IrModelData.search(
            [
                ("module", "=", "plasticos_partner_import"),
                ("model", "=", RES_PARTNER),
            ]
        )
        new_names = {d.name for d in new_module_data}
        duplicate_external_ids = [item for item in old_external_ids if item["xmlid"].split(".")[-1] in new_names]

        summary_parts = []
        if old_external_ids:
            summary_parts.append(f"{len(old_external_ids)} partner(s) with old external ID (plasticos_import)")
        if facilities_missing_role:
            summary_parts.append(f"{len(facilities_missing_role)} facility(ies) missing facility_role")
        if contacts_missing_parent:
            summary_parts.append(f"{len(contacts_missing_parent)} contact(s) with no parent")
        if duplicate_external_ids:
            summary_parts.append(
                f"{len(duplicate_external_ids)} duplicate(s): same name exists under plasticos_partner_import"
            )
        summary = "; ".join(summary_parts) if summary_parts else "No issues found."

        return {
            "old_external_ids": old_external_ids,
            "facilities_missing_role": facilities_missing_role,
            "contacts_missing_parent": contacts_missing_parent,
            "duplicate_external_ids": duplicate_external_ids,
            "summary": summary,
        }

    def _fix_facility_roles(self, Partner):
        """Set facility_role='other' on facility companies that lack it; return (count, errors)."""
        fixed = 0
        errors = []
        facilities = Partner.search(
            [("company_type", "=", "company"), ("parent_id", "!=", False), ("facility_role", "=", False)]
        )
        for p in facilities:
            try:
                p.facility_role = "other"
                fixed += 1
            except Exception as e:
                errors.append(f"Facility id={p.id} ({p.name}): {e}")
        return fixed, errors

    def _migrate_external_ids(self, IrModelData):
        """Migrate ir.model.data module from plasticos_import to plasticos_partner_import; return (count, errors)."""
        migrated = 0
        errors = []
        new_names = set(
            IrModelData.search(
                [("module", "=", "plasticos_partner_import"), ("model", "=", RES_PARTNER)]
            ).mapped("name")
        )
        old_data = IrModelData.search(
            [("module", "=", "plasticos_import"), ("model", "=", RES_PARTNER)]
        )
        for d in old_data:
            if d.name in new_names:
                continue
            try:
                d.module = "plasticos_partner_import"
                migrated += 1
            except Exception as e:
                errors.append(f"ir.model.data id={d.id} ({d.module}.{d.name}): {e}")
        return migrated, errors

    def repair_import_data(self, dry_run=True):
        """
        Fix common post-import issues:
        - Set facility_role = 'other' for facility companies that lack it.
        - Migrate ir.model.data from module plasticos_import to plasticos_partner_import
          only when no duplicate (same name) exists in plasticos_partner_import.

        Returns:
            dict with keys: facilities_fixed, external_ids_migrated, errors, summary
        """
        Partner = self.env[RES_PARTNER]
        IrModelData = self.env["ir.model.data"]

        facilities_fixed = 0
        external_ids_migrated = 0
        errors = []

        if not dry_run:
            facilities_fixed, fac_errors = self._fix_facility_roles(Partner)
            errors.extend(fac_errors)

            migrated, mig_errors = self._migrate_external_ids(IrModelData)
            external_ids_migrated += migrated
            errors.extend(mig_errors)

        summary = (
            "Dry run: no changes."
            if dry_run
            else (
                f"Fixed {facilities_fixed} facility role(s); migrated {external_ids_migrated} external ID(s)."
                + (" " + "; ".join(errors[:5]) if errors else "")
            )
        )
        return {
            "facilities_fixed": facilities_fixed,
            "external_ids_migrated": external_ids_migrated,
            "errors": errors,
            "summary": summary,
        }
