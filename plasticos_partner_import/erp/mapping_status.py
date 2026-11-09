"""Machine-readable field-mapping status for the ERP source payload.

Encodes the disposition of every source column of the tracked export
(``plasticos_partner_import/erp_extracted_data``) and emits the mapping-status table consumed by
the canonical import command, the completeness test, and operator evidence.

The dispositions below are verified against the mapping authority
``docs/erp_import_mapping.md`` (identity contract, header
reconstruction, CounterParty/Address/Contact/WKSDetail mappings, drop
decisions with measured evidence) and against the Odoo model schema as the
import service probes it at runtime. Status vocabulary:

* ``VERIFIED`` — mapped to a real Odoo field (or a proven identity/reference
  role) and exercised by the service.
* ``NEEDS_CORRECTION`` — mapped, but the current mapping is known to be
  insufficient or wrong; must be fixed before acceptance.
* ``UNMAPPED_INTENTIONALLY`` — deliberately not imported; the reason field
  carries the measured justification. Never a silent discard.
* ``UNKNOWN`` — no disposition could be established. The completeness test
  fails on any column in this state for a consumed table.

Odoo-free on purpose: this module is exercised by the pure-Python CI tier.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path

from .reader import SOURCE_TABLES, payload_root

ALLOWED_STATUSES = frozenset({"VERIFIED", "NEEDS_CORRECTION", "UNMAPPED_INTENTIONALLY", "UNKNOWN"})

VERIFIED = "VERIFIED"
UNMAPPED = "UNMAPPED_INTENTIONALLY"
NEEDS_CORRECTION = "NEEDS_CORRECTION"
# The service does not write these yet. The names are the native fields.
NATIVE_PENDING = "Native target from the field matrix. The import service does not write it yet."
OMITTED_NO_NATIVE = "Authorized omission. No native field; do not create one."
QUICKBOOKS_OWNS = "QuickBooks owns settlement. Do not write account.payment."
# PayablesBatch header columns 25_payablesbatch.sql projects. None is written to Odoo.
SOURCE_CONTROL = "Source control. Read by source_index.payables_batch_census; no Odoo field is written from it."
READ_NOT_WRITTEN = "Read but not yet written. Projected by 25_payablesbatch.sql; no Odoo field is written from it."
UNRESOLVED_TARGET = (
    "Unresolved target. Bills stay one per PayableID (operator decision 2026-10-24); "
    "no Odoo field is written from this header column."
)
NOT_PROJECTED = "Not projected by 25_payablesbatch.sql."

# Tables tracked in the export but not consumed by the importer: their columns
# stay UNMAPPED_INTENTIONALLY with the table-level reason below.
UNCONSUMED_TABLES: dict[str, str] = {
    "UACashLedger": "cash-ledger evidence only; no Odoo target field and no business requirement identified",
    "WksDocument": "document-registry evidence only; document files are not carried by the export",
}

# Direct-SQL tables outside the grid set whose columns carry per-column
# dispositions. Their column inventory is the frozen extract header.
DIRECT_SQL_DISPOSITION_TABLES: tuple[str, ...] = ("PayablesBatch",)

# Consumed-table dispositions: table -> column -> disposition record.
# identity_role marks the source-native reconciliation identity columns.
# required marks columns the importer requires for a complete import.
DISPOSITIONS: dict[str, dict[str, dict]] = {
    "CounterParty": {
        "CpID": {
            "status": VERIFIED,
            "target_model": "ir.model.data",
            "target_field": "legacy_erp_cp_<CpID>",
            "transformation": "XML-ID key",
            "required": True,
            "null_behavior": "blank raises (source_index PRIMARY_KEYS)",
            "identity_role": "counterparty identity",
        },
        "CompanyNm": {
            "status": VERIFIED,
            "target_model": "res.partner",
            "target_field": "name",
            "transformation": "strip; blank -> anomaly + reject",
            "required": True,
            "null_behavior": "blank -> anomaly, row rejected (counted in records_rejected)",
            "identity_role": "none",
        },
        "Role": {
            "status": VERIFIED,
            "target_model": "res.partner",
            "target_field": "company_role_tag_ids, company_role, supplier_rank, customer_rank",
            "transformation": "COMPANY_ROLE_TAGS_BY_ERP_ROLE; Service only beside Buyer or Supplier; Expense alone stays Carrier",
            "required": False,
            "null_behavior": "blank -> anomaly, ranks default (0,0)",
            "identity_role": "none",
        },
        "ActiveStatus": {
            "status": VERIFIED,
            "target_model": "res.partner",
            "target_field": "active, entity_status",
            "transformation": "!= 'I'",
            "required": False,
            "null_behavior": "blank -> treated active",
            "identity_role": "none",
        },
        "OurCustNo": {
            "status": VERIFIED,
            "target_model": "res.partner",
            "target_field": "ref",
            "transformation": "direct",
            "required": False,
            "null_behavior": "blank -> unset",
            "identity_role": "none",
        },
        "APEMail": {
            "status": VERIFIED,
            "target_model": "res.partner",
            "target_field": "email",
            "transformation": "direct",
            "required": False,
            "null_behavior": "blank -> unset",
            "identity_role": "none",
        },
        "WebSite": {
            "status": VERIFIED,
            "target_model": "res.partner",
            "target_field": "website",
            "transformation": "direct",
            "required": False,
            "null_behavior": "blank -> unset",
            "identity_role": "none",
        },
        "CreditLimit": {
            "status": VERIFIED,
            "target_model": "res.partner",
            "target_field": "credit_limit",
            "transformation": "parse_decimal; field probed at runtime",
            "required": False,
            "null_behavior": "blank/unparseable -> unset",
            "identity_role": "none",
        },
        "TermsCode": {
            "status": VERIFIED,
            "target_model": "account.payment.term",
            "target_field": "property_supplier_payment_term_id",
            "transformation": "lookup by name; never created",
            "required": False,
            "null_behavior": "blank -> unset; no match -> anomaly",
            "identity_role": "none",
        },
        "IndustryNm": {
            "status": VERIFIED,
            "target_model": "res.partner.industry",
            "target_field": "industry_id",
            "transformation": "lookup by name; never created",
            "required": False,
            "null_behavior": "blank -> unset; no match -> anomaly",
            "identity_role": "none",
        },
        "MasterAccountID": {
            "status": UNMAPPED,
            "reason": "0 of 1290 populated; no hierarchy exists to import",
            "identity_role": "none",
        },
        "CustSvcRep": {
            "status": UNMAPPED,
            "reason": "1289 of 1290 NULL (single value 'IB') — no signal",
            "identity_role": "none",
        },
        "PaymentDays": {"status": UNMAPPED, "reason": "1279 zero, 11 NULL — no signal", "identity_role": "none"},
        "OnHold": {"status": UNMAPPED, "reason": "1287 blank, 2 NULL, 1 'N' — no signal", "identity_role": "none"},
        "CurrCode": {
            "status": UNMAPPED,
            "reason": "1289 USD, 1 EUR — single-currency payload",
            "identity_role": "none",
        },
        "Terms": {
            "status": UNMAPPED,
            "reason": "free-text twin of TermsCode, which is mapped",
            "identity_role": "none",
        },
        "CpLastEdit": {
            "status": UNMAPPED,
            "reason": "source audit metadata; Odoo keeps its own write_date",
            "identity_role": "none",
        },
    },
    "Address": {
        "AddressID": {
            "status": VERIFIED,
            "target_model": "ir.model.data",
            "target_field": "legacy_erp_address_<AddressID>",
            "transformation": "XML-ID key for a child location. The company's own remit has no child partner",
            "required": True,
            "null_behavior": "blank raises (source_index PRIMARY_KEYS)",
            "identity_role": "address identity",
        },
        "CpID": {
            "status": VERIFIED,
            "target_model": "res.partner",
            "target_field": "parent_id",
            "transformation": "source-key join only (never by name)",
            "required": True,
            "null_behavior": "unresolved -> IdentityViolation",
            "identity_role": "parent link",
        },
        "Type": {
            "status": VERIFIED,
            "target_model": "res.partner",
            "target_field": "type",
            "transformation": "PRIMARY is invoice; a place name is delivery; kind words are not the title",
            "required": False,
            "null_behavior": "blank or unrecognised -> delivery, label preserved",
            "identity_role": "none",
        },
        "Addr1": {
            "status": VERIFIED,
            "target_model": "res.partner",
            "target_field": "name",
            "transformation": "location company; form title. Falls back to the parent counterparty name",
            "required": False,
            "null_behavior": "blank -> unset",
            "identity_role": "none",
        },
        "Addr2": {
            "status": VERIFIED,
            "target_model": "res.partner",
            "target_field": "street",
            "transformation": "facility or remit street. Not the location short name",
            "required": False,
            "null_behavior": "blank -> unset",
            "identity_role": "none",
        },
        "Addr3": {
            "status": VERIFIED,
            "target_model": "res.partner",
            "target_field": "street2",
            "transformation": "second street line",
            "required": False,
            "null_behavior": "blank -> unset",
            "identity_role": "none",
        },
        "City": {
            "status": VERIFIED,
            "target_model": "res.partner",
            "target_field": "city",
            "transformation": "direct",
            "required": False,
            "null_behavior": "blank -> unset",
            "identity_role": "none",
        },
        "Region": {
            "status": VERIFIED,
            "target_model": "res.country.state",
            "target_field": "state_id",
            "transformation": "lookup by code/name in country; never created",
            "required": False,
            "null_behavior": "blank/no match -> unset",
            "identity_role": "none",
        },
        "PostalCd": {
            "status": VERIFIED,
            "target_model": "res.partner",
            "target_field": "zip",
            "transformation": "direct",
            "required": False,
            "null_behavior": "blank -> unset",
            "identity_role": "none",
        },
        "Country": {
            "status": VERIFIED,
            "target_model": "res.country",
            "target_field": "country_id",
            "transformation": "lookup by 2-letter code; never created",
            "required": False,
            "null_behavior": "blank/no match -> unset",
            "identity_role": "none",
        },
        "Telephone": {
            "status": VERIFIED,
            "target_model": "res.partner",
            "target_field": "phone",
            "transformation": "Telephone else MobilePhone",
            "required": False,
            "null_behavior": "both blank -> unset",
            "identity_role": "none",
        },
        "MobilePhone": {
            "status": VERIFIED,
            "target_model": "res.partner",
            "target_field": "phone",
            "transformation": "fallback of Telephone",
            "required": False,
            "null_behavior": "both blank -> unset",
            "identity_role": "none",
        },
        "Email": {
            "status": VERIFIED,
            "target_model": "res.partner",
            "target_field": "email",
            "transformation": "Email else BillingEmail",
            "required": False,
            "null_behavior": "both blank -> unset",
            "identity_role": "none",
        },
        "BillingEmail": {
            "status": VERIFIED,
            "target_model": "res.partner",
            "target_field": "email",
            "transformation": "fallback of Email",
            "required": False,
            "null_behavior": "both blank -> unset",
            "identity_role": "none",
        },
        "InvoiceAddr": {
            "status": VERIFIED,
            "target_model": "res.partner",
            "target_field": "type",
            "transformation": "address_kind billing signal",
            "required": False,
            "null_behavior": "blank -> no signal",
            "identity_role": "none",
        },
        "RemitToAddress": {
            "status": VERIFIED,
            "target_model": "res.partner",
            "target_field": "type",
            "transformation": "address_kind billing signal",
            "required": False,
            "null_behavior": "blank -> no signal",
            "identity_role": "none",
        },
        "isBillingAddressOnly": {
            "status": VERIFIED,
            "target_model": "res.partner",
            "target_field": "type",
            "transformation": "address_kind billing signal",
            "required": False,
            "null_behavior": "blank -> no signal",
            "identity_role": "none",
        },
        "Fax": {"status": UNMAPPED, "reason": "Odoo 19 res.partner has no fax field", "identity_role": "none"},
    },
    "Contact": {
        "CT_ID": {
            "status": VERIFIED,
            "target_model": "ir.model.data",
            "target_field": "legacy_erp_contact_<CT_ID>",
            "transformation": "XML-ID key",
            "required": True,
            "null_behavior": "blank raises (source_index PRIMARY_KEYS)",
            "identity_role": "contact identity",
        },
        "CpID": {
            "status": VERIFIED,
            "target_model": "res.partner",
            "target_field": "parent_id",
            "transformation": "source-key join only",
            "required": True,
            "null_behavior": "unresolved -> anomaly",
            "identity_role": "parent link",
        },
        "Location": {
            "status": VERIFIED,
            "target_model": "res.partner",
            "target_field": "location_partner_ids (facility)",
            "transformation": "exact (CpID, Type) join into addresses; never fuzzy; parent_id stays the company",
            "required": False,
            "null_behavior": "unresolved -> no location link; parented to company",
            "identity_role": "none",
        },
        "ContactNm": {
            "status": VERIFIED,
            "target_model": "res.partner",
            "target_field": "name",
            "transformation": "strip; blank -> anomaly + reject",
            "required": True,
            "null_behavior": "blank -> anomaly, row rejected (counted in records_rejected)",
            "identity_role": "none",
        },
        "Email": {
            "status": VERIFIED,
            "target_model": "res.partner",
            "target_field": "email; comment for another active alias's different email",
            "transformation": (
                "internal brokerage mailboxes dropped (mapping.external_emails); first active CT_ID's email kept; "
                "a different email of another active CT_ID of the same person is appended once to comment as "
                "'ERP contact <CT_ID> email: ...'"
            ),
            "required": False,
            "null_behavior": "blank -> unset",
            "identity_role": "none",
        },
        "PhoneBusiness": {
            "status": VERIFIED,
            "target_model": "res.partner",
            "target_field": "phone",
            "transformation": "direct",
            "required": False,
            "null_behavior": "blank -> unset",
            "identity_role": "none",
        },
        "PhoneMobile": {
            "status": VERIFIED,
            "target_model": "plasticos.partner.phone",
            "target_field": "phone_line_ids (label mobile)",
            "transformation": "mapping.real_phone; additive phone line; never folded into phone",
            "required": False,
            "null_behavior": "blank -> unset",
            "identity_role": "none",
        },
        "PhoneOther": {
            "status": VERIFIED,
            "target_model": "plasticos.partner.phone",
            "target_field": "phone_line_ids (label other)",
            "transformation": "mapping.real_phone; additive phone line",
            "required": False,
            "null_behavior": "blank -> unset",
            "identity_role": "none",
        },
        "IsActive": {
            "status": VERIFIED,
            "target_model": "—",
            "target_field": "row eligibility (mapping.contact_exclusion)",
            "transformation": (
                "parse_bool is True imports the row; N, blank or unrecognised excludes it before person grouping, "
                "company channel fill and CT_ID aliasing (no person, no marker); imported people are active"
            ),
            "required": True,
            "null_behavior": (
                "N, blank or unrecognised -> omitted (skipped, not an open exception); an earlier "
                "run's marker is removed and its person archived when no other contact marker points at it"
            ),
            "identity_role": "none",
        },
        "Notes": {
            "status": VERIFIED,
            "target_model": "res.partner",
            "target_field": "comment; phone_line_ids (label fax) for a 'Fax:' line",
            "transformation": (
                "distinct notes of the person's active CT_IDs joined; a 'Fax:' line becomes a fax phone line; "
                "merged so CRM paragraphs already on comment are kept (erp.comment_notes)"
            ),
            "required": False,
            "null_behavior": "blank -> unset",
            "identity_role": "none",
        },
        "CompanyNm": {"status": UNMAPPED, "reason": "duplicate of the parent company's name", "identity_role": "none"},
    },
    "ContactRoleAssignment": {
        "CRA_ID": {
            "status": VERIFIED,
            "target_model": "—",
            "target_field": "set semantics (idempotent replay)",
            "transformation": "identity; no standalone record needed",
            "required": True,
            "null_behavior": "blank raises (source_index PRIMARY_KEYS)",
            "identity_role": "assignment identity",
        },
        "CT_ID": {
            "status": VERIFIED,
            "target_model": "res.partner",
            "target_field": "category_id (tags)",
            "transformation": "join to contact",
            "required": True,
            "null_behavior": "unresolved -> IdentityViolation",
            "identity_role": "contact link",
        },
        "RoleNm": {
            "status": VERIFIED,
            "target_model": "res.partner",
            "target_field": "category_id, function",
            "transformation": (
                "role word -> one tag under 'ERP Contact Role' (CONTACT_ROLE_TAGS; set semantics, replay adds "
                "nothing); Job Position (function) = 'Decision Maker' when that tag is present, else the single "
                "other tag, else left unchanged (mapping.job_position); 'RR' stays unresolved, never guessed"
            ),
            "required": False,
            "null_behavior": "blank or unmapped word -> rejected row with anomaly; no tag written",
            "identity_role": "none",
        },
    },
    "SalesReps": {
        "CpID": {
            "status": VERIFIED,
            "target_model": "res.partner",
            "target_field": "company (legacy_erp_cp_<CpID>)",
            "transformation": "source-key join only",
            "required": True,
            "null_behavior": "blank or not exported -> IdentityViolation",
            "identity_role": "company link",
        },
        "ReferrerNo": {
            "status": VERIFIED,
            "target_model": "res.users",
            "target_field": "res.partner.user_id",
            "transformation": "strip padding; initials -> SALES_REP_LOGINS -> existing user by login; never created",
            "required": False,
            "null_behavior": "unknown initials -> anomaly; no single user -> unresolved",
            "identity_role": "none",
        },
        "IsDefault": {
            "status": VERIFIED,
            "target_model": "res.partner",
            "target_field": "user_id",
            "transformation": "unique IsDefault=1 wins; otherwise the sole assigned rep sets the Salesperson",
            "required": False,
            "null_behavior": "no resolvable rep -> leave the existing Salesperson",
            "identity_role": "none",
        },
        "Rate": {"status": UNMAPPED, "reason": "commission rate; not a contact field", "identity_role": "none"},
        "Charge": {"status": UNMAPPED, "reason": "commission charge; not a contact field", "identity_role": "none"},
        "ChgPer": {"status": UNMAPPED, "reason": "commission basis; not a contact field", "identity_role": "none"},
    },
    "WKSDetail": {
        "DetailID": {
            "status": NEEDS_CORRECTION,
            "target_model": "sale.order.line; purchase.order.line",
            "target_field": "ir.model.data external identities",
            "reason": NATIVE_PENDING,
            "required": True,
            "null_behavior": "blank raises (source_index PRIMARY_KEYS)",
            "identity_role": "line identity",
        },
        "BuySellNo": {
            "status": NEEDS_CORRECTION,
            "target_model": "sale.order; purchase.order",
            "target_field": "ir.model.data source identity; sale.order.origin",
            "reason": NATIVE_PENDING,
            "required": True,
            "null_behavior": "unresolved -> anomaly",
            "identity_role": "transaction link",
        },
        "GradeID": {
            "status": NEEDS_CORRECTION,
            "target_model": "sale.order.line; purchase.order.line",
            "target_field": "product_id",
            "reason": NATIVE_PENDING,
            "required": False,
            "null_behavior": "no match -> anomaly",
            "identity_role": "none",
        },
        "InvoiceDesc": {
            "status": NEEDS_CORRECTION,
            "target_model": "sale.order.line; purchase.order.line; account.move.line",
            "target_field": "name",
            "reason": NATIVE_PENDING,
            "required": False,
            "null_behavior": "blank -> unset",
            "identity_role": "none",
        },
        "SWeight": {
            "status": NEEDS_CORRECTION,
            "target_model": "sale.order.line; account.move.line",
            "target_field": "product_uom_qty; quantity",
            "reason": NATIVE_PENDING,
            "required": False,
            "null_behavior": "unparseable -> anomaly",
            "identity_role": "none",
        },
        "PWeight": {
            "status": NEEDS_CORRECTION,
            "target_model": "purchase.order.line; account.move.line",
            "target_field": "product_qty; quantity",
            "reason": NATIVE_PENDING,
            "required": False,
            "null_behavior": "unparseable -> anomaly",
            "identity_role": "none",
        },
        "SWeightUOM": {
            "status": NEEDS_CORRECTION,
            "target_model": "sale.order.line; account.move.line",
            "target_field": "product_uom_id",
            "reason": NATIVE_PENDING,
            "required": False,
            "null_behavior": "neither side -> anomaly; mismatch -> anomaly, never defaulted",
            "identity_role": "none",
        },
        "PWeightUOM": {
            "status": NEEDS_CORRECTION,
            "target_model": "purchase.order.line; account.move.line",
            "target_field": "product_uom_id",
            "reason": NATIVE_PENDING,
            "required": False,
            "null_behavior": "neither side -> anomaly; mismatch -> anomaly",
            "identity_role": "none",
        },
        "SPrice": {
            "status": NEEDS_CORRECTION,
            "target_model": "sale.order.line; account.move.line",
            "target_field": "price_unit",
            "reason": NATIVE_PENDING,
            "required": False,
            "null_behavior": "unparseable -> anomaly",
            "identity_role": "none",
        },
        "PPrice": {
            "status": NEEDS_CORRECTION,
            "target_model": "purchase.order.line; account.move.line",
            "target_field": "price_unit",
            "reason": NATIVE_PENDING,
            "required": False,
            "null_behavior": "unparseable -> anomaly",
            "identity_role": "none",
        },
        "SAmount": {
            "status": NEEDS_CORRECTION,
            "target_model": "account.move.line",
            "target_field": "price_subtotal",
            "reason": NATIVE_PENDING,
            "required": False,
            "null_behavior": "unparseable -> anomaly",
            "identity_role": "none",
        },
        "PAmount": {
            "status": NEEDS_CORRECTION,
            "target_model": "account.move.line",
            "target_field": "price_subtotal",
            "reason": NATIVE_PENDING,
            "required": False,
            "null_behavior": "unparseable -> anomaly",
            "identity_role": "none",
        },
        "Color": {
            "status": UNMAPPED,
            "reason": OMITTED_NO_NATIVE,
            "required": False,
            "null_behavior": "blank -> unset",
            "identity_role": "none",
        },
        "SPo": {
            "status": NEEDS_CORRECTION,
            "target_model": "sale.order",
            "target_field": "name",
            "reason": NATIVE_PENDING,
            "required": False,
            "null_behavior": "blank -> unset",
            "identity_role": "none",
        },
        "PPo": {
            "status": NEEDS_CORRECTION,
            "target_model": "purchase.order",
            "target_field": "name",
            "reason": NATIVE_PENDING,
            "required": False,
            "null_behavior": "blank -> unset",
            "identity_role": "none",
        },
        "LotNo": {
            "status": UNMAPPED,
            "reason": OMITTED_NO_NATIVE,
            "required": False,
            "null_behavior": "blank -> unset",
            "identity_role": "none",
        },
        "UnitType": {
            "status": UNMAPPED,
            "reason": OMITTED_NO_NATIVE,
            "required": False,
            "null_behavior": "blank -> None; unknown -> anomaly",
            "identity_role": "none",
        },
        "Units": {
            "status": UNMAPPED,
            "reason": OMITTED_NO_NATIVE,
            "required": False,
            "null_behavior": "blank -> unset",
            "identity_role": "none",
        },
        "Comment": {
            "status": UNMAPPED,
            "reason": OMITTED_NO_NATIVE,
            "required": False,
            "null_behavior": "blank -> unset",
            "identity_role": "none",
        },
        "DesignatedCpID": {
            "status": UNMAPPED,
            "reason": "rejected as a party (22 of 8257 rows, matches neither side)",
            "identity_role": "none",
        },
        "IsReceived": {"status": UNMAPPED, "reason": "NULL in 11303 of 11303 rows", "identity_role": "none"},
        "IsItemReceived": {"status": UNMAPPED, "reason": "NULL in 11303 of 11303 rows", "identity_role": "none"},
        "SCurrencyCd": {"status": UNMAPPED, "reason": "USD in 11303 of 11303 rows", "identity_role": "none"},
        "PCurrencyCd": {"status": UNMAPPED, "reason": "USD in 11303 of 11303 rows", "identity_role": "none"},
        "SFxAmount": {
            "status": UNMAPPED,
            "reason": "identical to SAmount in 11303 of 11303 rows — zero added information",
            "identity_role": "none",
        },
        "PFxAmount": {
            "status": UNMAPPED,
            "reason": "identical to PAmount in 11303 of 11303 rows — zero added information",
            "identity_role": "none",
        },
        "SPriceUOM": {
            "status": UNMAPPED,
            "reason": "price-basis UOM, distinct from weight UOM; no line field and no business requirement",
            "identity_role": "none",
        },
        "PUOM": {
            "status": UNMAPPED,
            "reason": "price-basis UOM, distinct from weight UOM; no line field and no business requirement",
            "identity_role": "none",
        },
    },
    "GPLedger": {
        "LedgerID": {
            "status": VERIFIED,
            "target_model": "—",
            "target_field": "ledger grouping key",
            "transformation": "source-key index",
            "required": True,
            "null_behavior": "blank raises (source_index PRIMARY_KEYS)",
            "identity_role": "ledger identity",
        },
        "TradeDt": {
            "status": VERIFIED,
            "target_model": "purchase.order",
            "target_field": "date_approve (PO issued / transaction approved); the order stays a draft",
            "transformation": "earliest GPLedger.TradeDt per BuySellNo; a PO serving several worksheets keeps the earliest",
            "required": False,
            "null_behavior": "unparsable -> anomaly; none -> anomaly",
            "identity_role": "none",
        },
        "BuySellNo": {
            "status": NEEDS_CORRECTION,
            "target_model": "sale.order; purchase.order",
            "target_field": "join key only",
            "reason": NATIVE_PENDING,
            "required": True,
            "null_behavior": "blank -> excluded from index",
            "identity_role": "transaction link",
        },
        "Source": {
            "status": UNMAPPED,
            "reason": "booking source code; header reconstruction does not consume it and no Odoo target exists",
            "identity_role": "none",
        },
        "Sale": {
            "status": UNMAPPED,
            "reason": "ledger sale amount; line-level amounts come from WKSDetail, no header aggregation field",
            "identity_role": "none",
        },
        "Cost": {"status": UNMAPPED, "reason": "ledger cost; no header aggregation field", "identity_role": "none"},
        "GrossProfit": {
            "status": UNMAPPED,
            "reason": "derived ledger value; no header aggregation field",
            "identity_role": "none",
        },
        "Commission": {
            "status": UNMAPPED,
            "reason": "ledger commission; plasticos_commission owns commission semantics, not this import",
            "identity_role": "none",
        },
        "AdjCpID": {
            "status": UNMAPPED,
            "reason": "ledger adjustment party; settlement reconstruction does not consume adjustments",
            "identity_role": "none",
        },
        "AdjType": {"status": UNMAPPED, "reason": "ledger adjustment code; no Odoo target", "identity_role": "none"},
        "AdjFxAmount": {
            "status": UNMAPPED,
            "reason": "ledger adjustment amount; no Odoo target",
            "identity_role": "none",
        },
        "APBatchNo": {
            "status": UNMAPPED,
            "reason": "payables batch link; supplier evidence comes from Payables rows directly",
            "identity_role": "none",
        },
        "ARBatchNo": {
            "status": UNMAPPED,
            "reason": "receipts batch link; buyer evidence comes from Receipt.ARBatchNo directly",
            "identity_role": "none",
        },
        "ReferenceID": {"status": UNMAPPED, "reason": "ledger reference; no Odoo target", "identity_role": "none"},
    },
    "Payables": {
        "PayableID": {
            "status": VERIFIED,
            "target_model": "—",
            "target_field": "payable grouping key",
            "transformation": "source-key index",
            "required": True,
            "null_behavior": "blank raises (source_index PRIMARY_KEYS)",
            "identity_role": "payable identity",
        },
        "BuySellNo": {
            "status": NEEDS_CORRECTION,
            "target_model": "account.move.line",
            "target_field": "join key only",
            "reason": NATIVE_PENDING,
            "required": True,
            "null_behavior": "blank -> excluded from index",
            "identity_role": "transaction link",
        },
        "ItemID": {
            "status": VERIFIED,
            "target_model": "—",
            "target_field": "material-vs-freight split (empty/0 = material payable)",
            "transformation": "membership test in _EMPTY_ITEM_IDS",
            "required": False,
            "null_behavior": "empty treated as material payable",
            "identity_role": "none",
        },
        "CpID": {
            "status": NEEDS_CORRECTION,
            "target_model": "account.move",
            "target_field": "partner_id",
            "reason": NATIVE_PENDING,
            "required": False,
            "null_behavior": "none/ambiguous -> anomaly",
            "identity_role": "supplier link",
        },
        "Posted": {
            "status": VERIFIED,
            "target_model": "—",
            "target_field": "supplier-paid evidence (state derivation)",
            "transformation": "== '1'",
            "required": False,
            "null_behavior": "not posted -> not paid",
            "identity_role": "none",
        },
        "Amount": {
            "status": UNMAPPED,
            "reason": "payable amount; line amounts come from WKSDetail, settlement state uses Posted only",
            "identity_role": "none",
        },
        "FxAmount": {
            "status": UNMAPPED,
            "reason": "payable FX amount; no Odoo target in this import",
            "identity_role": "none",
        },
        "CurrencyCd": {
            "status": UNMAPPED,
            "reason": "single-currency payload (USD); see CounterParty.CurrCode drop",
            "identity_role": "none",
        },
        "InvoiceNo": {
            "status": VERIFIED,
            "target_model": "account.move",
            "target_field": "ref (when the PayablesBatch header carries no InvoiceNo)",
            "transformation": "strip; header InvoiceNo, else this, else PayableID",
            "required": False,
            "null_behavior": "blank -> PayableID",
            "identity_role": "none",
        },
        "InvoiceDt": {
            "status": VERIFIED,
            "target_model": "account.move",
            "target_field": "invoice_date (when the PayablesBatch header carries no InvoiceDt)",
            "transformation": "header InvoiceDt, else this; date part; no order-date fallback",
            "required": False,
            "null_behavior": "blank -> undated draft + anomaly",
            "identity_role": "none",
        },
        "RcvDt": {
            "status": UNMAPPED,
            "reason": "receipt date on payable; delivery evidence comes from WksDelivery",
            "identity_role": "none",
        },
        "IsCheck": {"status": UNMAPPED, "reason": "payment method flag; no Odoo target", "identity_role": "none"},
        "CheckNo": {"status": UNMAPPED, "reason": "check number; no Odoo target", "identity_role": "none"},
        "APBatchNo": {
            "status": VERIFIED,
            "target_model": "—",
            "target_field": "PayablesBatch join: PrePay=1 exclusion; source batch grouping",
            "transformation": "strip; membership in SourceIndex.prepay_batches",
            "required": False,
            "null_behavior": "blank -> no batch; row is not a prepay exclusion",
            "identity_role": "payables batch link",
        },
        "Reference_Date": {
            "status": UNMAPPED,
            "reason": "payable reference date; no Odoo target",
            "identity_role": "none",
        },
        "GLAcct": {"status": UNMAPPED, "reason": "source GL account; Odoo owns accounting", "identity_role": "none"},
    },
    "PayablesBatch": {
        "APBatchNo": {
            "status": VERIFIED,
            "target_model": "—",
            "target_field": "payables batch header key",
            "transformation": "RTRIM; source-key index (SourceIndex.payables_batches)",
            "required": True,
            "null_behavior": "blank or duplicated -> payables_batch_violations; left out of the lookup",
            "identity_role": "payables batch identity",
        },
        "PrePay": {
            "status": VERIFIED,
            "target_model": "—",
            "target_field": "prepayment-batch exclusion; Payables rows in a PrePay=1 batch are never billed",
            "transformation": "== '1'",
            "required": False,
            "null_behavior": "not '1' -> not excluded",
            "identity_role": "none",
        },
        "NumofItems": {"status": UNMAPPED, "reason": SOURCE_CONTROL, "identity_role": "none"},
        "FXAmount": {"status": UNMAPPED, "reason": SOURCE_CONTROL, "identity_role": "none"},
        "CurrencyCd": {"status": UNMAPPED, "reason": SOURCE_CONTROL, "identity_role": "none"},
        "PostedInAccting": {
            "status": UNMAPPED,
            "reason": f"{READ_NOT_WRITTEN} Posted in the ERP accounting is not vendor cash paid. {QUICKBOOKS_OWNS}",
            "identity_role": "none",
        },
        "Comment": {"status": UNMAPPED, "reason": READ_NOT_WRITTEN, "identity_role": "none"},
        "ReversedFxAmt": {"status": UNMAPPED, "reason": READ_NOT_WRITTEN, "identity_role": "none"},
        "CpID": {
            "status": NEEDS_CORRECTION,
            "target_model": "account.move (owner unresolved)",
            "target_field": "unresolved (candidate partner_id)",
            "reason": UNRESOLVED_TARGET,
            "required": False,
            "null_behavior": "not written",
            "identity_role": "none",
        },
        "InvoiceNo": {
            "status": VERIFIED,
            "target_model": "account.move",
            "target_field": "ref (vendor invoice number of every bill in the batch)",
            "transformation": "strip; native_orders.vendor_bill_header_facts",
            "required": False,
            "null_behavior": "blank -> Payables.InvoiceNo, else PayableID",
            "identity_role": "none",
        },
        "InvoiceDt": {
            "status": VERIFIED,
            "target_model": "account.move",
            "target_field": "invoice_date",
            "transformation": "date part; native_orders.vendor_bill_header_facts",
            "required": False,
            "null_behavior": "blank -> Payables.InvoiceDt, else undated draft + anomaly",
            "identity_role": "none",
        },
        "PostingDt": {
            "status": NEEDS_CORRECTION,
            "target_model": "account.move (owner unresolved)",
            "target_field": "unresolved (candidate date)",
            "reason": UNRESOLVED_TARGET,
            "required": False,
            "null_behavior": "not written",
            "identity_role": "none",
        },
        "DueDate": {
            "status": VERIFIED,
            "target_model": "account.move",
            "target_field": "invoice_date_due, with invoice_payment_term_id cleared (when APTerms names no term)",
            "transformation": "date part",
            "required": False,
            "null_behavior": "blank -> Odoo default term and due date",
            "identity_role": "none",
        },
        "APTerms": {
            "status": VERIFIED,
            "target_model": "account.payment.term",
            "target_field": "invoice_payment_term_id",
            "transformation": "lookup by exact name; never created; unmatched name reported once",
            "required": False,
            "null_behavior": "blank/no match -> DueDate is the due date",
            "identity_role": "none",
        },
        "COID": {"status": UNMAPPED, "reason": NOT_PROJECTED, "identity_role": "none"},
        "UserID": {"status": UNMAPPED, "reason": NOT_PROJECTED, "identity_role": "none"},
        "RecordDate": {"status": UNMAPPED, "reason": NOT_PROJECTED, "identity_role": "none"},
        "ExportBatchNo": {"status": UNMAPPED, "reason": NOT_PROJECTED, "identity_role": "none"},
        "FxRate": {"status": UNMAPPED, "reason": NOT_PROJECTED, "identity_role": "none"},
        "FxDiscountAmt": {"status": UNMAPPED, "reason": NOT_PROJECTED, "identity_role": "none"},
        "DoNotExport": {"status": UNMAPPED, "reason": NOT_PROJECTED, "identity_role": "none"},
        "ReverseBatchNo": {"status": UNMAPPED, "reason": NOT_PROJECTED, "identity_role": "none"},
    },
    "Receipt": {
        "ReceiptID": {
            "status": VERIFIED,
            "target_model": "—",
            "target_field": "receipt grouping key",
            "transformation": "source-key index",
            "required": True,
            "null_behavior": "blank raises (source_index PRIMARY_KEYS)",
            "identity_role": "receipt identity",
        },
        "BuySellNo": {
            "status": UNMAPPED,
            "reason": QUICKBOOKS_OWNS,
            "required": True,
            "null_behavior": "blank -> excluded from index",
            "identity_role": "transaction link",
        },
        "ARBatchNo": {
            "status": VERIFIED,
            "target_model": "—",
            "target_field": "buyer evidence via ReceiptBatch.CPID",
            "transformation": "batch lookup",
            "required": False,
            "null_behavior": "blank -> row ignored for buyer; missing batch -> anomaly",
            "identity_role": "buyer link",
        },
        "Amount": {
            "status": UNMAPPED,
            "reason": "receipt amount; settlement state uses receipt membership only",
            "identity_role": "none",
        },
        "FxAmount": {"status": UNMAPPED, "reason": "receipt FX amount; no Odoo target", "identity_role": "none"},
        "CurrencyCd": {"status": UNMAPPED, "reason": "single-currency payload (USD)", "identity_role": "none"},
        "CheckNo": {"status": UNMAPPED, "reason": "check number; no Odoo target", "identity_role": "none"},
        "PaymentDt": {
            "status": UNMAPPED,
            "reason": "payment date; trade date comes from GPLedger.TradeDt",
            "identity_role": "none",
        },
        "EntryDt": {"status": UNMAPPED, "reason": "entry date; no Odoo target", "identity_role": "none"},
        "DiscountAmt": {"status": UNMAPPED, "reason": "discount amount; no Odoo target", "identity_role": "none"},
        "LedgerID": {"status": UNMAPPED, "reason": "ledger link; no Odoo target", "identity_role": "none"},
        "PostingType": {"status": UNMAPPED, "reason": "posting type code; no Odoo target", "identity_role": "none"},
        "Reference": {"status": UNMAPPED, "reason": "receipt reference; no Odoo target", "identity_role": "none"},
        "DepositDate": {"status": UNMAPPED, "reason": "deposit date; no Odoo target", "identity_role": "none"},
    },
    "ReceiptBatch": {
        "ARBatchNo": {
            "status": VERIFIED,
            "target_model": "—",
            "target_field": "batch key",
            "transformation": "source-key index",
            "required": True,
            "null_behavior": "blank raises (source_index PRIMARY_KEYS)",
            "identity_role": "batch identity",
        },
        "CPID": {
            "status": UNMAPPED,
            "reason": QUICKBOOKS_OWNS,
            "required": False,
            "null_behavior": "blank -> no buyer; ambiguous -> anomaly",
            "identity_role": "buyer link",
        },
        "PostType": {"status": UNMAPPED, "reason": "posting type code; no Odoo target", "identity_role": "none"},
        "COID": {"status": UNMAPPED, "reason": "company ID; no Odoo target", "identity_role": "none"},
        "NumOfItems": {"status": UNMAPPED, "reason": "batch item count; no Odoo target", "identity_role": "none"},
        "UserID": {"status": UNMAPPED, "reason": "source user; no Odoo target", "identity_role": "none"},
        "PostingDt": {
            "status": UNMAPPED,
            "reason": "batch posting date; trade date comes from GPLedger.TradeDt",
            "identity_role": "none",
        },
        "RecordDate": {"status": UNMAPPED, "reason": "source audit metadata", "identity_role": "none"},
        "CheckNo": {"status": UNMAPPED, "reason": "check number; no Odoo target", "identity_role": "none"},
        "Currency": {"status": UNMAPPED, "reason": "single-currency payload (USD)", "identity_role": "none"},
        "HcApplyAmt": {
            "status": UNMAPPED,
            "reason": "home-currency applied amount; no Odoo target",
            "identity_role": "none",
        },
        "FxApplyAmt": {"status": UNMAPPED, "reason": "FX applied amount; no Odoo target", "identity_role": "none"},
        "ExportBatchNo": {
            "status": UNMAPPED,
            "reason": "export bookkeeping; source audit metadata",
            "identity_role": "none",
        },
        "PostedInAccting": {
            "status": UNMAPPED,
            "reason": "accounting flag; settlement state uses Payables.Posted and receipt membership",
            "identity_role": "none",
        },
        "DoNotExport": {"status": UNMAPPED, "reason": "export bookkeeping flag", "identity_role": "none"},
    },
    "WksDelivery": {
        "ItemID": {
            "status": VERIFIED,
            "target_model": "—",
            "target_field": "delivery-leg evidence (state derivation)",
            "transformation": "membership test, ItemID != '0'",
            "required": False,
            "null_behavior": "blank -> not a delivery leg",
            "identity_role": "none",
        },
        "BuySellNo": {
            "status": NEEDS_CORRECTION,
            "target_model": "account.move.line",
            "target_field": "join key only",
            "reason": NATIVE_PENDING,
            "required": True,
            "null_behavior": "blank -> excluded from index",
            "identity_role": "transaction link",
        },
        "VendorID": {
            "status": UNMAPPED,
            "reason": "freight vendor id; freight/material split derives from Payables.ItemID (header_forensics)",
            "identity_role": "none",
        },
        "TrailerNo": {
            "status": UNMAPPED,
            "reason": "trailer number; no Odoo target in this import",
            "identity_role": "none",
        },
        "DeliveryDt": {
            "status": UNMAPPED,
            "reason": "delivery date; delivery evidence uses row membership only",
            "identity_role": "none",
        },
        "Cost": {
            "status": UNMAPPED,
            "reason": "freight cost; no transaction-line freight field consumed by this import",
            "identity_role": "none",
        },
        "ChgToCustAmt": {
            "status": UNMAPPED,
            "reason": "freight charge-to-customer amount; no Odoo target",
            "identity_role": "none",
        },
        "InvoiceDesc": {
            "status": UNMAPPED,
            "reason": "delivery invoice description; line descriptions come from WKSDetail",
            "identity_role": "none",
        },
        "Mileage": {"status": UNMAPPED, "reason": "mileage; no Odoo target", "identity_role": "none"},
        "PrintOnInvoice": {"status": UNMAPPED, "reason": "invoice print flag; no Odoo target", "identity_role": "none"},
        "CurrencyCd": {"status": UNMAPPED, "reason": "single-currency payload (USD)", "identity_role": "none"},
        "CurrencyCdCust": {"status": UNMAPPED, "reason": "customer currency; no Odoo target", "identity_role": "none"},
        "FxAmount": {"status": UNMAPPED, "reason": "FX amount; no Odoo target", "identity_role": "none"},
        "FxAmountCust": {"status": UNMAPPED, "reason": "customer FX amount; no Odoo target", "identity_role": "none"},
        "GLAcct": {"status": UNMAPPED, "reason": "source GL account; Odoo owns accounting", "identity_role": "none"},
        "Manifest": {"status": UNMAPPED, "reason": "manifest reference; no Odoo target", "identity_role": "none"},
        "PrepaidFreight": {
            "status": UNMAPPED,
            "reason": "prepaid freight flag; no Odoo target in this import",
            "identity_role": "none",
        },
        "PFreightCurCode": {
            "status": UNMAPPED,
            "reason": "prepaid freight currency; no Odoo target",
            "identity_role": "none",
        },
        "Price": {"status": UNMAPPED, "reason": "freight price; no Odoo target", "identity_role": "none"},
        "PricePer": {"status": UNMAPPED, "reason": "freight price basis; no Odoo target", "identity_role": "none"},
        "PriceCust": {"status": UNMAPPED, "reason": "customer freight price; no Odoo target", "identity_role": "none"},
        "PricePerCust": {
            "status": UNMAPPED,
            "reason": "customer freight price basis; no Odoo target",
            "identity_role": "none",
        },
        "DeliveryTime": {"status": UNMAPPED, "reason": "delivery time; no Odoo target", "identity_role": "none"},
        "FxRate": {"status": UNMAPPED, "reason": "FX rate; no Odoo target", "identity_role": "none"},
        "FxContractNo": {"status": UNMAPPED, "reason": "FX contract; no Odoo target", "identity_role": "none"},
        "ExpSalesFxRate": {
            "status": UNMAPPED,
            "reason": "export sales FX rate; no Odoo target",
            "identity_role": "none",
        },
        "ReferenceID": {"status": UNMAPPED, "reason": "delivery reference; no Odoo target", "identity_role": "none"},
        "DetailID": {
            "status": UNMAPPED,
            "reason": "delivery-leg-to-line link; delivery evidence uses row membership only (header_forensics _derive_state)",
            "identity_role": "none",
        },
        "IsJobFreightExp": {
            "status": UNMAPPED,
            "reason": "export bookkeeping flag; no Odoo target",
            "identity_role": "none",
        },
    },
}


@dataclass(frozen=True)
class MappingStatusRow:
    """One source column's verified disposition."""

    source_table: str
    source_field: str
    source_sql_type: str
    target_model: str
    target_field: str
    transformation: str
    required: str
    null_behavior: str
    identity_role: str
    status: str
    reason: str = ""


