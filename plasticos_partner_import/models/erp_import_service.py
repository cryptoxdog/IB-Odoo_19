"""ERP -> PlasticOS historical import (one deterministic pipeline).

One-way import of the ERP SQL in
``plasticos_partner_import/erp_extracted_data/`` into the current Odoo models.
When that folder has no ``INSERT`` rows, the frozen grid extract is used.
No UI, no wizard,
no menu, no cron, no queue, no ETL framework: a single non-interactive
entrypoint that calls already-tested source functions.

Pipeline::

    tracked ERP export
        -> erp.reader          (exact-format source rows)
        -> erp.source_index    (CpID / AddressID / CT_ID / CRA_ID /
                                     BuySellNo / DetailID)
        -> erp.header_forensics(supplier / buyer / date / state)
        -> this service             (deterministic upsert into current models)

Identity is always a stable ERP key resolved through ``ir.model.data``.
Company names, e-mail addresses, phone numbers, address text, and Odoo database
ids are never identity.

Atomicity: one ``BuySellNo`` is one logical unit. Header, every line, and every
identity marker are written inside a single savepoint, so a failing line leaves
no partial transaction and no stale marker — a retry reprocesses it cleanly.
This replaces ``transaction_import_service``, which committed every 100 records
mid-transaction and created transactions with no buyer, supplier, or date.
"""

from __future__ import annotations

import logging

from odoo import Command, api, models

_logger = logging.getLogger(__name__)

RES_PARTNER = "res.partner"
PLASTICOS_TRANSACTION = "plasticos.transaction"
PLASTICOS_TRANSACTION_LINE = "plasticos.transaction.line"
PARTNER_CATEGORY = "res.partner.category"

# ir.model.data namespace for ERP source identity.
# Markers were minted under plasticos_transaction. Keep that module name so a
# re-import updates the same records instead of creating a second set.
XMLID_MODULE = "plasticos_transaction"

# One partner file per invocation. The validator must pass before the next file.
PARTNER_LAYERS = ("counterparties", "addresses", "contacts", "roles")
LAYER_TABLE = {
    "counterparties": "CounterParty",
    "addresses": "Address",
    "contacts": "Contact",
    "roles": "ContactRoleAssignment",
}
PARTNER_COUNT_PARAM = "plasticos_partner_import.partner_count_after_contacts"
IMPORT_CONTEXT = {
    "import_mode": True,
    "tracking_disable": True,
    "mail_create_nolog": True,
    "mail_notrack": True,
}


