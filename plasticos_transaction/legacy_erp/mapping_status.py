"""Machine-readable field-mapping status for the LegacyErp source payload.

Encodes the disposition of every source column of the tracked export
(``data/legacy_erp_sm_export``) and emits the mapping-status table consumed by
the canonical import command, the completeness test, and operator evidence.

The dispositions below are verified against the mapping authority
``docs/legacy_erp_import_mapping.md`` (identity contract, header
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

# Tables tracked in the export but not consumed by the importer: their columns
# stay UNMAPPED_INTENTIONALLY with the table-level reason below.
UNCONSUMED_TABLES: dict[str, str] = {
    "PayablesBatch": "tracked export evidence only; importer reads Payables rows directly, never the batch",
    "UACashLedger": "cash-ledger evidence only; no Odoo target field and no business requirement identified",
    "WksDocument": "document-registry evidence only; document files are not carried by the export",
}

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
            "target_field": "company_role, supplier_rank, customer_rank",
            "transformation": "COMPANY_ROLE_BY_LEGACY_ERP_ROLE + trade_ranks (behaviour-proven census)",
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
            "transformation": "XML-ID key",
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
            "target_field": "name, type",
            "transformation": "ADDRESS_TYPE_KIND; unrecognised label kept as name",
            "required": False,
            "null_behavior": "unrecognised -> kind 'other', label preserved",
            "identity_role": "none",
        },
        "Addr1": {
            "status": VERIFIED,
            "target_model": "res.partner",
            "target_field": "street",
            "transformation": "direct",
            "required": False,
            "null_behavior": "blank -> unset",
            "identity_role": "none",
        },
        "Addr2": {
            "status": VERIFIED,
            "target_model": "res.partner",
            "target_field": "street2",
            "transformation": "joined with Addr3",
            "required": False,
            "null_behavior": "blank -> unset",
            "identity_role": "none",
        },
        "Addr3": {
            "status": VERIFIED,
            "target_model": "res.partner",
            "target_field": "street2",
            "transformation": "joined with Addr2",
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
            "target_field": "parent_id (facility)",
            "transformation": "exact (CpID, Type) join into addresses; never fuzzy",
            "required": False,
            "null_behavior": "unresolved -> parented to company",
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
            "target_field": "email",
            "transformation": "direct",
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
            "target_model": "res.partner",
            "target_field": "mobile if installed registry has it, else comment",
            "transformation": "runtime field probe; never folded into phone",
            "required": False,
            "null_behavior": "blank -> unset",
            "identity_role": "none",
        },
        "PhoneOther": {
            "status": VERIFIED,
            "target_model": "res.partner",
            "target_field": "comment",
            "transformation": "direct (no third phone field on Odoo)",
            "required": False,
            "null_behavior": "blank -> unset",
            "identity_role": "none",
        },
        "IsActive": {
            "status": VERIFIED,
            "target_model": "res.partner",
            "target_field": "active",
            "transformation": "parse_bool (Y/N); never compared to int",
            "required": False,
            "null_behavior": "blank -> treated active",
            "identity_role": "none",
        },
        "Notes": {
            "status": VERIFIED,
            "target_model": "res.partner",
            "target_field": "comment",
            "transformation": "direct",
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
            "transformation": "partner tags under 'LegacyErp Contact Role'; primary role fills function",
            "required": False,
            "null_behavior": "blank -> no tags",
            "identity_role": "none",
        },
    },
    "WKSDetail": {
        "DetailID": {
            "status": VERIFIED,
            "target_model": "ir.model.data",
            "target_field": "legacy_erp_detail_<DetailID>",
            "transformation": "XML-ID key",
            "required": True,
            "null_behavior": "blank raises (source_index PRIMARY_KEYS)",
            "identity_role": "line identity",
        },
        "BuySellNo": {
            "status": VERIFIED,
            "target_model": "plasticos.transaction",
            "target_field": "transaction_id (legacy_erp_transaction_<BuySellNo>)",
            "transformation": "source-key join",
            "required": True,
            "null_behavior": "unresolved -> anomaly",
            "identity_role": "transaction link",
        },
        "GradeID": {
            "status": VERIFIED,
            "target_model": "plasticos.transaction.line",
            "target_field": "grade_id",
            "transformation": "lookup",
            "required": False,
            "null_behavior": "no match -> anomaly",
            "identity_role": "none",
        },
        "InvoiceDesc": {
            "status": VERIFIED,
            "target_model": "plasticos.transaction.line",
            "target_field": "description",
            "transformation": "direct",
            "required": False,
            "null_behavior": "blank -> unset",
            "identity_role": "none",
        },
        "SWeight": {
            "status": VERIFIED,
            "target_model": "plasticos.transaction.line",
            "target_field": "sale_weight",
            "transformation": "parse_decimal",
            "required": False,
            "null_behavior": "unparseable -> anomaly",
            "identity_role": "none",
        },
        "PWeight": {
            "status": VERIFIED,
            "target_model": "plasticos.transaction.line",
            "target_field": "purchase_weight",
            "transformation": "parse_decimal",
            "required": False,
            "null_behavior": "unparseable -> anomaly",
            "identity_role": "none",
        },
        "SWeightUOM": {
            "status": VERIFIED,
            "target_model": "plasticos.transaction.line",
            "target_field": "weight_uom (shared)",
            "transformation": "weight_uom() agreement rule; outside L/S/E -> anomaly",
            "required": False,
            "null_behavior": "neither side -> anomaly; mismatch -> anomaly, never defaulted",
            "identity_role": "none",
        },
        "PWeightUOM": {
            "status": VERIFIED,
            "target_model": "plasticos.transaction.line",
            "target_field": "weight_uom (shared)",
            "transformation": "weight_uom() agreement rule",
            "required": False,
            "null_behavior": "neither side -> anomaly; mismatch -> anomaly",
            "identity_role": "none",
        },
        "SPrice": {
            "status": VERIFIED,
            "target_model": "plasticos.transaction.line",
            "target_field": "sale_price",
            "transformation": "parse_decimal",
            "required": False,
            "null_behavior": "unparseable -> anomaly",
            "identity_role": "none",
        },
        "PPrice": {
            "status": VERIFIED,
            "target_model": "plasticos.transaction.line",
            "target_field": "purchase_price",
            "transformation": "parse_decimal",
            "required": False,
            "null_behavior": "unparseable -> anomaly",
            "identity_role": "none",
        },
        "SAmount": {
            "status": VERIFIED,
            "target_model": "plasticos.transaction.line",
            "target_field": "sale_amount",
            "transformation": "parse_decimal",
            "required": False,
            "null_behavior": "unparseable -> anomaly",
            "identity_role": "none",
        },
        "PAmount": {
            "status": VERIFIED,
            "target_model": "plasticos.transaction.line",
            "target_field": "purchase_amount",
            "transformation": "parse_decimal",
            "required": False,
            "null_behavior": "unparseable -> anomaly",
            "identity_role": "none",
        },
        "Color": {
            "status": VERIFIED,
            "target_model": "plasticos.transaction.line",
            "target_field": "color",
            "transformation": "direct",
            "required": False,
            "null_behavior": "blank -> unset",
            "identity_role": "none",
        },
        "SPo": {
            "status": VERIFIED,
            "target_model": "plasticos.transaction.line",
            "target_field": "sale_po",
            "transformation": "direct",
            "required": False,
            "null_behavior": "blank -> unset",
            "identity_role": "none",
        },
        "PPo": {
            "status": VERIFIED,
            "target_model": "plasticos.transaction.line",
            "target_field": "purchase_po",
            "transformation": "direct",
            "required": False,
            "null_behavior": "blank -> unset",
            "identity_role": "none",
        },
        "LotNo": {
            "status": VERIFIED,
            "target_model": "plasticos.transaction.line",
            "target_field": "lot_no",
            "transformation": "direct",
            "required": False,
            "null_behavior": "blank -> unset",
            "identity_role": "none",
        },
        "UnitType": {
            "status": VERIFIED,
            "target_model": "plasticos.transaction.line",
            "target_field": "unit_type",
            "transformation": "UNIT_TYPE_MAP (legacy '9' -> 'O'); unknown -> anomaly",
            "required": False,
            "null_behavior": "blank -> None; unknown -> anomaly",
            "identity_role": "none",
        },
        "Units": {
            "status": VERIFIED,
            "target_model": "plasticos.transaction.line",
            "target_field": "units",
            "transformation": "direct",
            "required": False,
            "null_behavior": "blank -> unset",
            "identity_role": "none",
        },
        "Comment": {
            "status": VERIFIED,
            "target_model": "plasticos.transaction.line",
            "target_field": "specifications",
            "transformation": "direct",
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
            "target_model": "plasticos.transaction",
            "target_field": "transaction_date (reconstructed; not persisted — mapping doc §8)",
            "transformation": "earliest GPLedger.TradeDt per BuySellNo (min, deterministic)",
            "required": False,
            "null_behavior": "unparsable -> anomaly; none -> anomaly",
            "identity_role": "none",
        },
        "BuySellNo": {
            "status": VERIFIED,
            "target_model": "plasticos.transaction",
            "target_field": "legacy_erp_transaction_<BuySellNo>",
            "transformation": "grouping key",
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
            "status": VERIFIED,
            "target_model": "plasticos.transaction",
            "target_field": "legacy_erp_transaction_<BuySellNo>",
            "transformation": "grouping key",
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
            "status": VERIFIED,
            "target_model": "plasticos.transaction",
            "target_field": "supplier (reconstructed header)",
            "transformation": "material payable CpID",
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
            "status": UNMAPPED,
            "reason": "payable invoice number; no header/lines field consumed by this import",
            "identity_role": "none",
        },
        "InvoiceDt": {
            "status": UNMAPPED,
            "reason": "payable invoice date; trade date comes from GPLedger.TradeDt (earliest booked)",
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
            "status": UNMAPPED,
            "reason": "batch link; supplier evidence uses Payables rows directly",
            "identity_role": "none",
        },
        "Reference_Date": {
            "status": UNMAPPED,
            "reason": "payable reference date; no Odoo target",
            "identity_role": "none",
        },
        "GLAcct": {"status": UNMAPPED, "reason": "source GL account; Odoo owns accounting", "identity_role": "none"},
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
            "status": VERIFIED,
            "target_model": "plasticos.transaction",
            "target_field": "legacy_erp_transaction_<BuySellNo>",
            "transformation": "grouping key",
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
            "status": VERIFIED,
            "target_model": "plasticos.transaction",
            "target_field": "buyer (reconstructed header)",
            "transformation": "receipt batch CPID (source header spelling)",
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
            "status": VERIFIED,
            "target_model": "plasticos.transaction",
            "target_field": "legacy_erp_transaction_<BuySellNo>",
            "transformation": "grouping key",
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

    source: str = "legacy_erp_sm_export"
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
        "mapping_authority": "docs/legacy_erp_import_mapping.md",
        "row_count": len(status.rows),
        "unknown_count": len(status.unknowns),
        "rows": status.rows,
    }
