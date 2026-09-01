"""LegacyErp -> PlasticOS historical import (one deterministic pipeline).

One-way import of the authoritative LegacyErp export tracked at
``data/legacy_erp_sm_export/`` into the current Odoo models. No UI, no wizard,
no menu, no cron, no queue, no ETL framework: a single non-interactive
entrypoint that calls already-tested source functions.

Pipeline::

    tracked LegacyErp export
        -> legacy_erp.reader          (exact-format source rows)
        -> legacy_erp.source_index    (CpID / AddressID / CT_ID / CRA_ID /
                                     BuySellNo / DetailID)
        -> legacy_erp.header_forensics(supplier / buyer / date / state)
        -> this service             (deterministic upsert into current models)

Identity is always a stable LegacyErp key resolved through ``ir.model.data``.
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

from odoo import api, models

_logger = logging.getLogger(__name__)

RES_PARTNER = "res.partner"
PLASTICOS_TRANSACTION = "plasticos.transaction"
PLASTICOS_TRANSACTION_LINE = "plasticos.transaction.line"
PARTNER_CATEGORY = "res.partner.category"

# ir.model.data namespace for LegacyErp source identity.
XMLID_MODULE = "plasticos_transaction"

# Import context: historical rows must not fire validation, mail tracking, or
# automation intended for live trades.
IMPORT_CONTEXT = {
    "import_mode": True,
    "tracking_disable": True,
    "mail_create_nolog": True,
    "mail_notrack": True,
}


class PlasticosLegacyErpImport(models.AbstractModel):
    """Deterministic, replay-safe LegacyErp historical import."""

    _name = "plasticos.legacy_erp.import"
    _description = "LegacyErp Historical Import"

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
    ) -> dict:
        """Run the complete import and return an accounting report.

        Args:
            payload_root: Override the tracked payload location. Defaults to
                ``data/legacy_erp_sm_export`` in this checkout.
            limit: Process at most this many transactions (diagnostics only).
            commit: Commit between complete transactions. Never mid-transaction.
            dry_run: Resolve and map everything, persist nothing.

        Returns:
            Per-entity created/updated/skipped counts plus every unresolved
            reference and mapping anomaly encountered.
        """
        # Lazy import: the source layer is Odoo-free and must not be imported
        # at addon load time.
        from ..legacy_erp import header_forensics, reader, source_index
        from ..legacy_erp import report as report_module

        payload = reader.load_payload(payload_root)
        index = source_index.build_source_index(payload)
        _logger.info("LegacyErp payload loaded (%s): %s", payload.kind.value, payload.row_counts())

        report = report_module.ImportReport()
        report.payload_kind = payload.kind.value
        report.source_counts = index.counts()
        for violation in index.violations:
            report.unresolved.append(violation.as_dict())

        partner_by_cp = self._import_counterparties(index, report, dry_run)
        partner_by_address = self._import_addresses(index, report, partner_by_cp, dry_run)
        self._import_contacts(index, report, partner_by_cp, partner_by_address, dry_run)

        headers = header_forensics.reconstruct_all_headers(index)
        self._import_transactions(index, headers, report, partner_by_cp, limit, commit, dry_run)

        result = report.as_dict()
        _logger.info("LegacyErp import finished: %s", result["counts"])
        return result

    # ------------------------------------------------------------------
    # Stage 1 — counterparties
    # ------------------------------------------------------------------
    def _import_counterparties(self, index, report, dry_run: bool) -> dict:
        from ..legacy_erp import mapping

        Partner = self.env[RES_PARTNER].with_context(**IMPORT_CONTEXT)
        partner_by_cp: dict[str, int] = {}

        for cp_id in index.counterparty_ids():
            row = index.counterparties[cp_id]
            name = _text(row, "CompanyNm")
            if not name:
                report.anomaly("CounterParty", cp_id, "blank CompanyNm")
                report.skip("counterparties")
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
        from ..legacy_erp import mapping

        Partner = self.env[RES_PARTNER].with_context(**IMPORT_CONTEXT)
        partner_by_address: dict[str, int] = {}

        for cp_id in sorted(index.addresses_by_cp):
            parent_id = partner_by_cp.get(cp_id)
            if not parent_id and not dry_run:
                report.unresolved_ref("Address", "parent_not_imported", cp_id, "counterparty partner was not created")
                continue

            for address_id in index.addresses_by_cp[cp_id]:
                row = index.addresses[address_id]
                kind = mapping.address_kind(row)
                # An invoice/remit address is an address, not a facility; every
                # other kind is a physical child-company location.
                is_billing = kind == "invoice"
                values = {
                    "name": _address_name(row, cp_id, address_id),
                    "parent_id": parent_id,
                    "is_company": not is_billing,
                    "type": mapping.ODOO_ADDRESS_TYPE[kind],
                }
                _set_if(values, "street", _text(row, "Addr1"))
                _set_if(values, "street2", _joined(row, ("Addr2", "Addr3")))
                _set_if(values, "city", _text(row, "City"))
                _set_if(values, "zip", _text(row, "PostalCd"))
                _set_if(values, "phone", _text(row, "Telephone") or _text(row, "MobilePhone"))
                _set_if(values, "email", _text(row, "Email") or _text(row, "BillingEmail"))

                self._resolve_country_state(values, row)

                if dry_run:
                    report.skip("locations")
                    continue

                partner = self._upsert(Partner, f"legacy_erp_address_{address_id}", values, report, "locations")
                partner_by_address[address_id] = partner.id

        return partner_by_address

    def _resolve_country_state(self, values: dict, row) -> None:
        """Resolve country/state to existing records only."""
        code = _text(row, "Country").upper()
        country = self.env["res.country"].search([("code", "=", code)], limit=1) if len(code) == 2 else None
        if country:
            values["country_id"] = country.id
            region = _text(row, "Region")
            if region:
                state = self.env["res.country.state"].search(
                    ["|", ("code", "=", region), ("name", "=", region), ("country_id", "=", country.id)],
                    limit=1,
                )
                if state:
                    values["state_id"] = state.id

    # ------------------------------------------------------------------
    # Stage 3 — contacts and contact roles
    # ------------------------------------------------------------------
    def _import_contacts(self, index, report, partner_by_cp: dict, partner_by_address: dict, dry_run: bool) -> None:
        from ..legacy_erp import mapping

        Partner = self.env[RES_PARTNER].with_context(**IMPORT_CONTEXT)
        tag_cache: dict[str, int] = {}

        for cp_id in sorted(index.contacts_by_cp):
            company_partner_id = partner_by_cp.get(cp_id)
            if not company_partner_id and not dry_run:
                report.unresolved_ref("Contact", "parent_not_imported", cp_id, "counterparty partner was not created")
                continue

            for contact_id in index.contacts_by_cp[cp_id]:
                row = index.contacts[contact_id]
                name = _text(row, "ContactNm")
                if not name:
                    report.anomaly("Contact", contact_id, "blank ContactNm")
                    report.skip("contacts")
                    continue

                # Location is the Address composite key (CpID, Type), so this is
                # an exact join, never a fuzzy text match.
                parent_id = self._contact_parent(index, row, cp_id, company_partner_id, partner_by_address)
                active = mapping.parse_bool(row.get("IsActive"))
                values = {
                    "name": name,
                    "parent_id": parent_id,
                    "is_company": False,
                    "type": "contact",
                    "active": True if active is None else active,
                }
                _set_if(values, "email", _text(row, "Email"))
                _set_if(values, "phone", _text(row, "PhoneBusiness"))
                _set_if(values, "mobile", _text(row, "PhoneMobile"))
                _set_if(values, "comment", _contact_comment(row))

                roles = self._contact_roles(index, contact_id)
                if roles:
                    values["function"] = roles[0]

                if dry_run:
                    report.skip("contacts")
                    continue

                partner = self._upsert(Partner, f"legacy_erp_contact_{contact_id}", values, report, "contacts")
                self._apply_contact_roles(partner, roles, tag_cache, report)

    def _contact_parent(
        self, index, row, cp_id: str, company_partner_id: int | None, partner_by_address: dict
    ) -> int | None:
        """Facility partner when ``Location`` names one of this CpID's addresses."""
        location = _text(row, "Location").upper()
        if location:
            for address_id in index.addresses_by_cp.get(cp_id, []):
                address_row = index.addresses[address_id]
                if _text(address_row, "Type").upper() == location:
                    resolved = partner_by_address.get(address_id)
                    if resolved:
                        return resolved
        return company_partner_id

    def _contact_roles(self, index, contact_id: str) -> list:
        """Ordered role names for a contact. ``Primary`` sorts first."""
        from ..legacy_erp import mapping

        names = []
        for role_id in index.roles_by_contact.get(contact_id, []):
            role = mapping.normalize_contact_role(index.contact_roles[role_id].get("RoleNm"))
            if role and role not in names:
                names.append(role)
        return mapping.sort_contact_roles(names)

    def _apply_contact_roles(self, partner, roles: list, tag_cache: dict, report) -> None:
        """Carry LegacyErp contact roles on the existing partner-tag mechanism.

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
        parent = self._upsert(Category, "legacy_erp_contact_role_root", {"name": "LegacyErp Contact Role"}, report, None)
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
                _logger.exception("LegacyErp transaction %s failed and was rolled back", buysell_no)
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
        # docs/legacy_erp_import_mapping.md, "Evidenced new-field candidate".
        if header.trade_date and "transaction_date" in Transaction._fields:
            values["transaction_date"] = header.trade_date

        transaction = self._upsert(
            Transaction, f"legacy_erp_transaction_{header.buysell_no}", values, report, "transactions"
        )
        self._import_lines(index, header, transaction, report)

    def _import_lines(self, index, header, transaction, report) -> None:
        from ..legacy_erp import mapping

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
        self.env["ir.model.data"].create(
            {
                "module": XMLID_MODULE,
                "name": xml_id,
                "model": model._name,
                "res_id": record.id,
                "noupdate": True,
            }
        )
        if bucket:
            report.bump(bucket, "created")
        return record


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


def _address_name(row, cp_id: str, address_id: str) -> str:
    """Human label for a location. Never used as identity."""
    for column in ("Type", "City", "Addr1"):
        value = _text(row, column)
        if value:
            return value
    return f"LegacyErp address {address_id} ({cp_id})"


def _contact_comment(row) -> str:
    """Preserve notes and the third phone number, which has no Odoo field."""
    parts = []
    notes = _text(row, "Notes")
    if notes:
        parts.append(notes)
    other_phone = _text(row, "PhoneOther")
    if other_phone:
        parts.append(f"Other phone: {other_phone}")
    return "\n".join(parts)


def _slug(value: str) -> str:
    return "".join(char if char.isalnum() else "_" for char in value.lower()).strip("_")