class PlasticosErpImport(models.AbstractModel):
    """Deterministic, replay-safe ERP historical import."""

    _name = "plasticos.erp.import"
    _description = "ERP Historical Import"

    # ------------------------------------------------------------------
    # Entrypoint
    # ------------------------------------------------------------------
    @api.model
    def run(
        self,
        payload_root: str | None = None,
        limit: int | None = None,
        commit: bool = False,
        dry_run: bool = False,
        partners_only: bool = False,
        layer: str | None = None,
    ) -> dict:
        """Run the complete import and return an accounting report.

        Args:
            payload_root: Override the payload location. Defaults to SQL in
                ``plasticos_partner_import/erp_extracted_data``, then the
                frozen grid pack.
            limit: Process at most this many transactions (diagnostics only).
            commit: Commit between complete transactions. Never mid-transaction.
                A partners-only run commits once, after the people are written.
            dry_run: Resolve and map everything, persist nothing.
            partners_only: Read and write only CounterParty, Address, Contact,
                and ContactRoleAssignment. Deal files are not opened.
            layer: One of ``counterparties``, ``addresses``, ``contacts``,
                ``roles``. Only that source file is opened. The parent records
                are the partners already stored under their source keys.

        Returns:
            Per-entity created/updated/skipped counts plus every unresolved
            reference and mapping anomaly encountered.
        """
        # Lazy import: the source layer is Odoo-free and must not be imported
        # at addon load time.
        from ..erp import header_forensics, reader, source_index
        from ..erp import report as report_module

        if layer and layer not in PARTNER_LAYERS:
            raise ValueError(f"unknown partner layer {layer!r}")
        if layer:
            only = frozenset({LAYER_TABLE[layer]})
        else:
            only = reader.PARTNER_SOURCE_TABLES if partners_only else None
        payload = reader.load_payload(payload_root, only=only)
        index = source_index.build_source_index(payload)
        _logger.info("ERP payload loaded (%s): %s", payload.kind.value, payload.row_counts())

        report = report_module.ImportReport()
        report.payload_kind = payload.kind.value
        report.source_counts = index.counts()
        for violation in index.violations:
            report.unresolved.append(violation.as_dict())

        if layer == "counterparties":
            self._import_counterparties(index, report, dry_run)
        elif layer == "addresses":
            partner_by_cp = self._partners_by_prefix("legacy_erp_cp_")
            self._import_addresses(index, report, partner_by_cp, dry_run)
        elif layer == "contacts":
            partner_by_cp = self._partners_by_prefix("legacy_erp_cp_")
            self._import_contacts(index, report, partner_by_cp, dry_run)
            if not dry_run:
                self._stamp_partner_count()
        elif layer == "roles":
            self._import_roles(index, report, dry_run)
        else:
            partner_by_cp = self._import_counterparties(index, report, dry_run)
            self._import_addresses(index, report, partner_by_cp, dry_run)
            self._import_contacts(index, report, partner_by_cp, dry_run)
            if partners_only:
                self._import_roles(index, report, dry_run)
                if commit and not dry_run:
                    self.env.cr.commit()
                result = report.as_dict()
                _logger.info("ERP import finished (partners only): %s", result["counts"])
                return result

            headers = header_forensics.reconstruct_all_headers(index)
            self._import_transactions(index, headers, report, partner_by_cp, limit, commit, dry_run)

        if layer and commit and not dry_run:
            self.env.cr.commit()
        result = report.as_dict()
        _logger.info("ERP import finished%s: %s", f" ({layer})" if layer else "", result["counts"])
        return result

    # ------------------------------------------------------------------
    # Stage 1 — counterparties
    # ------------------------------------------------------------------
    def _import_counterparties(self, index, report, dry_run: bool) -> dict:
        from ..erp import mapping

        Partner = self.env[RES_PARTNER].with_context(**IMPORT_CONTEXT)
        partner_by_cp: dict[str, int] = {}

        for cp_id in index.counterparty_ids():
            row = index.counterparties[cp_id]
            name = _text(row, "CompanyNm")
            if not name:
                report.anomaly("CounterParty", cp_id, "blank CompanyNm")
                report.reject("counterparties")
                continue

            role, role_anomaly = mapping.company_role(row.get("Role"))
            if role_anomaly:
                report.anomaly("CounterParty", cp_id, role_anomaly)
            supplier_rank, customer_rank = mapping.trade_ranks(row.get("Role"))
            active = _text(row, "ActiveStatus").upper() != "I"

            values = {
                "name": name,
                "is_company": True,
                "active": active,
                "entity_status": "active" if active else "inactive",
                "supplier_rank": supplier_rank,
                "customer_rank": customer_rank,
            }
            if role:
                values["company_role"] = role
            _set_if(values, "ref", _text(row, "OurCustNo"))
            _set_if(values, "email", _text(row, "APEMail"))
            _set_if(values, "website", _text(row, "WebSite"))

            credit_limit = mapping.parse_decimal(row.get("CreditLimit"))
            if credit_limit and "credit_limit" in Partner._fields:
                values["credit_limit"] = credit_limit

            self._resolve_payment_term(values, row, cp_id, report)
            self._resolve_industry(values, row, cp_id, report)

            if dry_run:
                report.skip("counterparties")
                continue

            partner = self._upsert(Partner, f"legacy_erp_cp_{cp_id}", values, report, "counterparties")
            partner_by_cp[cp_id] = partner.id

        return partner_by_cp

    def _resolve_payment_term(self, values: dict, row, cp_id: str, report) -> None:
        """Link ``TermsCode`` to an existing payment term. Never create one."""
        terms_code = _text(row, "TermsCode")
        if not terms_code or "property_supplier_payment_term_id" not in self.env[RES_PARTNER]._fields:
            return
        term = self.env["account.payment.term"].search([("name", "=", terms_code)], limit=1)
        if term:
            values["property_supplier_payment_term_id"] = term.id
        else:
            report.anomaly("CounterParty", cp_id, f"no account.payment.term named {terms_code!r}")

    def _resolve_industry(self, values: dict, row, cp_id: str, report) -> None:
        """Link ``IndustryNm`` to an existing industry. Never create one."""
        industry_name = _text(row, "IndustryNm")
        if not industry_name or "industry_id" not in self.env[RES_PARTNER]._fields:
            return
        industry = self.env["res.partner.industry"].search([("name", "=", industry_name)], limit=1)
        if industry:
            values["industry_id"] = industry.id
        else:
            report.anomaly("CounterParty", cp_id, f"no res.partner.industry named {industry_name!r}")

    # ------------------------------------------------------------------
    # Stage 2 — facilities / locations
    # ------------------------------------------------------------------
    def _import_addresses(self, index, report, partner_by_cp: dict, dry_run: bool) -> dict:
        from ..erp import mapping

        Partner = self.env[RES_PARTNER].with_context(**IMPORT_CONTEXT)
        partner_by_address: dict[str, int] = {}

        for cp_id in sorted(index.addresses_by_cp):
            parent_id = partner_by_cp.get(cp_id)
            if not parent_id and not dry_run:
                # The parent failure suppresses every address row under this
                # CpID. Account for each source row (one unresolved entry per
                # AddressID) so ``seen == created + updated + unchanged +
                # rejected`` still closes in the shared summary.
                for address_id in index.addresses_by_cp[cp_id]:
                    report.unresolved_ref(
                        "Address", "parent_not_imported", address_id, f"counterparty {cp_id} partner was not created"
                    )
                continue

            billing_rows = []
            location_rows = []
            for address_id in index.addresses_by_cp[cp_id]:
                row = index.addresses[address_id]
                if mapping.address_kind(row) == "invoice":
                    billing_rows.append((address_id, row))
                else:
                    location_rows.append((address_id, row))

            # One company partner per counterparty. Its remit is written onto
            # that partner. Another address is a location under it, never a
            # second company with the same name.
            canonical_id = _canonical_billing_id(billing_rows)
            parent = Partner.browse(parent_id) if parent_id else Partner.browse()
            parent_name = parent.name if parent else ""
            ordered = []
            if canonical_id:
                ordered.append(next(pair for pair in billing_rows if pair[0] == canonical_id))
            ordered.extend(pair for pair in (*billing_rows, *location_rows) if pair[0] != canonical_id)
            for address_id, row in ordered:
                if dry_run:
                    report.skip("locations")
                    continue
                if parent and (address_id == canonical_id or _same_party_name(_text(row, "Addr1"), parent_name)):
                    wrote = self._apply_billing_address(parent, row)
                    company_street = (parent.street or "").casefold()
                    row_street = _text(row, "Addr2").casefold()
                    if row_street and company_street and row_street != company_street:
                        self._create_location(
                            Partner,
                            row,
                            address_id,
                            parent.id,
                            parent_name,
                            partner_by_address,
                            report,
                            dry_run,
                            child_name=_location_title(row, parent_name),
                        )
                    else:
                        partner_by_address[address_id] = parent.id
                        report.bump("locations", "updated" if wrote else "skipped")
                    continue
                self._create_location(
                    Partner, row, address_id, parent_id, parent_name, partner_by_address, report, dry_run
                )

        return partner_by_address

    def _create_location(
        self,
        partner_model,
        row,
        address_id,
        parent_id,
        parent_name,
        partner_by_address,
        report,
        dry_run,
        child_name: str | None = None,
    ) -> None:
        """A location under the company. It is a company, not a second counterparty."""
        from ..erp import mapping

        kind = mapping.address_kind(row)
        parent = partner_model.browse(parent_id) if parent_id else partner_model.browse()
        values = {
            "name": child_name or _location_title(row, parent_name),
            "parent_id": parent_id,
            "is_company": True,
            "type": mapping.ODOO_ADDRESS_TYPE[kind],
        }
        values.update(self._copied_role(parent))
        if "erp_address_label" in partner_model._fields:
            values["erp_address_label"] = _text(row, "Type")
        self._address_values(values, row)
        if dry_run:
            report.skip("locations")
            return
        partner = self._upsert(partner_model, f"legacy_erp_address_{address_id}", values, report, "locations")
        partner_by_address[address_id] = partner.id
        self._sync_address_phones(partner, row)

    def _apply_billing_address(self, partner, row) -> bool:
        """Write the company's remit onto the company. Never a second partner.

        Fills only blank fields, so a counterparty email already stored from
        ``APEMail`` is kept. The remit is not copied onto facility children.
        """
        values = {}

        def fill(field_name: str, value: str) -> None:
            if value and field_name in partner._fields and not partner[field_name]:
                values[field_name] = value

        fill("street", _text(row, "Addr2"))
        fill("street2", _text(row, "Addr3"))
        fill("city", _text(row, "City"))
        fill("zip", _text(row, "PostalCd"))
        fill("phone", _real_phone(row.get("Telephone")))
        fill("email", _text(row, "Email") or _text(row, "BillingEmail"))
        geo: dict = {}
        self._resolve_country_state(geo, row)
        for field_name in ("country_id", "state_id"):
            if geo.get(field_name) and not partner[field_name]:
                values[field_name] = geo[field_name]
        if not values:
            self._sync_address_phones(partner, row)
            return False
        partner.write(values)
        self._sync_address_phones(partner, row)
        return True

    def _fill_company_from_contact(self, index, cp_id: str, company_partner_id: int) -> None:
        """Put the primary contact's phone and email on the company when it has none.

        The ERP stores the number and the mailbox on the person. The company
        is who we trade with, so those values also land on the company. A
        value already taken from the counterparty or the remit is left as-is.
        """
        partner = self.env[RES_PARTNER].browse(company_partner_id)
        if partner.email and partner.phone:
            return
        chosen = None
        fallback = None
        for contact_id in index.contacts_by_cp.get(cp_id, []):
            row = index.contacts[contact_id]
            if not _text(row, "Email") and not _text(row, "PhoneBusiness"):
                continue
            roles = [role.lower() for role in self._contact_roles(index, contact_id)]
            if "primary" in roles:
                chosen = row
                break
            if fallback is None:
                fallback = row
        row = chosen or fallback
        if not row:
            return
        values = {}
        if not partner.email and _text(row, "Email"):
            values["email"] = _text(row, "Email")
        if not partner.phone and _text(row, "PhoneBusiness"):
            values["phone"] = _text(row, "PhoneBusiness")
        if values:
            partner.write(values)

    def _address_values(self, values: dict, row) -> None:
        """ERP: Addr2 is the street, Addr3 is the second street line."""
        _set_if(values, "street", _text(row, "Addr2"))
        _set_if(values, "street2", _text(row, "Addr3"))
        _set_if(values, "city", _text(row, "City"))
        _set_if(values, "zip", _text(row, "PostalCd"))
        _set_if(values, "phone", _real_phone(row.get("Telephone")))
        _set_if(values, "email", _text(row, "Email") or _text(row, "BillingEmail"))
        self._resolve_country_state(values, row)

    def _resolve_country_state(self, values: dict, row) -> None:
        """Resolve country/state to existing records only.

        Most address rows leave Country blank and put a US state code in
        Region. A blank country is resolved as United States when that code
        matches a US state.
        """
        code = _text(row, "Country").upper()
        if code == "NULL":
            code = ""
        country = self.env["res.country"].search([("code", "=", code)], limit=1) if len(code) == 2 else None
        region = _text(row, "Region")
        if not country and region:
            state = self.env["res.country.state"].search(
                [("code", "=", region), ("country_id.code", "=", "US")],
                limit=1,
            )
            if state:
                values["country_id"] = state.country_id.id
                values["state_id"] = state.id
                return
        if not country:
            return
        values["country_id"] = country.id
        if not region:
            return
        state = self.env["res.country.state"].search(
            [("country_id", "=", country.id), "|", ("code", "=", region), ("name", "=", region)],
            limit=1,
        )
        if state:
            values["state_id"] = state.id

    # ------------------------------------------------------------------
    # Stage 3 — contacts and contact roles
    # ------------------------------------------------------------------
    def _import_contacts(self, index, report, partner_by_cp: dict, dry_run: bool) -> None:
        """One person per company and name, parented to the company.

        A contact whose name is only a phone number is not a person. The
        number and the email land on the company. Role tags are a later layer.
        """
        from ..erp import mapping

        Partner = self.env[RES_PARTNER].with_context(**IMPORT_CONTEXT, active_test=False)
        catalog = self._address_catalog()
        mailbox_keys = mapping.site_mailbox_keys(_mailbox_companies_from(index, catalog))

        for cp_id in sorted(index.contacts_by_cp):
            company_partner_id = partner_by_cp.get(cp_id)
            if not company_partner_id and not dry_run:
                for contact_id in index.contacts_by_cp[cp_id]:
                    report.unresolved_ref(
                        "Contact", "parent_not_imported", contact_id, f"counterparty {cp_id} partner was not created"
                    )
                continue

            if company_partner_id and not dry_run:
                self._fill_company_from_contact(index, cp_id, company_partner_id)

            groups: dict[str, list] = {}
            order: list[str] = []
            addresses = [
                (address_id, label) for item_cp, address_id, label, _partner_id in catalog if item_cp == cp_id and label
            ]
            partner_by_address = {
                address_id: partner_id for item_cp, address_id, _label, partner_id in catalog if item_cp == cp_id
            }
            for contact_id in index.contacts_by_cp[cp_id]:
                row = index.contacts[contact_id]
                name = _text(row, "ContactNm")
                if not name:
                    report.anomaly("Contact", contact_id, "blank ContactNm")
                    report.reject("contacts")
                    continue
                if not mapping.is_person_name(name):
                    if not dry_run and company_partner_id:
                        self._apply_non_person(Partner.browse(company_partner_id), row)
                    report.skip("contacts")
                    continue
                target = mapping.site_mailbox_target(name, addresses, _text(row, "Location"), mailbox_keys)
                if target:
                    if not dry_run:
                        self._apply_site_mailbox(partner_by_address, target, row)
                    report.skip("contacts")
                    continue
                key = mapping.person_key(name)
                if key not in groups:
                    order.append(key)
                    groups[key] = []
                groups[key].append((contact_id, row))

            label_to_partner = {
                label: partner_id for item_cp, _address_id, label, partner_id in catalog if item_cp == cp_id and label
            }
            for key in order:
                self._import_person(
                    Partner,
                    groups[key],
                    company_partner_id,
                    label_to_partner,
                    report,
                    dry_run,
                    mapping,
                )

    def _import_person(
        self, partner_model, members, company_partner_id, label_to_partner, report, dry_run, mapping
    ) -> None:
        """One person per company plus first and last name. Every CT_ID aliases that person."""
        members = sorted(members, key=_contact_sort_key)
        name = _text(members[0][1], "ContactNm")
        active = any(_row_active(row, mapping) for _contact_id, row in members)
        parent = partner_model.browse(company_partner_id) if company_partner_id else partner_model.browse()
        values = {
            "name": name,
            "parent_id": company_partner_id,
            "is_company": False,
            "type": "contact",
            "active": active,
        }
        values.update(self._copied_role(parent))
        phone_lines = self._merge_person_channels(values, members, report)
        location_ids = []
        for _contact_id, row in members:
            loc = _text(row, "Location")
            partner_id = label_to_partner.get(loc)
            if partner_id and partner_id != company_partner_id and partner_id not in location_ids:
                location_ids.append(partner_id)

        if dry_run:
            report.skip("contacts", len(members))
            return

        anchor = self._anchor_contact_id(partner_model, members)
        partner = self._upsert(partner_model, f"legacy_erp_contact_{anchor}", values, report, "contacts")
        for contact_id, _row in members:
            if contact_id == anchor:
                continue
            self._alias_xmlid(partner_model, f"legacy_erp_contact_{contact_id}", partner, report, "contacts")
        if "location_partner_ids" in partner._fields:
            partner.write({"location_partner_ids": [(6, 0, location_ids)]})
        self._sync_phone_lines(partner, phone_lines)

    def _merge_person_channels(self, values: dict, members, report) -> list:
        """Union emails and phones. The first business number stays in ``phone``."""
        from ..erp import mapping

        comments: list[str] = []
        business: list[str] = []
        lines: list[tuple[str, str]] = []
        for contact_id, row in members:
            _keep_first(values, "email", _text(row, "Email"), report, contact_id)
            number = mapping.real_phone(row.get("PhoneBusiness"))
            if number and number not in business:
                business.append(number)
            mobile = mapping.real_phone(row.get("PhoneMobile"))
            if mobile:
                lines.append(("mobile", mobile))
            other = mapping.real_phone(row.get("PhoneOther"))
            if other:
                lines.append(("other", other))
            fax = mapping.fax_from_notes(_text(row, "Notes"))
            if fax:
                lines.append(("fax", fax))
            notes = _text(row, "Notes")
            if notes and not notes.lower().startswith("fax:") and notes not in comments:
                comments.append(notes)
        if business:
            values["phone"] = business[0]
            lines.extend(("other", number) for number in business[1:])
        if comments:
            values["comment"] = "\n".join(comments)
        return lines

    def _apply_non_person(self, company, row) -> None:
        """A phone-number contact title is not a person. Keep the channels on the company."""
        from ..erp import mapping

        values = {}
        if not company.phone:
            number = mapping.real_phone(row.get("PhoneBusiness"))
            if number:
                values["phone"] = number
        if not company.email and _text(row, "Email"):
            values["email"] = _text(row, "Email")
        if values:
            company.write(values)
        lines = []
        mobile = mapping.real_phone(row.get("PhoneMobile"))
        if mobile:
            lines.append(("mobile", mobile))
        other = mapping.real_phone(row.get("PhoneOther"))
        if other:
            lines.append(("other", other))
        fax = mapping.fax_from_notes(_text(row, "Notes"))
        if fax:
            lines.append(("fax", fax))
        self._sync_phone_lines(company, lines)

    def _import_roles(self, index, report, dry_run: bool) -> None:
        """Tag the person already stored for each CT_ID. Create no partner."""
        from ..erp import mapping

        Partner = self.env[RES_PARTNER].with_context(**IMPORT_CONTEXT, active_test=False)
        tag_cache: dict[str, int] = {}
        grouped: dict[int, dict] = {}
        unresolved_rr: list[str] = []
        for role_id in sorted(index.contact_roles):
            row = index.contact_roles[role_id]
            contact_id = _text(row, "CT_ID")
            partner = self._partner_by_xmlid(Partner, f"legacy_erp_contact_{contact_id}")
            if not partner:
                report.unresolved_ref(
                    "ContactRoleAssignment",
                    "unresolved_contact",
                    role_id,
                    f"CT_ID={contact_id} has no imported person",
                )
                continue
            tag, reason = mapping.map_contact_role(row.get("RoleNm"))
            if reason == "rr":
                unresolved_rr.append(contact_id)
                report.unresolved_ref("ContactRoleAssignment", "unresolved_rr", contact_id, "RR")
                continue
            if not tag:
                report.anomaly("ContactRoleAssignment", role_id, f"unmapped role {row.get('RoleNm')!r}")
                continue
            bucket = grouped.setdefault(partner.id, {"partner": partner, "tags": []})
            if tag not in bucket["tags"]:
                bucket["tags"].append(tag)
        if not dry_run:
            self.env["ir.config_parameter"].set_param(
                "plasticos_partner_import.unresolved_rr",
                ",".join(sorted(set(unresolved_rr))),
            )
        if dry_run:
            return
        for bucket in grouped.values():
            partner = bucket["partner"]
            self._apply_contact_roles(partner, bucket["tags"], tag_cache, report)
            job = mapping.job_position(bucket["tags"])
            if job and partner.function != job:
                partner.write({"function": job})

    def _address_catalog(self) -> list[tuple[str, str, str, int]]:
        """``(cp_id, address_id, Type label, partner_id)`` for every imported address."""
        Partner = self.env[RES_PARTNER].with_context(active_test=False)
        cp_by_partner = self._partners_by_prefix("legacy_erp_cp_")
        partner_to_cp = {partner_id: cp_id for cp_id, partner_id in cp_by_partner.items()}
        catalog = []
        data = self.env["ir.model.data"].search(
            [
                ("module", "=", XMLID_MODULE),
                ("model", "=", RES_PARTNER),
                ("name", "=like", "legacy_erp_address_%"),
            ]
        )
        for row in data:
            address_id = row.name.removeprefix("legacy_erp_address_")
            partner = Partner.browse(row.res_id).exists()
            if not partner:
                continue
            company = partner.parent_id or partner
            cp_id = partner_to_cp.get(company.id) or partner_to_cp.get(partner.id) or ""
            catalog.append((cp_id, address_id, partner.erp_address_label or "", partner.id))
        return catalog

    def _partners_by_prefix(self, prefix: str) -> dict[str, int]:
        """Source key to partner id for xmlids that start with ``prefix``."""
        found: dict[str, int] = {}
        data = self.env["ir.model.data"].search(
            [
                ("module", "=", XMLID_MODULE),
                ("model", "=", RES_PARTNER),
                ("name", "=like", prefix + "%"),
            ]
        )
        for row in data:
            key = row.name.removeprefix(prefix)
            if key:
                found[key] = row.res_id
        return found

    def _stamp_partner_count(self) -> None:
        """Remember how many partners exist after the contact layer."""
        self.env.cr.execute("SELECT count(*) FROM res_partner")
        count = int(self.env.cr.fetchone()[0])
        self.env["ir.config_parameter"].set_param(PARTNER_COUNT_PARAM, str(count))

    def _sync_address_phones(self, partner, row) -> None:
        from ..erp import mapping

        self._sync_phone_lines(
            partner,
            [
                ("mobile", mapping.real_phone(row.get("MobilePhone"))),
                ("fax", mapping.real_phone(row.get("Fax"))),
            ],
        )

    def _sync_phone_lines(self, partner, lines: list) -> None:
        """Add labeled numbers that are not already on the partner."""
        if "phone_line_ids" not in partner._fields:
            return
        present = {(line.label, line.number) for line in partner.phone_line_ids}
        commands = []
        for label, number in lines:
            if not number or (label, number) in present:
                continue
            present.add((label, number))
            commands.append(Command.create({"label": label, "number": number}))
        if commands:
            partner.with_context(**IMPORT_CONTEXT).write({"phone_line_ids": commands})

    def _anchor_contact_id(self, partner_model, members) -> str:
        """Prefer a CT_ID that already points at a partner, so a replay updates it."""
        for contact_id, _row in members:
            if self._partner_by_xmlid(partner_model, f"legacy_erp_contact_{contact_id}"):
                return contact_id
        return members[0][0]

    def _partner_by_xmlid(self, model, xml_id: str):
        data = self.env["ir.model.data"].search(
            [("module", "=", XMLID_MODULE), ("name", "=", xml_id), ("model", "=", model._name)],
            limit=1,
        )
        if not data or not data.res_id:
            return model.browse()
        return model.with_context(active_test=False).browse(data.res_id).exists()

    def _alias_xmlid(self, model, xml_id: str, record, report, bucket: str) -> None:
        """Point another CT_ID at the one person. Does not create a second partner."""
        data = self.env["ir.model.data"].search(
            [("module", "=", XMLID_MODULE), ("name", "=", xml_id), ("model", "=", model._name)],
            limit=1,
        )
        if data and data.res_id == record.id:
            report.bump(bucket, "skipped")
            return
        if data:
            data.write({"res_id": record.id, "model": model._name})
            report.bump(bucket, "updated")
            return
        self._write_identity_marker(model, xml_id, record)
        report.bump(bucket, "skipped")

    def _contact_roles(self, index, contact_id: str) -> list:
        """Ordered role names for a contact. ``Primary`` sorts first."""
        from ..erp import mapping

        names = []
        for role_id in index.roles_by_contact.get(contact_id, []):
            role = mapping.normalize_contact_role(index.contact_roles[role_id].get("RoleNm"))
            if role and role not in names:
                names.append(role)
        return mapping.sort_contact_roles(names)

    def _apply_contact_roles(self, partner, roles: list, tag_cache: dict, report) -> None:
        """Carry ERP contact roles on the existing partner-tag mechanism.

        ``res.partner.category`` is the repository's multi-valued partner
        classification. Tag membership is set semantics, so replaying an
        assignment is inherently idempotent — which is what ``CRA_ID``
        replay-safety requires. No roles subsystem is introduced.
        """
        if not roles:
            return
        tag_ids = [self._role_tag_id(role, tag_cache, report) for role in roles]
        tag_ids = [tag_id for tag_id in tag_ids if tag_id]
        if not tag_ids:
            return
        existing = set(partner.category_id.ids)
        missing = [tag_id for tag_id in tag_ids if tag_id not in existing]
        if missing:
            partner.write({"category_id": [(4, tag_id) for tag_id in missing]})
            report.bump("contact_roles", "created", len(missing))
        else:
            report.bump("contact_roles", "skipped", len(tag_ids))

    def _role_tag_id(self, role: str, tag_cache: dict, report) -> int | None:
        if role in tag_cache:
            return tag_cache[role]
        Category = self.env[PARTNER_CATEGORY].with_context(**IMPORT_CONTEXT)
        parent = self._upsert(Category, "legacy_erp_contact_role_root", {"name": "ERP Contact Role"}, report, None)
        tag = self._upsert(
            Category,
            f"legacy_erp_contact_role_tag_{_slug(role)}",
            {"name": role, "parent_id": parent.id},
            report,
            None,
        )
        tag_cache[role] = tag.id
        return tag.id

    # ------------------------------------------------------------------
    # Stage 4 — transactions and lines (atomic per BuySellNo)
    # ------------------------------------------------------------------
    def _import_transactions(
        self, index, headers, report, partner_by_cp: dict, limit, commit: bool, dry_run: bool
    ) -> None:
        buysell_numbers = index.buysell_numbers()
        if limit:
            buysell_numbers = buysell_numbers[:limit]

        for buysell_no in buysell_numbers:
            header = headers[buysell_no]
            for anomaly in header.anomalies:
                report.anomaly("Transaction", buysell_no, anomaly)

            if dry_run:
                report.skip("transactions")
                report.bump("transaction_lines", "skipped", len(header.detail_ids))
                continue

            try:
                # One BuySellNo = one logical unit. Header, all lines, and all
                # identity markers commit together or not at all.
                with self.env.cr.savepoint():
                    self._import_one_transaction(index, header, report, partner_by_cp)
            except Exception as exc:  # noqa: BLE001 - one bad unit must not abort the run
                report.error(buysell_no, str(exc))
                _logger.exception("ERP transaction %s failed and was rolled back", buysell_no)
                continue

            if commit:
                # Only ever between complete transactions.
                self.env.cr.commit()

    def _import_one_transaction(self, index, header, report, partner_by_cp: dict) -> None:
        Transaction = self.env[PLASTICOS_TRANSACTION].with_context(**IMPORT_CONTEXT)

        values = {"name": header.buysell_no, "state": header.state}
        supplier_id = partner_by_cp.get(header.supplier_cp_id) if header.supplier_cp_id else None
        buyer_id = partner_by_cp.get(header.buyer_cp_id) if header.buyer_cp_id else None
        if supplier_id:
            values["supplier_id"] = supplier_id
        if buyer_id:
            values["buyer_id"] = buyer_id

        # The reconstructed trade date is written only where a semantically
        # correct field exists. No field is invented for it; see
        # docs/erp_import_mapping.md, "Evidenced new-field candidate".
        if header.trade_date and "transaction_date" in Transaction._fields:
            values["transaction_date"] = header.trade_date

        transaction = self._upsert(
            Transaction, f"legacy_erp_transaction_{header.buysell_no}", values, report, "transactions"
        )
        self._import_lines(index, header, transaction, report)

    def _import_lines(self, index, header, transaction, report) -> None:
        from ..erp import mapping

        Line = self.env[PLASTICOS_TRANSACTION_LINE].with_context(**IMPORT_CONTEXT)

        for detail_id in header.detail_ids:
            row = index.lines[detail_id]
            values = {
                "transaction_id": transaction.id,
                "detail_id": detail_id,
                "units": mapping.parse_decimal(row.get("Units")) or 1.0,
            }
            _set_if(values, "grade_id", _text(row, "GradeID"))
            _set_if(values, "description", _text(row, "InvoiceDesc"))
            _set_if(values, "lot_no", _text(row, "LotNo"))
            _set_if(values, "color", _text(row, "Color"))
            _set_if(values, "sale_po", _text(row, "SPo"))
            _set_if(values, "purchase_po", _text(row, "PPo"))
            _set_if(values, "specifications", _text(row, "Comment"))

            for target, column in (
                ("sale_weight", "SWeight"),
                ("purchase_weight", "PWeight"),
                ("sale_price", "SPrice"),
                ("purchase_price", "PPrice"),
                ("sale_amount", "SAmount"),
                ("purchase_amount", "PAmount"),
            ):
                parsed = mapping.parse_decimal(row.get(column))
                if parsed is None and _text(row, column):
                    report.anomaly("WKSDetail", detail_id, f"unparsable {column}={row.get(column)!r}")
                elif parsed is not None:
                    values[target] = parsed

            uom, uom_anomaly = mapping.weight_uom(row.get("SWeightUOM"), row.get("PWeightUOM"))
            if uom:
                values["weight_uom"] = uom
            elif uom_anomaly:
                report.anomaly("WKSDetail", detail_id, uom_anomaly)

            unit, unit_anomaly = mapping.unit_type(row.get("UnitType"))
            if unit:
                values["unit_type"] = unit
            elif unit_anomaly:
                report.anomaly("WKSDetail", detail_id, unit_anomaly)

            self._upsert(Line, f"legacy_erp_detail_{detail_id}", values, report, "transaction_lines")

    # ------------------------------------------------------------------
    # Deterministic upsert through ir.model.data
    # ------------------------------------------------------------------
    def _upsert(self, model, xml_id: str, values: dict, report, bucket: str | None):
        """Create or update the record owning ``xml_id``.

        The identity marker is written in the same transaction as the record, so
        a rollback removes both and a retry re-creates them together.
        """
        if model._name == RES_PARTNER:
            source_id = self._erp_lead_source_id()
            if source_id:
                values["lead_source_id"] = source_id

        data = self.env["ir.model.data"].search(
            [("module", "=", XMLID_MODULE), ("name", "=", xml_id), ("model", "=", model._name)],
            limit=1,
        )
        if data and data.res_id:
            record = model.browse(data.res_id).exists()
            if record:
                changed = {k: v for k, v in values.items() if _differs(record, k, v)}
                if changed:
                    record.write(changed)
                    if bucket:
                        report.bump(bucket, "updated")
                elif bucket:
                    report.bump(bucket, "skipped")
                return record
            data.unlink()

        record = model.create(values)
        self._write_identity_marker(model, xml_id, record)
        if bucket:
            report.bump(bucket, "created")
        return record

    def _write_identity_marker(self, model, xml_id: str, record) -> None:
        """Bind ``xml_id`` to an existing ``record`` in the ERP identity namespace."""
        self.env["ir.model.data"].create(
            {
                "module": XMLID_MODULE,
                "name": xml_id,
                "model": model._name,
                "res_id": record.id,
                "noupdate": True,
            }
        )

    def _copied_role(self, parent) -> dict:
        """The child's Company Role and ranks are the parent's."""
        if not parent:
            return {}
        values = {
            "supplier_rank": parent.supplier_rank or 0,
            "customer_rank": parent.customer_rank or 0,
        }
        if parent.company_role:
            values["company_role"] = parent.company_role
        return values

    def _apply_site_mailbox(self, partner_by_address: dict, address_id: str, row) -> None:
        """Put a site mailbox on the location when that location has no email yet."""
        partner_id = partner_by_address.get(address_id)
        if not partner_id:
            return
        partner = self.env[RES_PARTNER].browse(partner_id)
        email = _text(row, "Email").split(";")[0].strip()
        if email and not partner.email:
            partner.write({"email": email})

    def _erp_lead_source_id(self) -> int | bool:
        """``utm.source`` named ERP. Missing seed leaves the field unset."""
        source = self.env.ref("plasticos_crm_bridge.utm_source_erp", raise_if_not_found=False)
        return source.id if source else False


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------
def _text(row, column: str) -> str:
    return (row.get(column) or "").strip()


