"""ERP -> PlasticOS historical import (one deterministic pipeline).

One-way import of the ERP source into the current Odoo models. The source is
read through ``erp.reader``: a direct read of the restored ERP database
(ADR-021), an ``INSERT`` statement payload, or the frozen grid extract as a
regression fixture. No UI, no wizard, no menu, no cron, no queue, no ETL
framework: a single non-interactive entrypoint that calls already-tested
source functions.

Pipeline::

    ERP source (database / statements / frozen grid)
        -> erp.reader          (exact-format source rows)
        -> erp.source_index    (CpID / AddressID / CT_ID / CRA_ID /
                                     BuySellNo / DetailID)
        -> erp.header_forensics(supplier / buyer / date / state; the deal
           extension consumes this, the partner stages do not)
        -> this service             (deterministic partner upsert)

Identity is always a stable ERP key resolved through ``ir.model.data``.
Company names, e-mail addresses, phone numbers, address text, and Odoo database
ids are never identity.

Partner stages always run in this order, in a full run as well as a
partners-only run: counterparties -> addresses -> contacts -> roles ->
salespersons. An ``after_stage`` hook runs after each stage and before anything
commits, so a stage whose validator fails is rolled back by the caller and
never persists.

Deal rows are not written here. A full run hands the indexed source to the
historical-import extension, which realizes ``sale.order``, ``purchase.order``,
and ``account.move``. Partner-only and single-layer runs stay on the partner
stages.
"""

from __future__ import annotations

import logging
from html import escape

from odoo import Command, api, models
from odoo.tools import html2plaintext

from ..erp.comment_notes import comment_with_erp_notes as _comment_with_erp_notes

_logger = logging.getLogger(__name__)

RES_PARTNER = "res.partner"
PARTNER_CATEGORY = "res.partner.category"

# ir.model.data namespace for ERP source identity.
# Markers were minted under plasticos_transaction. Keep that module name so a
# re-import updates the same records instead of creating a second set.
XMLID_MODULE = "plasticos_transaction"