@dataclass
class MappingStatus:
    """The full status table for one payload."""

    source: str = "erp_extracted_data"
    rows: list[dict] = field(default_factory=list)
    unknowns: list[dict] = field(default_factory=list)


def _sql_types(root: Path) -> dict[str, dict[str, str]]:
    """Column DATA_TYPE per table from the extract's SQL Server metadata."""
    types: dict[str, dict[str, str]] = {}
    meta = root / "meta" / "p0_columns.csv"
    if not meta.is_file():
        return types
    with open(meta, encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            table = (row.get("TABLE_NAME") or "").strip()
            column = (row.get("COLUMN_NAME") or "").strip()
            data_type = (row.get("DATA_TYPE") or "").strip()
            if table and column:
                types.setdefault(table, {})[column] = data_type
    return types


def _disposition(table: str, column: str, sql_type: str) -> dict:
    dispositions = DISPOSITIONS.get(table, {})
    record = dispositions.get(column)
    if record is None:
        return {
            "source_table": table,
            "source_field": column,
            "source_sql_type": sql_type or "unknown",
            "target_model": "",
            "target_field": "",
            "transformation": "",
            "required": "unknown",
            "null_behavior": "unknown",
            "identity_role": "none",
            "status": "UNKNOWN",
            "reason": "",
        }
    return {
        "source_table": table,
        "source_field": column,
        "source_sql_type": sql_type or "unknown",
        "target_model": record.get("target_model", ""),
        "target_field": record.get("target_field", ""),
        "transformation": record.get("transformation", ""),
        "required": str(record.get("required", "unknown")),
        "null_behavior": record.get("null_behavior", ""),
        "identity_role": record.get("identity_role", "none"),
        "status": record.get("status", "UNKNOWN"),
        "reason": record.get("reason", ""),
    }


def build_mapping_status(repo_root: Path | str | None = None) -> MappingStatus:
    """Enumerate every column of the tracked export and join its disposition."""
    root = payload_root(repo_root)
    status = MappingStatus()
    sql_types = _sql_types(root)
    for table, filename in sorted(SOURCE_TABLES.items()):
        extract = root / "bulk" / filename
        with open(extract, encoding="utf-8-sig", newline="") as handle:
            columns = next(csv.reader(handle))
        for column in columns:
            column = column.strip()
            if not column:
                continue
            row = _disposition(table, column, sql_types.get(table, {}).get(column, ""))
            if row["status"] == "UNKNOWN":
                status.unknowns.append(row)
            status.rows.append(row)
    for table in DIRECT_SQL_DISPOSITION_TABLES:
        extract = root / "bulk" / f"{table}.csv"
        if not extract.is_file():
            continue
        with open(extract, encoding="utf-8-sig", newline="") as handle:
            columns = next(csv.reader(handle))
        for column in columns:
            column = column.strip()
            if not column:
                continue
            row = _disposition(table, column, sql_types.get(table, {}).get(column, ""))
            if row["status"] == "UNKNOWN":
                status.unknowns.append(row)
            status.rows.append(row)
    for table, reason in sorted(UNCONSUMED_TABLES.items()):
        extract = root / "bulk" / f"{table}.csv"
        if not extract.is_file():
            continue
        with open(extract, encoding="utf-8-sig", newline="") as handle:
            columns = next(csv.reader(handle))
        for column in columns:
            column = column.strip()
            if not column:
                continue
            status.rows.append(
                {
                    "source_table": table,
                    "source_field": column,
                    "source_sql_type": sql_types.get(table, {}).get(column, ""),
                    "target_model": "",
                    "target_field": "",
                    "transformation": "",
                    "required": "unknown",
                    "null_behavior": "",
                    "identity_role": "none",
                    "status": UNMAPPED,
                    "reason": reason,
                }
            )
    return status


def as_dict(status: MappingStatus) -> dict:
    return {
        "source": status.source,
        "mapping_authority": "docs/erp_import_mapping.md",
        "row_count": len(status.rows),
        "unknown_count": len(status.unknowns),
        "rows": status.rows,
    }