def _joined(row, columns) -> str:
    return ", ".join(part for part in (_text(row, c) for c in columns) if part)


def _set_if(values: dict, key: str, value) -> None:
    if value:
        values[key] = value


def _differs(record, field_name: str, value) -> bool:
    """True when writing ``value`` would actually change ``record``."""
    if field_name not in record._fields:
        return False
    current = record[field_name]
    if hasattr(current, "id"):
        current = current.id or False
    return current != (value if value is not None else False)


def _same_party_name(left: str, right: str) -> bool:
    """True when two labels are the same company once punctuation and spacing are ignored."""

    def norm(value: str) -> str:
        return "".join(ch for ch in (value or "").upper() if ch.isalnum())

    a, b = norm(left), norm(right)
    return not a or not b or a == b


def _mailbox_companies_from(index, catalog) -> list[tuple[list[str], list[str]]]:
    """Contact names and stored address Types for each counterparty."""
    from collections import defaultdict

    labels: dict[str, list[str]] = defaultdict(list)
    for cp_id, _address_id, label, _partner_id in catalog:
        if label:
            labels[cp_id].append(label)
    companies = []
    cp_ids = set(index.contacts_by_cp) | set(labels) | set(index.addresses_by_cp)
    for cp_id in cp_ids:
        names = [_text(index.contacts[contact_id], "ContactNm") for contact_id in index.contacts_by_cp.get(cp_id, [])]
        site_labels = labels.get(cp_id) or [
            _text(index.addresses[address_id], "Type") for address_id in index.addresses_by_cp.get(cp_id, [])
        ]
        companies.append((names, site_labels))
    return companies


