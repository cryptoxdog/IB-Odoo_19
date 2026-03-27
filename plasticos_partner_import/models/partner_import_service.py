"""PlasticOS Partner Import Service — schema v5.0.0.

Changes from v4.x:
  - Full VS_COMPANY_TYPE_MAP: VanillaSoft company_type strings -> company_role codes
  - _resolve_company_role(): maps CSV role + company_type to company_role
  - _resolve_trade_role(): auto-sets trade_role from company_role + CSV role column
  - _resolve_origin_sector(): auto-sets origin_sector for known roles
  - _apply_vanillasoft_lead_source(): sets lead_source_id to VanillaSoft utm.source
  - _import_corporate_row(): writes company_role (not facility_role)
  - _import_facility_row(): writes company_role (not facility_role)
  - PROCESS TYPE NOTE: we do NOT auto-set plasticos_process_type_ids at import.
    process types are set via enrichment or manual entry only.
  - All field writes use company_role key; facility_role shim handles backward compat.
"""

import csv
import logging
import re

from odoo import models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

BATCH_SIZE = 100

CONTACT_TYPE_AR = "invoice"
CONTACT_TYPE_AP = "contact"
CONTACT_TYPE_DELIVERY = "delivery"

INVOICE_TYPES = {"Remit", "Inv/Remit", "Invoice", "Primary"}

# ---------------------------------------------------------------------------
# VS_COMPANY_TYPE_MAP
# ---------------------------------------------------------------------------
VS_COMPANY_TYPE_MAP = {
    "recycler": "recycler",
    "plastic recycler": "recycler",
    "plastics recycler": "recycler",
    "scrap recycler": "recycler",
    "recycling facility": "recycler",
    "recycling center": "recycler",
    "recycling company": "recycler",
    "commercial recycler": "commercial_recycler",
    "c&i recycler": "commercial_recycler",
    "industrial recycler": "commercial_recycler",
    "route recycler": "commercial_recycler",
    "processor": "processor",
    "plastics processor": "processor",
    "plastic processor": "processor",
    "regrinder": "processor",
    "pelletizer": "processor",
    "compounder": "compounder",
    "compounding": "compounder",
    "plastic compounder": "compounder",
    "manufacturer": "manufacturer",
    "plastics manufacturer": "manufacturer",
    "plastic manufacturer": "manufacturer",
    "molder": "manufacturer",
    "injection molder": "manufacturer",
    "blow molder": "manufacturer",
    "extruder": "manufacturer",
    "thermoformer": "manufacturer",
    "film producer": "manufacturer",
    "end user": "manufacturer",
    "mrf": "mrf",
    "materials recovery facility": "mrf",
    "material recovery facility": "mrf",
    "transfer station": "transfer_station",
    "waste transfer": "transfer_station",
    "broker": "broker",
    "plastics broker": "broker",
    "material broker": "broker",
    "exporter": "broker",
    "plastics exporter": "broker",
    "distributor": "distributor",
    "plastics distributor": "distributor",
    "distribution center": "distribution_center",
    "dc": "distribution_center",
    "warehouse": "distribution_center",
    "fulfillment center": "distribution_center",
    "fulfillment": "distribution_center",
    "grower": "grower_farm",
    "farm": "grower_farm",
    "farmer": "grower_farm",
    "nursery": "grower_farm",
    "greenhouse": "grower_farm",
    "flower grower": "grower_farm",
    "agricultural": "grower_farm",
    "carrier": "carrier",
    "trucking": "carrier",
    "transporter": "carrier",
    "logistics": "carrier",
    "freight": "carrier",
    "equipment supplier": "equipment_supplier",
    "equipment manufacturer": "equipment_supplier",
    "baler manufacturer": "equipment_supplier",
    "other": "other",
    "unknown": "other",
}

_SUPPLIER_ONLY_ROLES = frozenset(
    {
        "recycler",
        "commercial_recycler",
        "mrf",
        "transfer_station",
        "distribution_center",
        "grower_farm",
    }
)
_BUYER_ONLY_ROLES = frozenset({"manufacturer", "compounder"})
_ROLE_ORIGIN_SECTOR_DEFAULTS = {
    "grower_farm": "agriculture",
    "distribution_center": "distribution_logistics",
}


