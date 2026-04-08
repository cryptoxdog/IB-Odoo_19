import csv
import logging

from odoo import models
from odoo.addons.plasticos_facility_profile.models.lead_source import LEAD_SOURCE_MAPPING
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

BATCH_SIZE = 100

# VanillaSoft Lead Status → crm.stage XML ID mapping
STAGE_MAPPING = {
    "2a=Qualified/HOT": "plasticos_crm_bridge.stage_qualified_hot",
    "2b=Qualified/WARM": "plasticos_crm_bridge.stage_qualified_warm",
    "2c=Qualified/COLD": "plasticos_crm_bridge.stage_qualified_warm",  # Map COLD to WARM stage
    "2=Qualified/Open": "plasticos_crm_bridge.stage_qualified_warm",  # Map Open to WARM stage
    "3=Qualified/Resist": "plasticos_crm_bridge.stage_resistant",
    "1= Currently Working With": "plasticos_crm_bridge.stage_active_supplier",
    "4=Unqualified": "plasticos_crm_bridge.stage_dead_lead",
    "7=Do Not Call": "plasticos_crm_bridge.stage_dead_lead",
    "8=Duplicate": "plasticos_crm_bridge.stage_dead_lead",
    "6=Wrong #": "plasticos_crm_bridge.stage_dead_lead",
    "New": "plasticos_crm_bridge.stage_new",
}

# VanillaSoft Company Type → res.partner.category XML ID mapping
COMPANY_TYPE_MAPPING = {
    "Distribution Center": "plasticos_crm_bridge.categ_distribution_center",
    "Commercial Recycler": "plasticos_crm_bridge.categ_commercial_recycler",
    "Pallet Recycler": "plasticos_crm_bridge.categ_pallet_recycler",
    "Compounder": "plasticos_crm_bridge.categ_compounder",
    "Grinder/Processor": "plasticos_crm_bridge.categ_grinder_processor",
    "E-Waste": "plasticos_crm_bridge.categ_ewaste",
    "MRF": "plasticos_crm_bridge.categ_mrf",
    "Manufacturer": "plasticos_crm_bridge.categ_manufacturer",
    "Broker": "plasticos_crm_bridge.categ_broker",
    "Carrier": "plasticos_crm_bridge.categ_carrier",
}

ROLE_TAG_MAPPING = {
    "Buyer": "plasticos_crm_bridge.categ_buyer",
    "Supplier": "plasticos_crm_bridge.categ_supplier",
}