def _location_title(row, parent_name: str) -> str:
    from ..erp import mapping

    return mapping.location_title(
        _text(row, "Type"),
        _text(row, "City"),
        _text(row, "Addr2"),
        _text(row, "Addr3"),
        parent_name,
    )


def _real_phone(value) -> str:
    from ..erp import mapping

    return mapping.real_phone(value)


def _contact_sort_key(item) -> tuple:
    """Lowest CT_ID is the original row. String order puts 182850001 before 55450001."""
    contact_id = str(item[0])
    if contact_id.isdigit():
        return (0, int(contact_id))
    return (1, contact_id)


def _person_key(name: str) -> str:
    """Identity of a person within one counterparty. First and last word."""
    from ..erp import mapping

    return mapping.person_key(name)


def _row_active(row, mapping) -> bool:
    flag = mapping.parse_bool(row.get("IsActive"))
    return True if flag is None else flag


def _keep_first(values: dict, field_name: str, value: str, report, contact_id: str) -> None:
    if not value:
        return
    current = values.get(field_name)
    if not current:
        values[field_name] = value
    elif str(current).casefold() != value.casefold():
        report.anomaly("Contact", contact_id, f"same person already has {field_name} {current!r}")


def _canonical_billing_id(pairs: list) -> str | None:
    """The company's own remit: Remit-to, then Invoice, then the first billing row."""
    from ..erp import mapping

    if not pairs:
        return None

    def rank(row) -> tuple:
        remit = 0 if mapping.parse_bool(row.get("RemitToAddress")) else 1
        invoice = 0 if mapping.parse_bool(row.get("InvoiceAddr")) else 1
        label = 0 if _text(row, "Type").upper() in {"INVOICE", "REMIT"} else 1
        return (remit, invoice, label)

    return min(pairs, key=lambda pair: rank(pair[1]))[0]