class PlasticosPartnerImportService(models.AbstractModel):
    _name = "plasticos.partner.import.service"
    _description = "Deterministic Partner Import Service"

    # =========================================================================
    # Core upsert
    # =========================================================================
    def _upsert(self, model_name, external_id, values):
        env = self.env
        if not env.context.get("skip_automations"):
            env = env(context=dict(env.context, skip_automations=True, import_mode=True))

        record = env.ref(external_id, raise_if_not_found=False)
        if record:
            record.write(values)
            _logger.debug("Updated %s via %s", model_name, external_id)
            return record

        model = env[model_name]
        rec = model.create(values)
        self.env["ir.model.data"].create(
            {
                "name": external_id.split(".")[-1],
                "module": external_id.split(".")[0],
                "model": model_name,
                "res_id": rec.id,
                "noupdate": True,
            }
        )
        _logger.debug("Created %s via %s (id=%d)", model_name, external_id, rec.id)
        return rec

    # =========================================================================
    # Schema v5.0.0 role resolution
    # =========================================================================
    def _resolve_company_role(self, vs_company_type_str, csv_role_str=None):
        if vs_company_type_str:
            normalized = vs_company_type_str.strip().lower()
            if normalized in VS_COMPANY_TYPE_MAP:
                return VS_COMPANY_TYPE_MAP[normalized]
            for key, role in VS_COMPANY_TYPE_MAP.items():
                if key in normalized or normalized in key:
                    return role
        if csv_role_str:
            role_lower = csv_role_str.lower()
            if "broker" in role_lower:
                return "broker"
            if "carrier" in role_lower or "trucker" in role_lower:
                return "carrier"
            if "processor" in role_lower:
                return "processor"
            if "manufacturer" in role_lower or "molder" in role_lower:
                return "manufacturer"
        return "other"

    def _resolve_trade_role(self, company_role, csv_role_str=None):
        if company_role in _SUPPLIER_ONLY_ROLES:
            return "supplier"
        if company_role in _BUYER_ONLY_ROLES:
            return "buyer"
        if company_role in ("broker", "distributor"):
            return "both"
        if company_role in ("carrier", "equipment_supplier"):
            return "other"
        if csv_role_str:
            role_lower = csv_role_str.lower()
            has_supplier = "supplier" in role_lower
            has_customer = "customer" in role_lower
            if has_supplier and has_customer:
                return "both"
            if has_supplier:
                return "supplier"
            if has_customer:
                return "buyer"
        return "other"

    def _resolve_origin_sector(self, company_role):
        return _ROLE_ORIGIN_SECTOR_DEFAULTS.get(company_role, False)

    def _apply_vanillasoft_lead_source(self, partner):
        if partner.lead_source_id:
            return
        vs_source = self.env.ref("plasticos_facility_profile.utm_source_vanillasoft", raise_if_not_found=False)
        if vs_source:
            partner.lead_source_id = vs_source.id

    # =========================================================================
    # Lookup helpers
    # =========================================================================
    def _lookup_user(self, name):
        if not name or name in ("FALSE", ""):
            return False
        user = self.env["res.users"].search([("name", "ilike", name.strip())], limit=1)
        return user.id if user else False

    def _lookup_state(self, state_code, country_id=None):
        if not state_code:
            return False
        domain = [("code", "=", state_code.strip().upper())]
        if country_id:
            domain.append(("country_id", "=", country_id))
        state = self.env["res.country.state"].search(domain, limit=1)
        return state.id if state else False

    def _lookup_country(self, country_name):
        if not country_name:
            return False
        country = self.env["res.country"].search(
            ["|", ("name", "ilike", country_name.strip()), ("code", "=", country_name.strip().upper()[:2])],
            limit=1,
        )
        return country.id if country else False

    def _lookup_category_tags(self, role_str):
        if not role_str:
            return []
        tag_ids = []
        role_lower = role_str.lower()
        operational_tag_mapping = {
            "exporter": "plasticos_base.tag_exporter",
            "toll": "plasticos_base.tag_toll_processor",
        }
        for key, xml_id in operational_tag_mapping.items():
            if key in role_lower:
                tag = self.env.ref(xml_id, raise_if_not_found=False)
                if tag:
                    tag_ids.append(tag.id)
        return tag_ids

    def _make_external_id(self, prefix, name):
        safe = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
        return f"plasticos_partner_import.{prefix}_{safe}"

    def _normalize_email(self, email_str, contact_name=None):
        if not email_str:
            return False
        emails = re.split(r"[;,\s]+", email_str.strip())
        valid_emails = [e.strip() for e in emails if "@" in e.strip() and "." in e.strip()]
        if not valid_emails:
            return False
        if len(valid_emails) == 1 or not contact_name:
            return valid_emails[0]
        name_parts = [p for p in re.split(r"[\s&,]+", contact_name.lower()) if len(p) > 2]
        for email in valid_emails:
            email_local = email.split("@")[0].lower()
            for part in name_parts:
                if part in email_local:
                    return email
        return valid_emails[0]

    def _normalize_phone(self, phone_str):
        return phone_str.strip() if phone_str else False

    def _get_default_payment_term(self):
        term = self.env.ref("plasticos_accounting.payment_term_net_30", raise_if_not_found=False)
        if term:
            return term.id
        term = self.env["account.payment.term"].search([("name", "=", "Net 30")], limit=1)
        return term.id if term else False

    # =========================================================================
    # Main import entry points
    # =========================================================================
    def run_full_import(self, corporate=None, facilities=None, contacts=None):
        _logger.info("Starting partner import pipeline")
        self.env["plasticos.partner.import.validation"].validate_reference_integrity()
        counts = {
            "corporates": self._load_corporates(corporate or []),
            "facilities": self._load_facilities(facilities or []),
            "contacts": self._load_contacts(contacts or []),
        }
        self.env["plasticos.partner.import.validation"].validate_partner_graph()
        _logger.info("Partner import complete: %s", counts)
        return counts

    def run_csv_import(self, corporate_csv_path, facility_csv_path):
        _logger.info("Starting CSV import: corporate=%s, facility=%s", corporate_csv_path, facility_csv_path)
        self.env["plasticos.partner.import.validation"].validate_reference_integrity()
        corporate_count = 0
        if corporate_csv_path:
            corporate_count = self._import_corporate_csv(corporate_csv_path)
        facility_count = 0
        contact_count = 0
        if facility_csv_path:
            facility_count, contact_count = self._import_facility_csv(facility_csv_path)
        self.env["plasticos.partner.import.validation"].validate_partner_graph()
        return {
            "corporates": corporate_count,
            "facilities": facility_count,
            "contacts": contact_count,
            "corporates_created": corporate_count,
            "corporates_updated": 0,
            "facilities_created": facility_count,
            "facilities_updated": 0,
            "contacts_created": contact_count,
            "errors": [],
        }

    # =========================================================================
    # CSV Import: Corporates
    # =========================================================================
    def _import_corporate_csv(self, csv_path):
        count = 0
        with open(csv_path, encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for i, row in enumerate(reader):
                try:
                    self._import_corporate_row(row, i)
                    count += 1
                    if count % BATCH_SIZE == 0:
                        self.env.cr.commit()
                        _logger.info("Corporates progress: %d", count)
                except Exception as e:
                    _logger.error("Error at corporate row %d: %s", i, e)
                    raise
        _logger.info("Loaded %d corporates from CSV", count)
        return count

    def _import_corporate_row(self, row, row_num):
        name = row.get("name", "").strip()
        if not name:
            _logger.warning("Skipping corporate row %d: empty name", row_num)
            return None

        ref = row.get("ref", "").strip()
        external_id = self._make_external_id("corp", ref or name)

        country_id = self._lookup_country(row.get("country", ""))
        state_id = self._lookup_state(row.get("state_id", ""), country_id)
        user_id = self._lookup_user(row.get("user_id", ""))
        csv_role_str = row.get("role", "")
        vs_company_type_str = row.get("company_type", "")

        company_role = self._resolve_company_role(vs_company_type_str, csv_role_str)
        trade_role = self._resolve_trade_role(company_role, csv_role_str)
        origin_sector = self._resolve_origin_sector(company_role)
        is_supplier = trade_role in ("supplier", "both")
        is_customer = trade_role in ("buyer", "both")
        category_tag_ids = self._lookup_category_tags(csv_role_str)
        default_payment_term_id = self._get_default_payment_term()

        vals = {
            "name": name,
            "company_type": "company",
            "is_company": True,
            "parent_id": False,
            "ref": ref,
            "street": row.get("street", "").strip() or False,
            "street2": row.get("street2", "").strip() or False,
            "city": row.get("city", "").strip() or False,
            "state_id": state_id,
            "zip": row.get("zip", "").strip() or False,
            "country_id": country_id,
            "user_id": user_id,
            "supplier_rank": 1 if is_supplier else 0,
            "customer_rank": 1 if is_customer else 0,
            "company_role": company_role,
            "plasticos_trade_role": trade_role,
        }
        if origin_sector:
            vals["plasticos_origin_sector"] = origin_sector
        if category_tag_ids:
            vals["category_id"] = [(6, 0, category_tag_ids)]
        if is_customer and default_payment_term_id:
            vals["property_payment_term_id"] = default_payment_term_id
        if is_supplier and default_payment_term_id:
            vals["property_supplier_payment_term_id"] = default_payment_term_id

        partner = self._upsert("res.partner", external_id, vals)
        self._apply_vanillasoft_lead_source(partner)
        return partner

    # =========================================================================
    # CSV Import: Facilities
    # =========================================================================
    def _import_facility_csv(self, csv_path):
        facility_count = 0
        contact_count = 0
        contacts_created = {}
        with open(csv_path, encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for i, row in enumerate(reader):
                try:
                    fac, cont = self._import_facility_row(row, i, contacts_created)
                    if fac:
                        facility_count += 1
                    if cont:
                        contact_count += 1
                    if (facility_count + contact_count) % BATCH_SIZE == 0:
                        self.env.cr.commit()
                except Exception as e:
                    _logger.error("Error at facility row %d: %s", i, e)
                    raise
        _logger.info("Loaded %d facilities, %d contacts from CSV", facility_count, contact_count)
        return facility_count, contact_count

    def _import_facility_row(self, row, row_num, contacts_created):
        partner_name = row.get("partner_id", "").strip()
        if not partner_name:
            return None, None

        facility_type = row.get("Type", "").strip()
        alias = row.get("Alias", "").strip()
        parent = self._find_corporate_by_name(partner_name)
        if not parent:
            _logger.warning("Skipping facility row %d: parent '%s' not found", row_num, partner_name)
            return None, None

        facility_name = alias if alias and alias != "INVOICE" else f"{partner_name} - {facility_type}"
        country_id = self._lookup_country(row.get("country", ""))
        state_id = self._lookup_state(row.get("state", ""), country_id)

        parent_company_role = parent.company_role or False
        parent_trade_role = parent.plasticos_trade_role or False
        parent_origin_sector = parent.plasticos_origin_sector or False
        partner_type_odoo = "invoice" if facility_type in INVOICE_TYPES else "contact"
        external_id = self._make_external_id("fac", f"{partner_name}_{alias or facility_type}_{row_num}")
        parent_tag_ids = parent.category_id.ids if parent.category_id else []

        if facility_type == "Location":
            vals = {
                "name": facility_name,
                "company_type": "company",
                "is_company": True,
                "type": "contact",
                "parent_id": parent.id,
                "street": row.get("address", "").strip() or False,
                "street2": row.get("adderess2", "").strip() or False,
                "city": row.get("city", "").strip() or False,
                "state_id": state_id,
                "zip": row.get("zip", "").strip() or False,
                "country_id": country_id,
                "company_role": parent_company_role,
                "plasticos_trade_role": parent_trade_role,
            }
            if parent_origin_sector:
                vals["plasticos_origin_sector"] = parent_origin_sector
        else:
            vals = {
                "name": facility_name,
                "company_type": "person",
                "is_company": False,
                "type": partner_type_odoo,
                "parent_id": parent.id,
                "street": row.get("address", "").strip() or False,
                "street2": row.get("adderess2", "").strip() or False,
                "city": row.get("city", "").strip() or False,
                "state_id": state_id,
                "zip": row.get("zip", "").strip() or False,
                "country_id": country_id,
            }

        if parent_tag_ids:
            vals["category_id"] = [(6, 0, parent_tag_ids)]

        facility = self._upsert("res.partner", external_id, vals)
        self._apply_vanillasoft_lead_source(facility)

        contact = None
        contact_name = row.get("Contact", "").strip()
        contact_phone = self._normalize_phone(row.get("Phone", ""))
        contact_email = self._normalize_email(row.get("Email", ""), contact_name)
        if contact_name and contact_name not in ("Primary", "United States"):
            contact = self._create_facility_contact(
                facility, parent, contact_name, contact_phone, contact_email, facility_type, contacts_created
            )
        return facility, contact

    def _find_corporate_by_name(self, name):
        partner = self.env["res.partner"].search(
            [("name", "=", name), ("parent_id", "=", False), ("is_company", "=", True)],
            limit=1,
        )
        if partner:
            return partner
        return self.env["res.partner"].search(
            [("name", "ilike", name), ("parent_id", "=", False), ("is_company", "=", True)],
            limit=1,
        )

    def _create_facility_contact(self, facility, corporate, name, phone, email, facility_type, contacts_created):
        dedup_key = (corporate.id, name.lower(), (email or "").lower())
        if dedup_key in contacts_created:
            return None

        trade_role = corporate.plasticos_trade_role or ""
        is_supplier = trade_role in ("supplier", "both") or corporate.supplier_rank > 0
        is_customer = trade_role in ("buyer", "both") or corporate.customer_rank > 0

        if is_supplier:
            contact_type = CONTACT_TYPE_AR
        elif is_customer:
            contact_type = CONTACT_TYPE_AP
        else:
            contact_type = "contact"
        if facility_type == "Location":
            contact_type = CONTACT_TYPE_DELIVERY

        external_id = self._make_external_id("contact", f"{corporate.name}_{name}_{facility.id}")
        vals = {
            "name": name,
            "company_type": "person",
            "is_company": False,
            "type": contact_type,
            "parent_id": facility.id,
            "phone": phone,
            "email": email,
        }
        contact = self._upsert("res.partner", external_id, vals)
        contacts_created[dedup_key] = contact.id
        return contact

    # =========================================================================
    # Legacy dict-based methods (backward compat)
    # =========================================================================
    def _load_corporates(self, rows):
        count = 0
        default_payment_term_id = self._get_default_payment_term()
        for i, r in enumerate(rows):
            if not r.get("external_id"):
                raise ValidationError(f"BLOCKER: MISSING_EXTERNAL_ID at row {i}")
            company_role = r.get("company_role") or r.get("facility_role") or "other"
            trade_role = self._resolve_trade_role(company_role, r.get("role", ""))
            vals = {
                "name": r["name"],
                "company_type": "company",
                "is_company": True,
                "parent_id": False,
                "country_id": r.get("country_id"),
                "state_id": r.get("state_id"),
                "user_id": r.get("user_id"),
                "company_role": company_role,
                "plasticos_trade_role": trade_role,
            }
            if r.get("property_payment_term_id"):
                vals["property_payment_term_id"] = r["property_payment_term_id"]
            elif r.get("is_customer") and default_payment_term_id:
                vals["property_payment_term_id"] = default_payment_term_id
            if r.get("property_supplier_payment_term_id"):
                vals["property_supplier_payment_term_id"] = r["property_supplier_payment_term_id"]
            elif r.get("is_supplier") and default_payment_term_id:
                vals["property_supplier_payment_term_id"] = default_payment_term_id
            self._upsert("res.partner", r["external_id"], vals)
            count += 1
            if count % BATCH_SIZE == 0:
                self.env.cr.commit()
        _logger.info("Loaded %d corporates", count)
        return count

    def _load_facilities(self, rows):
        count = 0
        for i, r in enumerate(rows):
            if not r.get("external_id"):
                raise ValidationError(f"BLOCKER: MISSING_EXTERNAL_ID at facility row {i}")
            parent = self.env.ref(r["parent_external_id"], raise_if_not_found=False)
            if not parent:
                raise ValidationError(
                    f"BLOCKER: FACILITY_PARENT_MISSING - {r['parent_external_id']} "
                    f"not found for facility '{r.get('name')}'"
                )
            company_role = r.get("company_role") or r.get("facility_role") or parent.company_role or "other"
            vals = {
                "name": r["name"],
                "company_type": "company",
                "is_company": True,
                "parent_id": parent.id,
                "company_role": company_role,
            }
            self._upsert("res.partner", r["external_id"], vals)
            count += 1
            if count % BATCH_SIZE == 0:
                self.env.cr.commit()
        _logger.info("Loaded %d facilities", count)
        return count

    def _load_contacts(self, rows):
        count = 0
        for i, r in enumerate(rows):
            if not r.get("external_id"):
                raise ValidationError(f"BLOCKER: MISSING_EXTERNAL_ID at contact row {i}")
            parent = self.env.ref(r["parent_external_id"], raise_if_not_found=False)
            if not parent:
                raise ValidationError(
                    f"BLOCKER: CONTACT_PARENT_MISSING - {r['parent_external_id']} "
                    f"not found for contact '{r.get('name')}'"
                )
            vals = {
                "name": r["name"],
                "company_type": "person",
                "is_company": False,
                "parent_id": parent.id,
                "phone": r.get("phone"),
                "email": r.get("email"),
                "function": r.get("function"),
                "type": r.get("type", "contact"),
            }
            self._upsert("res.partner", r["external_id"], vals)
            count += 1
            if count % BATCH_SIZE == 0:
                self.env.cr.commit()
        _logger.info("Loaded %d contacts", count)
        return count