class PlasticosCRMLeadImportService(models.AbstractModel):
    """Import VanillaSoft CRM contacts as crm.lead records.

    This service handles the 3rd VanillaSoft CSV file (CRM leads)
    as distinct from the corporate/facility partner imports.

    CRM leads are created as type='lead' and staged per VanillaSoft
    Lead Status. They are NOT converted to res.partner automatically —
    that happens via the "Convert to Intake" action on the CRM form.
    """

    _name = "plasticos.crm.lead.import.service"
    _description = "VanillaSoft CRM Lead Import Service"

    def _resolve_stage(self, lead_status):
        """Map VanillaSoft Lead Status to crm.stage record."""
        xml_id = STAGE_MAPPING.get(lead_status)
        if xml_id:
            stage = self.env.ref(xml_id, raise_if_not_found=False)
            if stage:
                return stage.id
        # Default to "New" stage
        new_stage = self.env.ref(
            "plasticos_crm_bridge.stage_new",
            raise_if_not_found=False,
        )
        return new_stage.id if new_stage else False

    def _resolve_utm_source(self, raw_source):
        """Map VanillaSoft Lead Source to utm.source record."""
        if not raw_source:
            return False
        utm_name = LEAD_SOURCE_MAPPING.get(raw_source.strip(), "Other")
        source = self.env["utm.source"].search([("name", "=", utm_name)], limit=1)
        return source.id if source else False

    def _resolve_category_tags(self, company_type, role):
        """Build category_id tag list from Company Type and Buyer/Supplier role."""
        tag_ids = []

        # Company Type tag
        xml_id = COMPANY_TYPE_MAPPING.get(company_type)
        if xml_id:
            tag = self.env.ref(xml_id, raise_if_not_found=False)
            if tag:
                tag_ids.append(tag.id)

        # Role tag (Buyer/Supplier)
        if role:
            for role_part in role.split("/"):
                role_xml_id = ROLE_TAG_MAPPING.get(role_part.strip())
                if role_xml_id:
                    tag = self.env.ref(role_xml_id, raise_if_not_found=False)
                    if tag:
                        tag_ids.append(tag.id)

        return tag_ids

    def _lookup_state(self, state_code, country_id=None):
        """Lookup res.country.state by code."""
        if not state_code:
            return False
        domain = [("code", "=", state_code.strip().upper())]
        if country_id:
            domain.append(("country_id", "=", country_id))
        state = self.env["res.country.state"].search(domain, limit=1)
        return state.id if state else False

    def _lookup_country(self, country_name):
        """Lookup res.country by name or code."""
        if not country_name:
            return False
        country = self.env["res.country"].search(
            [
                "|",
                ("name", "ilike", country_name.strip()),
                ("code", "=", country_name.strip().upper()[:2]),
            ],
            limit=1,
        )
        return country.id if country else False

    def _lookup_user(self, name):
        """Lookup res.users by name. Returns ID or False."""
        if not name or name.strip() in ("FALSE", ""):
            return False
        user = self.env["res.users"].search([("name", "ilike", name.strip())], limit=1)
        return user.id if user else False

    # ─── Main Import Entry Point ──────────────────────────────

    def run_crm_lead_import(self, csv_path):
        """Import VanillaSoft CRM contacts from CSV as crm.lead records.

        Args:
            csv_path: Path to the VanillaSoft CRM CSV file

        Returns:
            dict with counts: leads_created, leads_skipped, errors
        """
        _logger.info("Starting VanillaSoft CRM lead import from: %s", csv_path)

        leads_created = 0
        leads_skipped = 0
        errors = []

        with open(csv_path, encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for i, row in enumerate(reader):
                try:
                    result = self._import_crm_lead_row(row, i)
                    if result:
                        leads_created += 1
                    else:
                        leads_skipped += 1

                    if (leads_created + leads_skipped) % BATCH_SIZE == 0:
                        self.env.cr.commit()
                        _logger.info(
                            "CRM lead progress: %d created, %d skipped",
                            leads_created,
                            leads_skipped,
                        )

                except Exception as e:
                    _logger.error("Error at CRM lead row %d: %s", i, e)
                    errors.append({"row": i, "error": str(e)})
                    if len(errors) > 50:
                        raise ValidationError(f"Too many errors ({len(errors)}). Aborting import.") from e

        _logger.info(
            "CRM lead import complete: %d created, %d skipped, %d errors",
            leads_created,
            leads_skipped,
            len(errors),
        )

        return {
            "leads_created": leads_created,
            "leads_skipped": leads_skipped,
            "errors": errors,
        }

    def _import_crm_lead_row(self, row, row_num):
        """Import a single CRM lead row.

        Expected columns:
            ContactID, Company, First Name, Last Name, Email, Direct,
            Mobile 1, Address, Address 2, City, State, Zip, Country,
            Lead Status, Lead Source, Company Type, Contact Owner,
            Buyer/Supplier, Notes
        """
        company = (row.get("Company") or "").strip()
        first = (row.get("First Name") or "").strip()
        last = (row.get("Last Name") or "").strip()
        contact_id = (row.get("ContactID") or "").strip()

        if not company and not first and not last:
            _logger.debug("Skipping empty row %d", row_num)
            return None

        # Check for duplicate by ContactID (external ref)
        if contact_id:
            existing = self.env["crm.lead"].search([("vanillasoft_id", "=", contact_id)], limit=1)
            if existing:
                _logger.debug(
                    "Skipping duplicate ContactID %s (lead %d)",
                    contact_id,
                    existing.id,
                )
                return None

        # Resolve lookups
        country_id = self._lookup_country(row.get("Country", ""))
        state_id = self._lookup_state(row.get("State", ""), country_id)
        stage_id = self._resolve_stage(row.get("Lead Status", ""))
        source_id = self._resolve_utm_source(row.get("Lead Source", ""))
        user_id = self._lookup_user(row.get("Contact Owner", ""))
        tag_ids = self._resolve_category_tags(
            row.get("Company Type", ""),
            row.get("Buyer/Supplier", ""),
        )

        contact_name = " ".join(filter(None, [first, last]))

        vals = {
            "name": f"{company} — {contact_name}" if company else contact_name or "Unknown",
            "type": "lead",
            "partner_name": company or False,
            "contact_name": contact_name or False,
            "email_from": (row.get("Email") or "").strip() or False,
            "phone": (row.get("Direct") or "").strip() or False,
            "mobile": (row.get("Mobile 1") or "").strip() or False,
            "street": (row.get("Address 1") or row.get("Address") or "").strip() or False,
            "street2": (row.get("Address 2") or "").strip() or False,
            "city": (row.get("City") or "").strip() or False,
            "state_id": state_id,
            "zip": (row.get("Zip Code") or row.get("Zip") or "").strip() or False,
            "country_id": country_id,
            "stage_id": stage_id,
            "source_id": source_id,
            "user_id": user_id,
            "description": (row.get("Notes") or "").strip() or False,
            "vanillasoft_id": contact_id or False,
        }

        # Partner category tags are stored in description for now.
        # crm.lead.tag_ids points to crm.tag (not res.partner.category),
        # so we cannot write partner category IDs there.
        # Tags will be applied to the partner when the lead is converted.

        lead = self.env["crm.lead"].create(vals)
        return lead