def _address_name(row, parent_name: str, address_id: str) -> str:
    """Form title for a location. Never the location short name or the street.

    The ERP shows the counterparty at the top of a location window. In the
    extract that company is ``Addr1``. ``Type`` is the location short name
    (often the street, such as ``1600 STIEVE ROAD``) and must not become
    ``res.partner.name``.
    """
    company = _text(row, "Addr1")
    if company:
        return company
    if parent_name:
        return parent_name
    return f"ERP address {address_id}"


def _partner_mobile_field(partner_model) -> str | None:
    """Name of the res.partner field that stores a mobile number, or None.

    Odoo 19 dropped `mobile` from res.partner. A deployment may restore it (an
    OCA addon, or a future plasticos module), so the field is resolved from the
    live registry instead of assumed present or assumed absent.
    """
    return "mobile" if "mobile" in partner_model._fields else None


def _contact_comment(row, keep_mobile: bool = False) -> str:
    """Preserve notes and the phone numbers that have no Odoo field.

    `PhoneOther` never had one. `PhoneMobile` joins it whenever the installed
    registry has no mobile field, so the number is retained and labelled rather
    than dropped or written over the business phone.
    """
    parts = []
    notes = _text(row, "Notes")
    if notes:
        parts.append(notes)
    if keep_mobile:
        mobile = _text(row, "PhoneMobile")
        if mobile:
            parts.append(f"Mobile: {mobile}")
    other_phone = _text(row, "PhoneOther")
    if other_phone:
        parts.append(f"Other phone: {other_phone}")
    return "\n".join(parts)


def _slug(value: str) -> str:
    return "".join(char if char.isalnum() else "_" for char in value.lower()).strip("_")
