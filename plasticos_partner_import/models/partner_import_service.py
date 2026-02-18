import logging
import csv
import re
from odoo import models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

BATCH_SIZE = 100  # Commit every N records

# Contact types in Odoo
CONTACT_TYPE_AR = "invoice"    # AR contact - we pay them
CONTACT_TYPE_AP = "contact"    # AP contact - they pay us  
CONTACT_TYPE_DELIVERY = "delivery"  # Shipping contact

# Facility types that are invoice/remit addresses
INVOICE_TYPES = {"Remit", "Inv/Remit", "Invoice", "Primary"}


class PlasticosPartnerImportService(models.AbstractModel):
    _name = "plasticos.partner.import.service"
    _description = "Deterministic Partner Import Service"

    # -------------------------------------------------------------------------
    # Core upsert
    # -------------------------------------------------------------------------
    def _upsert(self, model_name, external_id, values):
        """Idempotent upsert with external ID tracking."""
        record = self.env.ref(external_id, raise_if_not_found=False)

        if record:
            record.write(values)
            _logger.debug("Updated %s via %s", model_name, external_id)
            return record

        model = self.env[model_name]
        rec = model.create(values)

        self.env["ir.model.data"].create({
            "name": external_id.split(".")[-1],
            "module": external_id.split(".")[0],
            "model": model_name,
            "res_id": rec.id,
        })

        _logger.debug("Created %s via %s (id=%d)", model_name, external_id, rec.id)
        return rec

    # -------------------------------------------------------------------------
    # Lookup helpers
    # -------------------------------------------------------------------------
    def _lookup_user(self, name):
        """Lookup res.users by name. Returns ID or False."""
        if not name or name in ("FALSE", ""):
            return False
        user = self.env["res.users"].search([("name", "ilike", name.strip())], limit=1)
        if user:
            return user.id
        _logger.warning("User not found: %s", name)
        return False

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
        """Lookup res.country by name."""
        if not country_name:
            return False
        country = self.env["res.country"].search([
            "|",
            ("name", "ilike", country_name.strip()),
            ("code", "=", country_name.strip().upper()[:2])
        ], limit=1)
        return country.id if country else False

    def _parse_role(self, role_str):
        """Parse role string into supplier/customer flags."""
        if not role_str:
            return False, False
        role_lower = role_str.lower()
        is_supplier = "supplier" in role_lower
        is_customer = "customer" in role_lower
        return is_supplier, is_customer

    def _make_external_id(self, prefix, name):
        """Generate external ID from name."""
        # Sanitize: lowercase, replace non-alphanum with underscore
        safe = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
        return f"plasticos_import.{prefix}_{safe}"

    def _normalize_email(self, email_str):
        """Extract first valid email from potentially messy string."""
        if not email_str:
            return False
        # Split on common separators
        emails = re.split(r"[;,\s]+", email_str.strip())
        for e in emails:
            e = e.strip()
            if "@" in e and "." in e:
                return e
        return False

    def _normalize_phone(self, phone_str):
        """Clean phone number."""
        if not phone_str:
            return False
        return phone_str.strip()

    # -------------------------------------------------------------------------
    # Main import entry points
    # -------------------------------------------------------------------------
    def run_full_import(self, corporate=None, facilities=None, contacts=None):
        """
        Execute full partner import pipeline.

        Args:
            corporate: List of corporate dicts (from CSV 1)
            facilities: List of facility dicts (from CSV 2)
            contacts: List of contact dicts (optional, for manual contact list)

        Returns:
            dict with counts
        """
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
        """
        Import from CSV files directly.

        Args:
            corporate_csv_path: Path to corporate CSV (file 1)
            facility_csv_path: Path to facility CSV (file 2)

        Returns:
            dict with counts
        """
        _logger.info("Starting CSV import: corporate=%s, facility=%s",
                     corporate_csv_path, facility_csv_path)

        self.env["plasticos.partner.import.validation"].validate_reference_integrity()

        # Phase 1: Load corporates
        corporate_count = self._import_corporate_csv(corporate_csv_path)

        # Phase 2: Load facilities and their contacts
        facility_count, contact_count = self._import_facility_csv(facility_csv_path)

        self.env["plasticos.partner.import.validation"].validate_partner_graph()

        counts = {
            "corporates": corporate_count,
            "facilities": facility_count,
            "contacts": contact_count,
        }
        _logger.info("CSV import complete: %s", counts)
        return counts

    # -------------------------------------------------------------------------
    # CSV Import: Corporates
    # -------------------------------------------------------------------------
    def _import_corporate_csv(self, csv_path):
        """
        Import corporates from CSV file.

        CSV columns: ref, role, user_id, alias, name-check, name, street, street2,
                     city, state_id, zip, country
        """
        count = 0
        with open(csv_path, "r", encoding="utf-8-sig") as f:
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
        """Import single corporate row."""
        name = row.get("name", "").strip()
        if not name:
            _logger.warning("Skipping corporate row %d: empty name", row_num)
            return None

        ref = row.get("ref", "").strip()
        external_id = self._make_external_id("corp", ref or name)

        # Lookups
        country_id = self._lookup_country(row.get("country", ""))
        state_id = self._lookup_state(row.get("state_id", ""), country_id)
        user_id = self._lookup_user(row.get("user_id", ""))
        is_supplier, is_customer = self._parse_role(row.get("role", ""))

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
        }

        return self._upsert("res.partner", external_id, vals)

    # -------------------------------------------------------------------------
    # CSV Import: Facilities
    # -------------------------------------------------------------------------
    def _import_facility_csv(self, csv_path):
        """
        Import facilities from CSV file.

        CSV columns: partner_id, Type, is_remit, is_invoice_entity, is_facility,
                     Alias, company_id, address, adderess2, city, state, zip,
                     country, Contact, Phone, Email
        """
        facility_count = 0
        contact_count = 0
        contacts_created = {}  # Track contacts by (parent_id, name, email) to dedupe

        with open(csv_path, "r", encoding="utf-8-sig") as f:
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
                        _logger.info("Facilities progress: %d facilities, %d contacts",
                                     facility_count, contact_count)
                except Exception as e:
                    _logger.error("Error at facility row %d: %s", i, e)
                    raise

        _logger.info("Loaded %d facilities, %d contacts from CSV", facility_count, contact_count)
        return facility_count, contact_count

    def _import_facility_row(self, row, row_num, contacts_created):
        """Import single facility row with its contact."""
        partner_name = row.get("partner_id", "").strip()
        if not partner_name:
            _logger.warning("Skipping facility row %d: empty partner_id", row_num)
            return None, None

        facility_type = row.get("Type", "").strip()
        alias = row.get("Alias", "").strip()

        # Find parent corporate
        parent = self._find_corporate_by_name(partner_name)
        if not parent:
            _logger.warning("Skipping facility row %d: parent '%s' not found", row_num, partner_name)
            return None, None

        # Determine facility name
        facility_name = alias if alias and alias != "INVOICE" else f"{partner_name} - {facility_type}"

        # Lookups
        country_id = self._lookup_country(row.get("country", ""))
        state_id = self._lookup_state(row.get("state", ""), country_id)

        # Determine partner type based on facility type
        if facility_type in INVOICE_TYPES:
            partner_type = "invoice"
            x_facility_role = False
        elif facility_type == "Location":
            partner_type = "contact"  # Will be company with parent
            x_facility_role = "other"
        else:
            partner_type = "contact"
            x_facility_role = "other"

        # Build external ID
        external_id = self._make_external_id("fac", f"{partner_name}_{alias or facility_type}_{row_num}")

        # For Location type, create as company child
        # For Invoice types, create as address
        if facility_type == "Location":
            vals = {
                "name": facility_name,
                "company_type": "company",
                "is_company": True,
                "type": "contact",
                "parent_id": parent.id,
                "x_facility_role": x_facility_role,
                "street": row.get("address", "").strip() or False,
                "street2": row.get("adderess2", "").strip() or False,  # Note: typo in CSV
                "city": row.get("city", "").strip() or False,
                "state_id": state_id,
                "zip": row.get("zip", "").strip() or False,
                "country_id": country_id,
            }
        else:
            # Invoice/Remit address
            vals = {
                "name": facility_name,
                "company_type": "person",
                "is_company": False,
                "type": partner_type,
                "parent_id": parent.id,
                "street": row.get("address", "").strip() or False,
                "street2": row.get("adderess2", "").strip() or False,
                "city": row.get("city", "").strip() or False,
                "state_id": state_id,
                "zip": row.get("zip", "").strip() or False,
                "country_id": country_id,
            }

        facility = self._upsert("res.partner", external_id, vals)

        # Create contact if Contact/Phone/Email provided
        contact = None
        contact_name = row.get("Contact", "").strip()
        contact_phone = self._normalize_phone(row.get("Phone", ""))
        contact_email = self._normalize_email(row.get("Email", ""))

        if contact_name and contact_name not in ("Primary", "United States"):
            contact = self._create_facility_contact(
                facility, parent, contact_name, contact_phone, contact_email,
                facility_type, contacts_created
            )

        return facility, contact

    def _find_corporate_by_name(self, name):
        """Find corporate partner by name."""
        # Try exact match first
        partner = self.env["res.partner"].search([
            ("name", "=", name),
            ("parent_id", "=", False),
            ("is_company", "=", True),
        ], limit=1)
        if partner:
            return partner

        # Try ilike match
        partner = self.env["res.partner"].search([
            ("name", "ilike", name),
            ("parent_id", "=", False),
            ("is_company", "=", True),
        ], limit=1)
        return partner

    def _create_facility_contact(self, facility, corporate, name, phone, email,
                                  facility_type, contacts_created):
        """
        Create contact under facility with AR/AP logic.

        Rules:
        - If corporate is Supplier → AR contact (type='invoice')
        - If corporate is Customer → AP contact (type='contact')
        - If both → AR contact (AR takes priority, no duplicate)
        - Dedupe by (corporate_id, name, email)
        """
        # Dedupe key
        dedup_key = (corporate.id, name.lower(), (email or "").lower())
        if dedup_key in contacts_created:
            _logger.debug("Skipping duplicate contact: %s", name)
            return None

        # Determine contact type based on corporate's supplier/customer status
        is_supplier = corporate.supplier_rank > 0
        is_customer = corporate.customer_rank > 0

        if is_supplier:
            # AR contact - we pay them, this is their receivables contact
            contact_type = CONTACT_TYPE_AR
        elif is_customer:
            # AP contact - they pay us, this is their payables contact
            contact_type = CONTACT_TYPE_AP
        else:
            # Default to contact
            contact_type = "contact"

        # For Location types, use delivery contact type
        if facility_type == "Location":
            contact_type = CONTACT_TYPE_DELIVERY

        external_id = self._make_external_id(
            "contact",
            f"{corporate.name}_{name}_{facility.id}"
        )

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

        _logger.debug("Created %s contact '%s' under %s", contact_type, name, facility.name)
        return contact

    # -------------------------------------------------------------------------
    # Legacy methods (for backward compatibility)
    # -------------------------------------------------------------------------
    def _load_corporates(self, rows):
        """Load corporate-level partners from dict list."""
        count = 0
        for i, r in enumerate(rows):
            if not r.get("external_id"):
                raise ValidationError(f"BLOCKER: MISSING_EXTERNAL_ID at row {i}")

            vals = {
                "name": r["name"],
                "company_type": "company",
                "is_company": True,
                "parent_id": False,
                "country_id": r.get("country_id"),
                "state_id": r.get("state_id"),
                "user_id": r.get("user_id"),
            }

            self._upsert("res.partner", r["external_id"], vals)
            count += 1

            if count % BATCH_SIZE == 0:
                self.env.cr.commit()
                _logger.info("Corporates progress: %d/%d", count, len(rows))

        _logger.info("Loaded %d corporates", count)
        return count

    def _load_facilities(self, rows):
        """Load facility-level partners from dict list."""
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

            vals = {
                "name": r["name"],
                "company_type": "company",
                "is_company": True,
                "parent_id": parent.id,
                "x_facility_role": r.get("x_facility_role", "other"),
            }

            self._upsert("res.partner", r["external_id"], vals)
            count += 1

            if count % BATCH_SIZE == 0:
                self.env.cr.commit()
                _logger.info("Facilities progress: %d/%d", count, len(rows))

        _logger.info("Loaded %d facilities", count)
        return count

    def _load_contacts(self, rows):
        """Load contact-level partners from dict list."""
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
                _logger.info("Contacts progress: %d/%d", count, len(rows))

        _logger.info("Loaded %d contacts", count)
        return count