# Partner stages, in execution order. A full run executes every one of them
# before the historical-import extension; ``layer`` selects exactly one.
PARTNER_LAYERS = ("counterparties", "addresses", "contacts", "roles", "salesreps")
LAYER_TABLE = {
    "counterparties": "CounterParty",
    "addresses": "Address",
    "contacts": "Contact",
    "roles": "ContactRoleAssignment",
    "salesreps": "SalesReps",
}
PARTNER_COUNT_PARAM = "plasticos_partner_import.partner_count_after_contacts"
UNRESOLVED_RR_PARAM = "plasticos_partner_import.unresolved_rr"
# Every historical-import write carries this context: no chatter, no tracking,
# no business automation reacting to a bulk load.
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
        limit: int | float | None = None,
        commit: bool = False,
        dry_run: bool = False,
        partners_only: bool = False,
        layer: str | None = None,
        database=None,
        after_stage=None,
        on_payload=None,
    ) -> dict:
        """Run the import and return an accounting report.

        Args:
            payload_root: Override the payload location. Defaults to statement
                SQL in ``plasticos_partner_import/erp_extracted_data``, then
                the frozen grid pack.
            limit: Newest N worksheets, or a fraction of them (``0.25`` is the
                newest quarter), passed to the historical-import extension
                (diagnostics and test databases). Validated before anything is
                read; an invalid limit raises ``ValueError``.
            commit: Commit between complete transactions. Never mid-transaction.
                A partners-only or single-layer run commits once, after every
                stage has passed its ``after_stage`` hook.
            dry_run: Resolve and map everything, persist nothing.
            partners_only: Read and write only CounterParty, Address, Contact,
                ContactRoleAssignment, and SalesReps. Deal files are not opened.
            layer: One of ``counterparties``, ``addresses``, ``contacts``,
                ``roles``, ``salesreps``. Only that source table is read. The
                parent records are the partners already stored under their
                source keys.
            database: ``erp.reader.DatabaseSource`` for a direct read of the
                restored ERP database. Takes precedence over ``payload_root``.
            after_stage: ``callable(layer_name, payload)`` invoked after each
                partner stage that wrote (not in a dry run). Raising aborts the
                run before any commit; the caller rolls back.
            on_payload: ``callable(payload)`` invoked once the source is
                loaded and before any stage writes (not in a dry run). The
                Production permit check binds the loaded rows here; raising
                aborts the run with nothing written.

        Returns:
            Per-entity created/updated/skipped/rejected counts plus every
            unresolved reference and mapping anomaly encountered. Every source
            row receives exactly one outcome.
        """
        # Lazy import: the source layer is Odoo-free and must not be imported
        # at addon load time.
        from ..erp import reader, source_index
        from ..erp import report as report_module
        from ..erp.limits import validate_limit

        validate_limit(limit)
        if layer and layer not in PARTNER_LAYERS:
            raise ValueError(f"unknown partner layer {layer!r}")
        if layer:
            only = frozenset({LAYER_TABLE[layer]})
        elif partners_only:
            only = reader.PARTNER_SOURCE_TABLES
        elif database is not None:
            only = reader.REQUIRED_TABLES | reader.COMMERCIAL_SQL_TABLES
        else:
            only = None
        payload = reader.load_payload(payload_root, only=only, database=database)
        if on_payload is not None and not dry_run:
            on_payload(payload)
        index = source_index.build_source_index(payload)
        _logger.info("ERP payload loaded (%s from %s): %s", payload.kind.value, payload.origin, payload.row_counts())

        report = report_module.ImportReport()
        report.payload_kind = payload.kind.value
        report.source_origin = payload.origin
        report.source_counts = index.counts()
        for violation in index.violations:
            report.unresolved.append(violation.as_dict())
        source_index.account_inventory_destinations(index, report)
        source_index.account_omissions(index, report)

        def stage_done(name: str) -> None:
            if after_stage is not None and not dry_run:
                after_stage(name, payload)

        realized_downstream = False
        if layer:
            self._run_layer(layer, index, report, dry_run)
            stage_done(layer)
        else:
            partner_by_cp = self._import_counterparties(index, report, dry_run)
            stage_done("counterparties")
            self._import_addresses(index, report, partner_by_cp, dry_run)
            stage_done("addresses")
            self._import_contacts(index, report, partner_by_cp, dry_run)
            if not dry_run:
                self._stamp_partner_count()
            stage_done("contacts")
            self._import_roles(index, report, dry_run)
            stage_done("roles")
            self._import_sales_reps(index, report, dry_run)
            stage_done("salesreps")
            if not partners_only:
                realized_downstream = bool(
                    self._extend_historical_import(index, report, partner_by_cp, limit, commit, dry_run)
                )

        if commit and not dry_run and (layer or partners_only or not realized_downstream):
            # Partner stages passed their hooks. A deal extension that returns
            # true owns its own commits and must not be committed twice.
            self.env.cr.commit()
        result = report.as_dict()
        scope = f" ({layer})" if layer else " (partners only)" if partners_only else ""
        _logger.info("ERP import finished%s: %s", scope, result["counts"])
        return result

    def _extend_historical_import(self, index, report, partner_by_cp, limit, commit, dry_run) -> bool:
        """Extension point. This module does not realize records beyond partners."""
        return False

    def _run_layer(self, layer: str, index, report, dry_run: bool) -> None:
        """Execute exactly one partner stage against the partners already stored."""
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
        elif layer == "salesreps":
            self._import_sales_reps(index, report, dry_run)

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

            tags, role_anomaly = mapping.company_role_tags(row.get("Role"))
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
            if tags:
                selection, _selection_anomaly = mapping.company_role(row.get("Role"))
                values["company_role"] = selection or False
                tag_ids, missing = self._company_role_tag_ids(tags)
                if missing:
                    report.anomaly("CounterParty", cp_id, f"company role tag missing: {', '.join(missing)}")
                elif "company_role_tag_ids" in Partner._fields:
                    values["company_role_tag_ids"] = [Command.set(tag_ids)]
            _set_if(values, "ref", _text(row, "OurCustNo"))
            _set_if(values, "email", _email(row, "APEMail"))
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
        from ..erp.mapping import payment_term_name

        terms_code = payment_term_name(_text(row, "TermsCode"))
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
                        # The address folded into the company. Alias its AddressID
                        # marker to the company so the contacts stage, which rebuilds
                        # the address catalog from markers alone, and every replay
                        # resolve this AddressID to the same partner.
                        partner_by_address[address_id] = parent.id
                        self._ensure_identity_marker(Partner, f"legacy_erp_address_{address_id}", parent)
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
        fill("email", _email(row, "Email", "BillingEmail"))
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
        """Fill the company's missing phone and email from its active contacts.

        The ERP stores the number and the mailbox on the person. The company
        is who we trade with, so those values also land on the company. Each
        value is filled on its own: from the first active ``Primary`` contact
        that has it, else from the first other active contact that has it. A
        value already taken from the counterparty or the remit is left as-is.
        """
        from ..erp import mapping

        partner = self.env[RES_PARTNER].with_context(**IMPORT_CONTEXT).browse(company_partner_id)
        if partner.email and partner.phone:
            return
        primary_rows: list = []
        other_rows: list = []
        for contact_id in index.contacts_by_cp.get(cp_id, []):
            row = index.contacts[contact_id]
            if mapping.contact_exclusion(row.get("IsActive")):
                continue
            roles = [role.lower() for role in self._contact_roles(index, contact_id)]
            (primary_rows if "primary" in roles else other_rows).append(row)
        values = {}
        for row in primary_rows + other_rows:
            if not partner.email and "email" not in values and _email(row, "Email"):
                values["email"] = _email(row, "Email")
            if not partner.phone and "phone" not in values:
                number = mapping.real_phone(row.get("PhoneBusiness"))
                if number:
                    values["phone"] = number
            if (partner.email or "email" in values) and (partner.phone or "phone" in values):
                break
        if values:
            partner.write(values)

    def _address_values(self, values: dict, row) -> None:
        """ERP: Addr2 is the street, Addr3 is the second street line."""
        _set_if(values, "street", _text(row, "Addr2"))
        _set_if(values, "street2", _text(row, "Addr3"))
        _set_if(values, "city", _text(row, "City"))
        _set_if(values, "zip", _text(row, "PostalCd"))
        _set_if(values, "phone", _real_phone(row.get("Telephone")))
        _set_if(values, "email", _email(row, "Email", "BillingEmail"))
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
        number and the email land on the company. A contact whose name is a
        site mailbox lands on that location. A person partner that an earlier
        run stored for such a row is retired with its marker, so a replay
        leaves no visible duplicate. Role tags are a later layer.
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
            excluded_ids: list[str] = []
            weak_rows: list[tuple[str, dict, str]] = []
            addresses = [
                (address_id, label) for item_cp, address_id, label, _partner_id in catalog if item_cp == cp_id and label
            ]
            partner_by_address = {
                address_id: partner_id for item_cp, address_id, _label, partner_id in catalog if item_cp == cp_id
            }
            for contact_id in index.contacts_by_cp[cp_id]:
                row = index.contacts[contact_id]
                excluded = mapping.contact_exclusion(row.get("IsActive"))
                if excluded:
                    # Before grouping, channel writes and aliasing: an inactive
                    # CT_ID gets no person, no number on the company and no marker.
                    index.omitted_contact_ids.add(contact_id)
                    report.skip("contacts")
                    excluded_ids.append(contact_id)
                    continue
                name = _text(row, "ContactNm")
                if not name:
                    # A blank title may still be a known person's row (R2).
                    # It is rejected only when it does not fold.
                    weak_rows.append((contact_id, row, mapping.WEAK_BLANK))
                    continue
                if not mapping.is_person_name(name):
                    index.omitted_contact_ids.add(contact_id)
                    retired = False
                    if not dry_run and company_partner_id:
                        self._apply_non_person(Partner.browse(company_partner_id), row)
                        retired = self._retire_stale_contact(Partner, contact_id)
                    report.bump("contacts", "updated" if retired else "skipped")
                    continue
                target = mapping.site_mailbox_target(name, addresses, _text(row, "Location"), mailbox_keys)
                if target:
                    index.omitted_contact_ids.add(contact_id)
                    retired = False
                    if not dry_run:
                        self._apply_site_mailbox(partner_by_address, target, row)
                        retired = self._retire_stale_contact(Partner, contact_id)
                    report.bump("contacts", "updated" if retired else "skipped")
                    continue
                kind = mapping.weak_name_kind(name, _row_emails(row))
                if kind:
                    weak_rows.append((contact_id, row, kind))
                    continue
                key = mapping.person_key(name)
                if key not in groups:
                    order.append(key)
                    groups[key] = []
                groups[key].append((contact_id, row))

            folded, unfolded = _fold_weak_rows(groups, order, weak_rows, report)
            display_names: dict[str, str] = {}
            for contact_id, row, kind in unfolded:
                name = _text(row, "ContactNm")
                if kind == mapping.WEAK_BLANK:
                    report.anomaly("Contact", contact_id, "blank ContactNm")
                    report.reject("contacts")
                    continue
                key = mapping.person_key(name)
                if key not in groups:
                    order.append(key)
                    groups[key] = []
                    if kind == mapping.WEAK_EMAIL_PREFIX:
                        display_names[key] = mapping.email_prefix_title(name)
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
                    folded=folded.get(key, ()),
                    name=display_names.get(key),
                )
            if excluded_ids and not dry_run:
                self._retire_inactive_contacts(Partner, excluded_ids)

    def _retire_inactive_contacts(self, partner_model, contact_ids: list[str]) -> None:
        """Remove the marker an earlier run stored for each excluded CT_ID.

        Runs after the active people of the counterparty are stored. The person
        a removed marker named is archived (never deleted) only when no other
        ERP contact marker still points at it, so an active alias keeps its
        person and an approved CRM binding to an excluded CT_ID no longer resolves.
        """
        Data = self.env["ir.model.data"]
        stale = Data.search(
            [
                ("module", "=", XMLID_MODULE),
                ("name", "in", [f"legacy_erp_contact_{contact_id}" for contact_id in contact_ids]),
                ("model", "=", RES_PARTNER),
            ]
        )
        if not stale:
            return
        affected = {row.res_id for row in stale if row.res_id}
        stale.unlink()
        if not affected:
            return
        still_named = Data.search(
            [
                ("module", "=", XMLID_MODULE),
                ("name", "=like", "legacy_erp_contact_%"),
                ("model", "=", RES_PARTNER),
                ("res_id", "in", sorted(affected)),
            ]
        )
        orphans = sorted(affected - {row.res_id for row in still_named})
        people = (
            partner_model.browse(orphans).exists().filtered(lambda partner: not partner.is_company and partner.active)
        )
        if people:
            people.write({"active": False})

    def _import_person(
        self,
        partner_model,
        members,
        company_partner_id,
        label_to_partner,
        report,
        dry_run,
        mapping,
        folded=(),
        name: str | None = None,
    ) -> None:
        """One person per company plus first and last name. Every CT_ID aliases that person.

        ``members`` holds explicitly active rows only; ``_import_contacts``
        excluded every other row before grouping. ``folded`` holds weak-name
        rows of the same company that resolved to this person (R2): they alias
        it, add their channels, sites and roles, but never supply the name or
        the anchor. ``name`` overrides the title (an unfolded e-mail prefix).
        """
        own = sorted(members, key=_contact_sort_key)
        members = own + sorted(folded, key=_contact_sort_key)
        name = name or _text(own[0][1], "ContactNm")
        parent = partner_model.browse(company_partner_id) if company_partner_id else partner_model.browse()
        values = {
            "name": name,
            "parent_id": company_partner_id,
            "is_company": False,
            "type": "contact",
            "active": True,
        }
        values.update(self._copied_role(parent))
        phone_lines, email_evidence = self._merge_person_channels(values, members, report)
        location_ids = []
        for _contact_id, row in members:
            loc = _text(row, "Location")
            partner_id = label_to_partner.get(loc)
            if partner_id and partner_id != company_partner_id and partner_id not in location_ids:
                location_ids.append(partner_id)

        if dry_run:
            report.skip("contacts", len(members))
            return

        anchor = self._anchor_contact_id(partner_model, own)
        partner = self._upsert(partner_model, f"legacy_erp_contact_{anchor}", values, report, "contacts")
        for contact_id, _row in members:
            if contact_id == anchor:
                continue
            self._alias_xmlid(partner_model, f"legacy_erp_contact_{contact_id}", partner, report, "contacts")
        if "location_partner_ids" in partner._fields and set(partner.location_partner_ids.ids) != set(location_ids):
            partner.write({"location_partner_ids": [(6, 0, location_ids)]})
        self._sync_phone_lines(partner, phone_lines)
        self._append_comment_evidence(partner, email_evidence)

    def _append_comment_evidence(self, partner, lines: list) -> None:
        """Append each labelled line to ``comment`` as its own paragraph, once.

        A paragraph already present is not written again, so a replay changes
        nothing. The ERP notes and any CRM paragraphs stay where they are.
        """
        comment = partner.comment
        wrote = False
        for line in lines:
            merged = _comment_with_paragraph(comment, line)
            if merged is not None:
                comment = merged
                wrote = True
        if wrote:
            partner.with_context(**IMPORT_CONTEXT).write({"comment": comment})

    def _merge_person_channels(self, values: dict, members, report) -> tuple[list, list]:
        """Union emails and phones. The first business number stays in ``phone``.

        The first email stays in ``email``. A different email from another
        active CT_ID of the same person is returned as labelled comment
        evidence; res.partner has one email field. Returns ``(lines, evidence)``.
        """
        from ..erp import mapping

        comments: list[str] = []
        business: list[str] = []
        lines: list[tuple[str, str]] = []
        evidence: list[str] = []
        seen_emails: set[str] = set()
        for contact_id, row in members:
            email = _email(row, "Email")
            _keep_first(values, "email", email, report, contact_id)
            seen_emails.add(str(values.get("email") or "").casefold())
            if email and email.casefold() not in seen_emails:
                seen_emails.add(email.casefold())
                evidence.append(f"ERP contact {contact_id} email: {email}")
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
        return lines, evidence

    def _apply_non_person(self, company, row) -> None:
        """A phone-number contact title is not a person. Keep the channels on the company."""
        from ..erp import mapping

        values = {}
        if not company.phone:
            number = mapping.real_phone(row.get("PhoneBusiness"))
            if number:
                values["phone"] = number
        if not company.email and _email(row, "Email"):
            values["email"] = _email(row, "Email")
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

    def _retire_stale_contact(self, partner_model, contact_id: str) -> bool:
        """Retire the person an earlier run stored for a row that is not a person.

        The row's identity marker is removed and the partner it pointed at is
        archived (never deleted: references stay valid). True when something
        was retired.
        """
        data = self.env["ir.model.data"].search(
            [
                ("module", "=", XMLID_MODULE),
                ("name", "=", f"legacy_erp_contact_{contact_id}"),
                ("model", "=", RES_PARTNER),
            ],
            limit=1,
        )
        if not data:
            return False
        partner = partner_model.browse(data.res_id).exists() if data.res_id else partner_model.browse()
        if partner and not partner.is_company and partner.active:
            partner.write({"active": False})
        data.unlink()
        return True

    def _import_roles(self, index, report, dry_run: bool) -> None:
        """Tag the person already stored for each CT_ID. Create no partner.

        Every ContactRoleAssignment row receives exactly one outcome: created
        when it is the row that puts a new tag on the person, skipped when the
        tag is already there (or repeated by another row), rejected when the
        role word is blank or unmapped, unresolved when no person exists for
        its CT_ID or the word is the unresolvable ``RR``.
        """
        from ..erp import mapping

        Partner = self.env[RES_PARTNER].with_context(**IMPORT_CONTEXT, active_test=False)
        tag_cache: dict[str, int] = {}
        grouped: dict[int, dict] = {}
        unresolved_rr: list[str] = []
        for contact_id in sorted(index.roles_by_contact):
            if contact_id in index.omitted_contact_ids:
                report.skip("contact_roles", len(index.roles_by_contact[contact_id]))
                continue
            partner = self._partner_by_xmlid(Partner, f"legacy_erp_contact_{contact_id}")
            for role_id in index.roles_by_contact[contact_id]:
                row = index.contact_roles[role_id]
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
                    report.unresolved_ref("ContactRoleAssignment", "unresolved_rr", role_id, f"CT_ID={contact_id} RR")
                    continue
                if not tag:
                    report.anomaly("ContactRoleAssignment", role_id, f"unmapped role {row.get('RoleNm')!r}")
                    report.reject("contact_roles")
                    continue
                bucket = grouped.setdefault(partner.id, {"partner": partner, "rows": []})
                bucket["rows"].append((role_id, tag))
        if dry_run:
            for bucket in grouped.values():
                report.skip("contact_roles", len(bucket["rows"]))
            return
        self.env["ir.config_parameter"].set_param(UNRESOLVED_RR_PARAM, ",".join(sorted(set(unresolved_rr))))
        for bucket in grouped.values():
            partner = bucket["partner"]
            tags = self._apply_contact_roles(partner, bucket["rows"], tag_cache, report)
            job = mapping.job_position(tags)
            if job and partner.function != job:
                partner.write({"function": job})

    def _user_ids_by_name(self, names: set[str]) -> dict[str, int | None]:
        """One query for the named users. A name with two users maps to None.

        Worksheet commission history still matches the stored recipient by
        display name. Partner Salesperson uses :meth:`_user_ids_by_login`.
        """
        if not names:
            return {}
        users = self.env["res.users"].search([("name", "in", sorted(names))])
        found: dict[str, list[int]] = {}
        for user in users:
            found.setdefault(user.name, []).append(user.id)
        return {name: ids[0] if len(ids) == 1 else None for name, ids in found.items()}

    def _user_ids_by_login(self, logins: set[str]) -> dict[str, int | None]:
        """One query for the logins. A login that is not exactly one user maps to None."""
        wanted = sorted({login.casefold() for login in logins if login})
        if not wanted:
            return {}
        domain: list = [("login", "=ilike", wanted[0])]
        if len(wanted) > 1:
            domain = ["|"] * (len(wanted) - 1) + [("login", "=ilike", login) for login in wanted]
        users = self.env["res.users"].search(domain)
        found: dict[str, list[int]] = {}
        allowed = set(wanted)
        for user in users:
            key = (user.login or "").casefold()
            if key in allowed:
                found.setdefault(key, []).append(user.id)
        return {login: ids[0] if len(ids) == 1 else None for login, ids in found.items()}

    def _import_sales_reps(self, index, report, dry_run: bool) -> None:
        """Set each company's Salesperson from its assigned rep. Create no user.

        A unique ``IsDefault=1`` row wins. When none is marked default, the
        sole assigned rep is written, including an ``IsDefault=0`` row. The
        rep is matched to an existing ``res.users`` record by login. A company
        whose rows do not resolve to one rep is left unchanged: this pass
        does not clear ``user_id``. Every SalesReps row receives one outcome:
        the row that decides the Salesperson carries the write outcome, the
        other rows of that company are skipped, and a company whose rows
        cannot be resolved rejects or leaves unresolved each of its rows.
        """
        from ..erp import mapping

        Partner = self.env[RES_PARTNER].with_context(**IMPORT_CONTEXT, active_test=False)
        chosen: list[tuple[str, list, str, object]] = []
        for cp_id in sorted(index.sales_reps_by_cp):
            rows = index.sales_reps_by_cp[cp_id]
            company = self._partner_by_xmlid(Partner, f"legacy_erp_cp_{cp_id}")
            if not company:
                for row in rows:
                    report.unresolved_ref(
                        "SalesReps",
                        "unresolved_counterparty",
                        _sales_rep_row_key(cp_id, row),
                        f"CpID={cp_id} has no company",
                    )
                continue
            code, anomaly = mapping.default_sales_rep(rows)
            if anomaly:
                report.anomaly("SalesReps", cp_id, anomaly)
                report.reject("salespersons", len(rows))
                continue
            if not code:
                # Rows exist, but none names a representative. Leave user_id.
                report.skip("salespersons", len(rows))
                continue
            login = mapping.sales_rep_login(code)
            if not login:
                report.anomaly("SalesReps", cp_id, f"unknown rep initials {code!r}")
                report.reject("salespersons", len(rows))
                continue
            chosen.append((cp_id, rows, login, company))
        user_by_login = self._user_ids_by_login({login for _cp_id, _rows, login, _company in chosen})
        for cp_id, rows, login, company in chosen:
            user_id = user_by_login.get(login.casefold())
            if not user_id:
                for row in rows:
                    report.unresolved_ref(
                        "SalesReps",
                        "unresolved_user",
                        _sales_rep_row_key(cp_id, row),
                        f"no single Odoo user with login {login!r}",
                    )
                continue
            if dry_run or company.user_id.id == user_id:
                report.skip("salespersons", len(rows))
                continue
            company.write({"user_id": user_id})
            report.bump("salespersons", "updated")
            report.skip("salespersons", len(rows) - 1)

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
        # Direct SQL justification: whole-table count after a bulk load, archived rows included.
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
        """Point another CT_ID at the one person. Does not create a second partner.

        When the CT_ID already pointed at a different partner (an earlier run
        stored that row as its own person), that partner is retired: its extra
        numbers move to the one person and it is archived, so no visible
        duplicate remains and the marker now resolves deterministically.
        """
        data = self.env["ir.model.data"].search(
            [("module", "=", XMLID_MODULE), ("name", "=", xml_id), ("model", "=", model._name)],
            limit=1,
        )
        if data and data.res_id == record.id:
            report.bump(bucket, "skipped")
            return
        if data:
            superseded = model.browse(data.res_id).exists() if data.res_id else model.browse()
            data.write({"res_id": record.id, "model": model._name})
            self._retire_superseded_partner(superseded, record)
            report.bump(bucket, "updated")
            return
        self._write_identity_marker(model, xml_id, record)
        report.bump(bucket, "skipped")

    def _retire_superseded_partner(self, superseded, record) -> None:
        """Archive a person partner that the identity migration folded into ``record``.

        Its extra numbers move to ``record``. It is archived (never deleted)
        only once no ERP contact marker still points at it, so a partner that
        another CT_ID still names stays visible until that CT_ID moves too.
        """
        if not superseded or superseded.id == record.id or superseded.is_company:
            return
        if "phone_line_ids" in superseded._fields:
            self._sync_phone_lines(record, [(line.label, line.number) for line in superseded.phone_line_ids])
        if superseded.active and not self._named_by_contact_marker(superseded.id):
            superseded.write({"active": False})

    def _named_by_contact_marker(self, partner_id: int) -> bool:
        """True while any ``legacy_erp_contact_%`` marker still points at ``partner_id``."""
        marker = self.env["ir.model.data"].search(
            [
                ("module", "=", XMLID_MODULE),
                ("name", "=like", "legacy_erp_contact_%"),
                ("model", "=", RES_PARTNER),
                ("res_id", "=", partner_id),
            ],
            limit=1,
        )
        return bool(marker)

    def _contact_roles(self, index, contact_id: str) -> list:
        """Ordered role names for a contact. ``Primary`` sorts first."""
        from ..erp import mapping

        names = []
        for role_id in index.roles_by_contact.get(contact_id, []):
            role = mapping.normalize_contact_role(index.contact_roles[role_id].get("RoleNm"))
            if role and role not in names:
                names.append(role)
        return mapping.sort_contact_roles(names)

    def _apply_contact_roles(self, partner, rows: list, tag_cache: dict, report) -> list:
        """Carry ERP contact roles on the existing partner-tag mechanism.

        ``res.partner.category`` is the repository's multi-valued partner
        classification. Tag membership is set semantics, so replaying an
        assignment is inherently idempotent — which is what ``CRA_ID``
        replay-safety requires. No roles subsystem is introduced.

        ``rows`` is ``[(role_id, tag), ...]`` for one person. One database
        write adds every missing tag; the accounting still credits each row:
        the first row carrying a newly added tag is ``created``, every other
        row is ``skipped``. Returns the ordered distinct tags.
        """
        tags: list[str] = []
        for _role_id, tag in rows:
            if tag not in tags:
                tags.append(tag)
        if not tags:
            return tags
        tag_ids = {tag: self._role_tag_id(tag, tag_cache, report) for tag in tags}
        existing = set(partner.category_id.ids)
        missing = [tag_ids[tag] for tag in tags if tag_ids[tag] and tag_ids[tag] not in existing]
        if missing:
            partner.write({"category_id": [(4, tag_id) for tag_id in missing]})
        added = set(missing)
        credited: set[str] = set()
        for _role_id, tag in rows:
            tag_id = tag_ids.get(tag)
            if tag_id and tag_id in added and tag not in credited:
                credited.add(tag)
                report.bump("contact_roles", "created")
            else:
                report.bump("contact_roles", "skipped")
        return tags

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
                if model._name == RES_PARTNER and "comment" in values:
                    values = dict(values)
                    comment = _comment_with_erp_notes(record.comment, values.pop("comment"))
                    if comment is not None:
                        values["comment"] = comment
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

    def _ensure_identity_marker(self, model, xml_id: str, record) -> None:
        """Bind ``xml_id`` to ``record`` unless the marker already names a live record.

        An existing marker is kept, so an address that an earlier run stored as
        its own location partner keeps that identity; only an unmarked
        AddressID is aliased.
        """
        data = self.env["ir.model.data"].search(
            [("module", "=", XMLID_MODULE), ("name", "=", xml_id), ("model", "=", model._name)],
            limit=1,
        )
        if data and data.res_id and model.browse(data.res_id).exists():
            return
        if data:
            data.unlink()
        self._write_identity_marker(model, xml_id, record)

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

    def _company_role_tag_ids(self, tags: tuple[str, ...]) -> tuple[list[int], list[str]]:
        """Resolve role tag keys to records. A missing tag is named, not skipped silently."""
        from ..erp import mapping

        found: list[int] = []
        missing: list[str] = []
        for key in tags:
            record = self.env.ref(mapping.COMPANY_ROLE_TAG_XMLID[key], raise_if_not_found=False)
            if record:
                found.append(record.id)
            else:
                missing.append(key)
        return found, missing

    def _copied_role(self, parent) -> dict:
        """The child's Company Role, role tags, and ranks are the parent's."""
        if not parent:
            return {}
        values = {
            "supplier_rank": parent.supplier_rank or 0,
            "customer_rank": parent.customer_rank or 0,
        }
        fields_on_parent = getattr(parent, "_fields", {})
        if parent.company_role:
            values["company_role"] = parent.company_role
        elif "company_role" in fields_on_parent:
            values["company_role"] = False
        if "company_role_tag_ids" in fields_on_parent:
            values["company_role_tag_ids"] = [Command.set(list(parent.company_role_tag_ids.ids))]
        return values

    def _apply_site_mailbox(self, partner_by_address: dict, address_id: str, row) -> None:
        """Put a site mailbox on the location when that location has no email yet."""
        partner_id = partner_by_address.get(address_id)
        if not partner_id:
            return
        partner = self.env[RES_PARTNER].with_context(**IMPORT_CONTEXT).browse(partner_id)
        email = _email(row, "Email").split(",")[0].strip()
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


