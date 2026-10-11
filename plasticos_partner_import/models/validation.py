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
        - Facilities / locations: company_type=company, parent_id set
        - Contacts: company_type=person, parent_id set, is_company=False

        ``facility_role`` is not part of the graph contract: the facility
        profile authority (plasticos_facility_profile.res_partner) supplies it
        through enrichment or manual entry, never derives it from partner type,
        so an imported location is valid without a facility specialization.
        """
        # Corporates (company, no parent) and locations (company with a
        # parent) are valid by definition, so only contacts are read. Of
        # those, a contact can fail only when it has no parent or carries
        # is_company=True; the res.users exemption stays in Python below.
        candidates = self.env["res.partner"].search(
            [
                ("company_type", "=", "person"),
                "|",
                ("parent_id", "=", False),
                ("is_company", "=", True),
            ]
        )

        errors = []
        for p in candidates:
            # Contact validation: person must have parent and not be company
            # Exception: partners linked to res.users (admin, cron, internal users) may
            # have no parent. Use user_ids (inverse of users.partner_id) — a bare
            # res.users search can miss rows under some registry/context combinations.
            if not p.parent_id and not p.user_ids:
                errors.append(f"Contact '{p.name}' (id={p.id}) missing parent_id")
            if p.is_company:
                errors.append(f"Contact '{p.name}' (id={p.id}) has is_company=True")

        if errors:
            _logger.error("Graph validation failed with %d errors", len(errors))
            for err in errors[:10]:  # Log first 10
                _logger.error("  - %s", err)
            raise ValidationError(f"BLOCKER: GRAPH_VALIDATION_FAILURE ({len(errors)} errors)")

        _logger.info("Partner graph validated: %d contact candidate(s) checked", len(candidates))
        return True

    def audit_import_integrity(self):
        """
        Report possible issues after a partial or incorrect import.
        Does not raise; returns a dict of findings for display or repair.

        ``facilities_missing_role`` is informational (locations awaiting
        enrichment), never an integrity error: facility_role is supplied by
        enrichment or manual entry and is not derived from partner type.

        Returns:
            dict with keys: old_external_ids, facilities_missing_role,
            contacts_missing_parent, duplicate_external_ids, summary
        """
        IrModelData = self.env["ir.model.data"]
        Partner = self.env["res.partner"]

        # 1. Partners with old external ID module (plasticos_import instead of plasticos_partner_import)
        old_data = IrModelData.search(
            [
                ("module", "=", "plasticos_import"),
                ("model", "=", "res.partner"),
                ("res_id", "!=", 0),
            ]
        )
        old_external_ids = [
            {"xmlid": f"{d.module}.{d.name}", "res_id": d.res_id, "partner": Partner.browse(d.res_id).name}
            for d in old_data
            if Partner.browse(d.res_id).exists()
        ]

        # 2. Facility companies (company + parent) missing facility_role
        # facility_role is a stored, indexed selection: unset is NULL, which
        # "= False" selects, so only the reported locations are read.
        facilities = Partner.search(
            [
                ("company_type", "=", "company"),
                ("parent_id", "!=", False),
                ("facility_role", "=", False),
            ]
        )
        facilities_missing_role = [{"id": p.id, "name": p.name, "parent": p.parent_id.name} for p in facilities]

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
                ("model", "=", "res.partner"),
            ]
        )
        new_names = {d.name for d in new_module_data}
        duplicate_external_ids = [item for item in old_external_ids if item["xmlid"].split(".")[-1] in new_names]

        summary_parts = []
        if old_external_ids:
            summary_parts.append(f"{len(old_external_ids)} partner(s) with old external ID (plasticos_import)")
        if facilities_missing_role:
            summary_parts.append(
                f"{len(facilities_missing_role)} location(s) without a facility_role (enrichment pending; not an error)"
            )
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

    def repair_import_data(self, dry_run=True):
        """
        Fix common post-import issues:
        - Migrate ir.model.data from module plasticos_import to plasticos_partner_import
          only when no duplicate (same name) exists in plasticos_partner_import.

        ``facility_role`` is never invented here: a location without one is
        awaiting enrichment or manual entry, not broken. ``facilities_fixed``
        stays in the result for callers and is always 0.

        Returns:
            dict with keys: facilities_fixed, external_ids_migrated, errors, summary
        """
        IrModelData = self.env["ir.model.data"]

        facilities_fixed = 0
        external_ids_migrated = 0
        errors = []

        if not dry_run:
            # Migrate external IDs: plasticos_import -> plasticos_partner_import where no duplicate
            new_names = set(
                IrModelData.search(
                    [
                        ("module", "=", "plasticos_partner_import"),
                        ("model", "=", "res.partner"),
                    ]
                ).mapped("name")
            )
            old_data = IrModelData.search(
                [
                    ("module", "=", "plasticos_import"),
                    ("model", "=", "res.partner"),
                ]
            )
            for d in old_data:
                if d.name in new_names:
                    continue
                try:
                    d.module = "plasticos_partner_import"
                    external_ids_migrated += 1
                except Exception as e:
                    errors.append(f"ir.model.data id={d.id} ({d.module}.{d.name}): {e}")

        summary = (
            "Dry run: no changes."
            if dry_run
            else (
                f"Migrated {external_ids_migrated} external ID(s); facility roles are left to enrichment."
                + (" " + "; ".join(errors[:5]) if errors else "")
            )
        )
        return {
            "facilities_fixed": facilities_fixed,
            "external_ids_migrated": external_ids_migrated,
            "errors": errors,
            "summary": summary,
        }