def _email(row, *columns: str) -> str:
    """The first non-empty e-mail cell among ``columns``, cleaned.

    The brokerage's own mailboxes are dropped (``mapping.external_emails``),
    then the entries are split, shape-checked, lower-cased, de-duplicated and
    joined with ``", "`` (``mapping.email_cell``). Every importer email write
    goes through here.
    """
    from ..erp import mapping

    for column in columns:
        value = mapping.email_cell(_text(row, column))
        if value:
            return value
    return ""


def _row_emails(row) -> list[str]:
    """The cleaned addresses of a contact row's ``Email`` cell."""
    value = _email(row, "Email")
    return value.split(", ") if value else []


def _fold_weak_rows(groups: dict, order: list, weak_rows: list, report) -> tuple[dict, list]:
    """Resolve each weak-name contact row of one company to at most one full-name person.

    R2: a weak row folds into the full-name group whose phone digits
    (``PhoneBusiness`` / ``PhoneMobile``) or external email match it, when
    exactly one group matches. A plain first name is only checked against the
    groups whose first word is that name. R3: phone to one group and email to
    another is a conflict; zero or several groups are ambiguous. Neither folds.

    Returns ``(folded, unfolded)``: ``folded`` maps a group key to its extra
    ``(contact_id, row)`` members; ``unfolded`` keeps ``(contact_id, row, kind)``.
    """
    from ..erp import mapping

    by_phone: dict[str, set[str]] = {}
    by_email: dict[str, set[str]] = {}
    first_word: dict[str, str] = {}
    for key in order:
        members = groups[key]
        first_word[key] = mapping.first_word_key(_text(sorted(members, key=_contact_sort_key)[0][1], "ContactNm"))
        for _contact_id, row in members:
            for digits in _row_phone_digits(row):
                by_phone.setdefault(digits, set()).add(key)
            for address in _row_emails(row):
                by_email.setdefault(address, set()).add(key)

    folded: dict[str, list] = {}
    unfolded: list = []
    for contact_id, row, kind in weak_rows:
        allowed = set(order)
        if kind == mapping.WEAK_FIRST_NAME:
            wanted = mapping.first_word_key(_text(row, "ContactNm"))
            allowed = {key for key in order if first_word[key] == wanted}
        phone_hits = set().union(*(by_phone.get(d, set()) for d in _row_phone_digits(row))) & allowed
        email_hits = set().union(*(by_email.get(a, set()) for a in _row_emails(row))) & allowed
        if phone_hits and email_hits and phone_hits.isdisjoint(email_hits):
            report.anomaly("Contact", contact_id, "alias conflict: phone and email name different people")
            unfolded.append((contact_id, row, kind))
            continue
        candidates = phone_hits | email_hits
        if len(candidates) != 1:
            report.anomaly("Contact", contact_id, f"alias ambiguous: {len(candidates)} full-name candidates")
            unfolded.append((contact_id, row, kind))
            continue
        folded.setdefault(next(iter(candidates)), []).append((contact_id, row))
    return folded, unfolded


def _row_phone_digits(row) -> list[str]:
    from ..erp import mapping

    found = []
    for column in ("PhoneBusiness", "PhoneMobile"):
        digits = mapping.phone_digits(row.get(column))
        if digits and digits not in found:
            found.append(digits)
    return found


def _sales_rep_row_key(cp_id: str, row) -> str:
    return f"{cp_id}/{_text(row, 'ReferrerNo')}"


def _joined(row, columns) -> str:
    return ", ".join(part for part in (_text(row, c) for c in columns) if part)


def _set_if(values: dict, key: str, value) -> None:
    if value:
        values[key] = value


def _differs(record, field_name: str, value) -> bool:
    """True when writing ``value`` would actually change ``record``.

    Odoo normalizes some values on write: an Html field wraps plain text in a
    paragraph and ``website`` gains its scheme. Those are compared on their
    normalized form, so a replay of unchanged source rows writes nothing.
    """
    if field_name not in record._fields:
        return False
    field = record._fields[field_name]
    current = record[field_name]
    target = value if value is not None else False
    if field.type in ("many2many", "one2many"):
        set_command = getattr(Command, "SET", 6)
        if isinstance(target, list) and len(target) == 1 and target[0][0] == set_command:
            current_ids = set(current.ids) if current else set()
            return current_ids != set(target[0][2])
        # The import writes relational lines as a clear command; an empty relation is already clear.
        return not (isinstance(target, list) and target == [Command.clear()] and not current)
    if hasattr(current, "id"):
        current = current.id or False
    if field.type == "html":
        return _plain_text(current) != _plain_text(target)
    if field.type in ("date", "datetime") and current and isinstance(target, str):
        parsed = field.to_date(target) if field.type == "date" else field.to_datetime(target)
        return current != parsed
    if field.type in ("float", "monetary") and isinstance(target, (int, float)):
        digits = field.get_digits(record.env) if field.type == "float" else None
        precision = digits[1] if digits else 2
        return round(float(current or 0.0), precision) != round(float(target), precision)
    if field_name == "website" and isinstance(current, str) and isinstance(target, str):
        return _bare_url(current) != _bare_url(target)
    return current != target


def _plain_text(value) -> str:
    """Html field content as the text the source carried."""
    if not value:
        return ""
    return html2plaintext(str(value)).strip()


def _bare_url(value: str) -> str:
    """A website without the scheme Odoo adds on write, for change detection only."""
    text = (value or "").strip().casefold()
    for scheme in ("https://", "http://"):
        if text.startswith(scheme):
            text = text[len(scheme) :]
    return text.rstrip("/")


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


def _comment_with_paragraph(comment, line: str):
    """``comment`` with ``line`` appended as its own paragraph. ``None`` means no write.

    A paragraph holding the same text, whitespace collapsed, is already there.
    """
    from ..erp.comment_notes import _CommentBlocks

    text = " ".join((line or "").split())
    if not text:
        return None
    parser = _CommentBlocks()
    parser.feed(str(comment or ""))
    parser.close()
    parser.flush()
    if text in parser.blocks:
        return None
    if comment and not str(comment).lstrip().startswith("<"):
        comment = f"<p>{escape(str(comment), quote=False)}</p>"
    return f"{comment or ''}<p>{escape(line.strip(), quote=False)}</p>"


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
