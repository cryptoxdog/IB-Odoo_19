"""Independent ERP source → Odoo 19 native field comparison.

The formulas below are the rehearsal contract. They are not the importer's
helpers: a change in ``plasticos_partner_import`` that disagrees with a
persisted native value fails Gate 6 instead of being re-used as the oracle.

Money may differ from the source amount by one cent when the stored quantity
and the stored unit price reproduce that amount. Any larger gap, a wrong
quantity, or a missing source or target value is a mapping defect.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime

SCHEMA = "l9.plasticos.rehearsal.fidelity.v1"
SHORT_TON_LB = 2000.0
MONEY_TOLERANCE = 0.01
QTY_TOLERANCE = 1e-4
PRICE_TOLERANCE = 1e-6
_DATE_FORMATS = ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d")
_OPEN_SALE = frozenset({"draft", "sent", "sale"})
_OPEN_PURCHASE = frozenset({"draft", "sent", "to approve"})
_MATERIAL_GL = "50100"
_INTERNAL_DOMAINS = ("scrapmanagement.com", "scrapmanagment.com", "ucsincny.com", "ussmrecycle.com")
_INTERNAL_EMAIL = re.compile(
    r"[A-Za-z0-9._%+\-]+@(?:" + "|".join(re.escape(domain) for domain in sorted(_INTERNAL_DOMAINS)) + r")\b",
    re.IGNORECASE,
)
_EMAIL_SPLIT = re.compile(r"[;,]")

# CounterParty.Role, copied from the proven partner-role evidence.
# supplier_rank, customer_rank.
_ROLE = {
    "V": ("supplier", 1, 0),
    "S": ("supplier", 1, 0),
    "D": ("carrier", 0, 0),
    "X": ("buyer", 0, 1),
    "C": ("buyer", 0, 1),
    "A": ("", 1, 1),
    "P": ("", 1, 1),
}
_UOM_XMLID = {"L": "uom.product_uom_lb", "S": "uom.product_uom_lb", "E": "uom.product_uom_unit"}
# The importer's crosswalk (plasticos_partner_import/erp/native_orders.py), copied so the verifier
# does not call it. Only ``fas`` is an Incoterm. The domestic shipping-point bases are declined like
# ``delivered``, but unlike it they never rewrite a stored Incoterm (BRS-EXP-02-R006, ADR-021
# amendment 2026-11-12).
_INCOTERM = {"fas": "FAS"}
_DOMESTIC_BASES = frozenset({"fob", "fob supplier dock", "pickup"})
_DECLINED_BASES = frozenset({"delivered"}) | _DOMESTIC_BASES

COVERAGE: list[dict] = [
    {
        "source_table": "CounterParty",
        "source_field": "CpID",
        "target_model": "ir.model.data",
        "target_field": "name",
        "kind": "direct",
        "scope": "all_imported",
    },
    {
        "source_table": "CounterParty",
        "source_field": "CompanyNm",
        "target_model": "res.partner",
        "target_field": "name",
        "kind": "direct",
        "scope": "all_imported",
    },
    {
        "source_table": "CounterParty",
        "source_field": "ActiveStatus",
        "target_model": "res.partner",
        "target_field": "active",
        "kind": "direct",
        "scope": "all_imported",
    },
    {
        "source_table": "CounterParty",
        "source_field": "Role",
        "target_model": "res.partner",
        "target_field": "company_role,supplier_rank,customer_rank",
        "kind": "direct",
        "scope": "all_imported",
    },
    {
        "source_table": "CounterParty",
        "source_field": "OurCustNo",
        "target_model": "res.partner",
        "target_field": "ref",
        "kind": "direct",
        "scope": "all_imported",
    },
    {
        "source_table": "CounterParty",
        "source_field": "APEMail",
        "target_model": "res.partner",
        "target_field": "email",
        "kind": "direct",
        "scope": "all_imported_when_source_present",
    },
    {
        "source_table": "CounterParty",
        "source_field": "WebSite",
        "target_model": "res.partner",
        "target_field": "website",
        "kind": "direct",
        "scope": "all_imported_when_source_present",
    },
    {
        "source_table": "CounterParty",
        "source_field": "CreditLimit",
        "target_model": "res.partner",
        "target_field": "credit_limit",
        "kind": "direct",
        "scope": "all_imported_when_source_present",
    },
    {
        "source_table": "Address",
        "source_field": "Addr2",
        "target_model": "res.partner",
        "target_field": "street",
        "kind": "direct",
        "scope": "all_imported",
    },
    {
        "source_table": "Address",
        "source_field": "Addr3",
        "target_model": "res.partner",
        "target_field": "street2",
        "kind": "direct",
        "scope": "all_imported",
    },
    {
        "source_table": "Address",
        "source_field": "City",
        "target_model": "res.partner",
        "target_field": "city",
        "kind": "direct",
        "scope": "all_imported",
    },
    {
        "source_table": "Address",
        "source_field": "PostalCd",
        "target_model": "res.partner",
        "target_field": "zip",
        "kind": "direct",
        "scope": "all_imported",
    },
    {
        "source_table": "Contact",
        "source_field": "ContactNm",
        "target_model": "res.partner",
        "target_field": "name",
        "kind": "direct",
        "scope": "all_imported",
    },
    {
        "source_table": "Contact",
        "source_field": "Email",
        "target_model": "res.partner",
        "target_field": "email",
        "kind": "direct",
        "scope": "all_imported_when_source_present",
    },
    {
        "source_table": "Contact",
        "source_field": "IsActive",
        "target_model": "res.partner",
        "target_field": "active",
        "kind": "direct",
        "scope": "all_imported",
        "note": "only an explicit active flag is imported; an inactive marker is a defect",
    },
    {
        "source_table": "PO",
        "source_field": "PONumber",
        "target_model": "sale.order,purchase.order",
        "target_field": "name",
        "kind": "direct",
        "scope": "all_imported",
    },
    {
        "source_table": "PO",
        "source_field": "PODate",
        "target_model": "sale.order,purchase.order",
        "target_field": "date_order",
        "kind": "direct",
        "scope": "all_imported",
    },
    {
        "source_table": "PO",
        "source_field": "PONumber",
        "target_model": "sale.order",
        "target_field": "state",
        "kind": "derived",
        "scope": "all_imported",
        "formula": "sale is the transaction compiler confirming the order; draft and sent remain when confirmation did not run",
    },
    {
        "source_table": "PO",
        "source_field": "POReference",
        "target_model": "sale.order",
        "target_field": "client_order_ref",
        "kind": "direct",
        "scope": "all_imported",
    },
    {
        "source_table": "PO",
        "source_field": "PriceBasis",
        "target_model": "sale.order,purchase.order",
        "target_field": "incoterm",
        "kind": "direct",
        "scope": "all_imported",
        "note": "PO.PriceBasis when set; otherwise the last mapped or delivered BuySell.PriceBasis in importer worksheet order, else the last domestic shipping-point basis (no Incoterm)",
    },
    {
        "source_table": "GPLedger",
        "source_field": "TradeDt",
        "target_model": "purchase.order",
        "target_field": "date_approve",
        "kind": "derived",
        "scope": "all_imported",
        "formula": "earliest TradeDt of the worksheets listed on origin; no trade date leaves it empty",
    },
    {
        "source_table": "WKSDetail",
        "source_field": "SWeight,SWeightUOM",
        "target_model": "sale.order.line",
        "target_field": "product_uom_qty,product_uom_id",
        "kind": "derived",
        "scope": "all_imported",
        "formula": "code S (short ton) becomes pounds at 2000 lb; L stays pounds; E stays each; any other code leaves the product default unit",
    },
    {
        "source_table": "WKSDetail",
        "source_field": "SAmount,SWeight,SPrice",
        "target_model": "sale.order.line",
        "target_field": "price_unit",
        "kind": "derived",
        "scope": "all_imported",
        "formula": "SAmount / converted quantity, else SPrice",
    },
    {
        "source_table": "WKSDetail",
        "source_field": "PWeight,PWeightUOM,PAmount,PPrice",
        "target_model": "purchase.order.line",
        "target_field": "product_qty,price_unit",
        "kind": "derived",
        "scope": "all_imported",
        "formula": "same quantity conversion and amount/quantity price as the sale side",
    },
    {
        "source_table": "WKSDetail",
        "source_field": "InvoiceDesc",
        "target_model": "sale.order.line,purchase.order.line",
        "target_field": "name",
        "kind": "direct",
        "scope": "all_imported_when_source_present",
    },
    {
        "source_table": "BuySell",
        "source_field": "InvoiceDt",
        "target_model": "account.move",
        "target_field": "invoice_date",
        "kind": "direct",
        "scope": "all_imported",
        "note": "customer invoice; a blank source date stays blank",
    },
    {
        "source_table": "BuySell",
        "source_field": "BuySellNo",
        "target_model": "account.move",
        "target_field": "invoice_origin,ref",
        "kind": "direct",
        "scope": "all_imported",
    },
    {
        "source_table": "WKSDetail",
        "source_field": "SAmount",
        "target_model": "account.move",
        "target_field": "amount_total",
        "kind": "derived",
        "scope": "all_imported",
        "formula": "sum of converted quantity x unit price for details with one sale-order header; a line with no sale key is omitted; a negative signed total is an out_refund",
    },
    {
        "source_table": "Payables",
        "source_field": "Amount",
        "target_model": "account.move",
        "target_field": "amount_total,move_type",
        "kind": "derived",
        "scope": "all_imported",
        "formula": "a material bill whose payable matches the signed purchase total stores each purchase line as an absolute amount; every other bill stores the absolute payable; a negative payable is an in_refund",
    },
    {
        "source_table": "PayablesBatch",
        "source_field": "InvoiceDt,InvoiceNo",
        "target_model": "account.move",
        "target_field": "invoice_date,ref",
        "kind": "direct",
        "scope": "all_imported",
        "note": "batch header wins, then the payable row; PayableID is the ref fallback",
    },
    {
        "source_table": "GPLedger",
        "source_field": "Sale,TradeDt,AdjMemoNo",
        "target_model": "account.move",
        "target_field": "amount_total,invoice_date,ref,move_type",
        "kind": "derived",
        "scope": "all_imported",
        "note": "customer credit and debit memos only",
    },
    {
        "source_table": "CounterParty",
        "source_field": "CurrCode",
        "target_model": None,
        "target_field": None,
        "kind": "unmapped",
        "reason": "the partner writer does not store a currency",
    },
    {
        "source_table": "CounterParty",
        "source_field": "OnHold",
        "target_model": None,
        "target_field": None,
        "kind": "unmapped",
        "reason": "the partner writer does not store the hold flag",
    },
    {
        "source_table": "CounterParty",
        "source_field": "CpLastEdit",
        "target_model": None,
        "target_field": None,
        "kind": "unmapped",
        "reason": "source audit metadata; Odoo keeps its own write date",
    },
    {
        "source_table": "CounterParty",
        "source_field": "PaymentDays",
        "target_model": None,
        "target_field": None,
        "kind": "unmapped",
        "reason": "the partner writer does not store payment days",
    },
    {
        "source_table": "WKSDetail",
        "source_field": "Color",
        "target_model": None,
        "target_field": None,
        "kind": "unmapped",
        "reason": "the native line writer does not assign Color",
    },
    {
        "source_table": "WKSDetail",
        "source_field": "SCurrencyCd",
        "target_model": None,
        "target_field": None,
        "kind": "unmapped",
        "reason": "the native line writer does not assign a currency",
    },
    {
        "source_table": "excluded",
        "source_field": "QuickBooks, opening balances, AR/AP aging, ledger reconciliation, posted history",
        "target_model": None,
        "target_field": None,
        "kind": "excluded",
        "reason": "outside this fidelity check; not a mapping pass",
    },
]


def text(value) -> str:
    if value is None or value is False:
        return ""
    return str(value).strip()


def as_float(value) -> float | None:
    if value is None or value is False or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    raw = text(value)
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def company_number(value) -> float | None:
    """The company-dependent amount Odoo stores on a monetary partner field.

    A plain number is that amount. A JSON object is the amount keyed by company
    id. One distinct amount is the stored value. Several amounts use company 1,
    which is the company the import writes.
    """
    parsed = value
    if isinstance(value, str) and value.strip().startswith("{"):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return None
    if isinstance(parsed, dict):
        keyed = {str(key): as_float(item) for key, item in parsed.items()}
        numbers = [item for item in keyed.values() if item is not None]
        if not numbers:
            return None
        if len(set(numbers)) == 1:
            return numbers[0]
        return keyed.get("1")
    return as_float(parsed)


def source_token(value) -> str:
    token = "".join(ch if ch.isalnum() else "_" for ch in text(value))
    return token or "blank"


def external_email(value) -> str:
    raw = value or ""
    if not _INTERNAL_EMAIL.search(raw):
        return raw.strip()
    kept = [part.strip() for part in _EMAIL_SPLIT.split(raw)]
    return "; ".join(part for part in kept if part and not _INTERNAL_EMAIL.search(part))


def bare_url(value) -> str:
    folded = text(value).casefold()
    for scheme in ("https://", "http://"):
        if folded.startswith(scheme):
            folded = folded[len(scheme) :]
    return folded.rstrip("/")


def native_quantity(weight, uom_code) -> tuple[float, str]:
    code = text(uom_code).upper()
    value = as_float(weight) or 0.0
    if code == "S":
        return value * SHORT_TON_LB, "L"
    return value, code


def unit_price(amount, quantity: float, source_price) -> float:
    if quantity:
        return (as_float(amount) or 0.0) / quantity
    parsed = as_float(source_price)
    return 0.0 if parsed is None else parsed


def parse_when(value) -> datetime | None:
    raw = text(value).replace("T", " ")
    if not raw:
        return None
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(raw[:26], fmt)
        except ValueError:
            continue
    return None


def same_when(expected, actual) -> bool:
    left = parse_when(expected)
    right = parse_when(actual)
    if left is None or right is None:
        return left is None and right is None
    if left.time().isoformat() != "00:00:00" and right.time().isoformat() != "00:00:00":
        return left.replace(microsecond=0) == right.replace(microsecond=0)
    return left.date() == right.date()


def incoterm_of(basis) -> str | None:
    folded = text(basis).lower()
    if not folded or "do not use" in folded or folded in _DECLINED_BASES:
        return None
    return _INCOTERM.get(folded)


def person_key(name) -> str:
    raw = text(name)
    folded = "".join(ch for ch in raw.upper() if ch.isalnum()) or raw.casefold()
    if not raw or ";" in raw or "/" in raw:
        return folded
    words = [word for word in raw.split() if word]
    if len(words) < 2:
        return folded
    return "|".join("".join(ch for ch in word.upper() if ch.isalnum()) for word in (words[0], words[-1]))


def explicit_active(value) -> bool:
    return text(value).upper() in {"Y", "1", "TRUE"}


def ledger_kind(row: dict) -> str:
    source = text(row.get("Source")).upper()
    if source == "B":
        return "base_trade"
    if source in {"D", "F"}:
        return "settlement_evidence"
    if text(row.get("AdjApproved")).upper() != "Y":
        return "unapproved"
    if text(row.get("AdjType")).upper() == "P":
        return "carried_by_payables"
    return "customer_credit" if (as_float(row.get("Sale")) or 0.0) < 0 else "customer_debit"


def _alnum(value) -> str:
    return "".join(ch for ch in text(value).upper() if ch.isalnum())


def address_is_invoice(row: dict) -> bool:
    label = text(row.get("Type")).upper()
    if label in {"INVOICE", "REMIT", "PRIMARY", "PRIMARY ADDRESS"}:
        return True
    for column in ("InvoiceAddr", "RemitToAddress", "isBillingAddressOnly"):
        if text(row.get(column)).upper() in {"Y", "1", "TRUE"}:
            return True
    return False


def canonical_billing(rows: list[tuple[str, dict]]) -> tuple[str, dict] | None:
    billing = [(address_id, row) for address_id, row in rows if address_is_invoice(row)]
    if not billing:
        return None

    def rank(item: tuple[str, dict]) -> tuple:
        row = item[1]
        remit = 0 if text(row.get("RemitToAddress")).upper() in {"Y", "1", "TRUE"} else 1
        invoice = 0 if text(row.get("InvoiceAddr")).upper() in {"Y", "1", "TRUE"} else 1
        label = 0 if text(row.get("Type")).upper() in {"INVOICE", "REMIT"} else 1
        return (remit, invoice, label, item[0])

    return min(billing, key=rank)


def same_party_name(left, right) -> bool:
    """True when two labels are the same company, or either label is blank."""
    left_key, right_key = _alnum(left), _alnum(right)
    return not left_key or not right_key or left_key == right_key


def folded_company_address(rows: list[tuple[str, dict]], company_name) -> tuple[dict[str, str], dict[str, str]]:
    """Street fields the company keeps after fill-if-blank.

    The remit is applied first. A later address fills a still-blank field when
    its party name matches the company. A blank party name matches.
    """
    pairs = sorted(rows, key=lambda item: item[0])
    billing = [item for item in pairs if address_is_invoice(item[1])]
    locations = [item for item in pairs if not address_is_invoice(item[1])]
    chosen = canonical_billing(pairs)
    chosen_id = chosen[0] if chosen else None
    ordered = [chosen] if chosen else []
    ordered.extend(item for item in (*billing, *locations) if item[0] != chosen_id)
    filled: dict[str, str] = {}
    sources: dict[str, str] = {}
    for address_id, row in ordered:
        if address_id != chosen_id and not same_party_name(row.get("Addr1"), company_name):
            continue
        for column in ("Addr2", "Addr3", "City", "PostalCd"):
            value = text(row.get(column))
            if value and column not in filled:
                filled[column] = value
                sources[column] = address_id
    return filled, sources


def sale_line_included(detail: dict, source: dict) -> bool:
    """A worksheet line is on the customer invoice when one sale header owns its key."""
    key = text(detail.get("SPO_ID"))
    if not key:
        return False
    number = text((source.get("order_lines") or {}).get(key))
    if not number:
        return False
    raw = (source.get("sale_header_count") or {}).get(number)
    try:
        count = int(raw)
    except (TypeError, ValueError):
        return False
    return count == 1


def _exact_each_quantity(amount, price) -> float | None:
    """Integer ``amount / price`` when the product reconciles exactly. Otherwise None.

    This is the rehearsal copy of the zero-weight rule. It does not read ``WKSDetail.Units``
    and it does not substitute quantity 1.
    """
    from decimal import Decimal, InvalidOperation

    def _dec(value):
        text = "" if value is None else str(value).strip()
        if not text or text.upper() == "NULL":
            return Decimal(0)
        try:
            return Decimal(text)
        except InvalidOperation:
            return None

    amount_d = _dec(amount)
    price_d = _dec(price)
    if amount_d is None or price_d is None or amount_d == 0 or price_d == 0:
        return None
    quantity = amount_d / price_d
    if quantity != quantity.to_integral_value() or quantity * price_d != amount_d or quantity == 0:
        return None
    return float(quantity)


def purchase_bill_absolute(details: list[dict]) -> tuple[float, float, bool]:
    """Signed purchase total and the absolute total a matching material bill stores."""
    signed = 0.0
    absolute = 0.0
    any_line = False
    for detail in details:
        amount = as_float(detail.get("PAmount")) or 0.0
        signed += amount
        weight, _code = native_quantity(detail.get("PWeight"), detail.get("PWeightUOM"))
        if not weight:
            weight = _exact_each_quantity(detail.get("PAmount"), detail.get("PPrice")) or 0.0
        if not weight or not amount:
            continue
        any_line = True
        absolute += abs(amount)
    return signed, absolute, any_line


def _row(
    *,
    source_id,
    source_table,
    source_field,
    source_value,
    target_model,
    target_field,
    expected,
    actual,
    tolerance,
    result,
    classification,
    detail="",
) -> dict:
    return {
        "source_id": "" if source_id is None else str(source_id),
        "source_table": source_table,
        "source_field": source_field,
        "source_value": source_value,
        "target_model": target_model,
        "target_field": target_field,
        "expected": expected,
        "actual": actual,
        "tolerance": tolerance,
        "result": result,
        "classification": classification,
        "detail": detail,
    }


def _close(expected, actual, tolerance: float) -> bool:
    left = as_float(expected)
    right = as_float(actual)
    if left is None or right is None:
        return False
    return abs(left - right) <= tolerance


def _mapped(rows: list, **kwargs) -> None:
    expected = kwargs["expected"]
    actual = kwargs["actual"]
    if expected == actual or (isinstance(expected, float) and _close(expected, actual, kwargs.get("tolerance") or 0.0)):
        rows.append(_row(result="PASS", classification="mapped", detail="", **kwargs))
        return
    if isinstance(expected, str) and isinstance(actual, str) and expected.casefold() == actual.casefold():
        rows.append(_row(result="PASS", classification="precision", detail="letter case only", **kwargs))
        return
    rows.append(_row(result="FAIL", classification="defect", detail="persisted value differs", **kwargs))


def _missing(rows: list, **kwargs) -> None:
    rows.append(_row(result="FAIL", classification="defect", **kwargs))


class _Rows:
    """Field comparisons. A rehearsal retains failures only; the counters stay complete."""

    def __init__(self, retain_passes: bool = True):
        self.retain_passes = retain_passes
        self.rows: list[dict] = []
        self.compared = 0
        self.failed = 0
        self.rejected = 0
        self.unmapped = 0
        self.precision = 0

    def append(self, row: dict) -> None:
        result = row.get("result")
        classification = row.get("classification")
        if result == "FAIL":
            self.failed += 1
            self.rows.append(row)
            return
        if result == "PASS" and classification == "rejected":
            self.rejected += 1
        elif result == "PASS" and classification == "unmapped":
            self.unmapped += 1
        elif result == "PASS" and classification == "precision":
            self.precision += 1
            self.compared += 1
        elif result == "PASS" and classification == "mapped":
            self.compared += 1
        else:
            self.rows.append(row)
            return
        if self.retain_passes:
            self.rows.append(row)


class _Check:
    def __init__(self, odoo: dict, source: dict, *, retain_passes: bool = True):
        self.odoo = odoo
        self.source = source
        self.rows = _Rows(retain_passes)
        self.partners = {
            row["xmlid"]: row for row in odoo.get("partners") or [] if isinstance(row, dict) and row.get("xmlid")
        }
        self.by_partner: dict[int, list[dict]] = {}
        for row in self.partners.values():
            partner_id = row.get("partner_id")
            if isinstance(partner_id, int):
                self.by_partner.setdefault(partner_id, []).append(row)

    def companies(self) -> list[dict]:
        return [row for xmlid, row in self.partners.items() if xmlid.startswith("legacy_erp_cp_")]

    def add(self, **kwargs) -> None:
        _mapped(self.rows, **kwargs)

    def miss(self, **kwargs) -> None:
        _missing(self.rows, **kwargs)


def _partner_fields(check: _Check, row: dict, source_row: dict, source_id: str) -> None:
    check.add(
        source_id=source_id,
        source_table="CounterParty",
        source_field="CompanyNm",
        source_value=text(source_row.get("CompanyNm")),
        target_model="res.partner",
        target_field="name",
        expected=text(source_row.get("CompanyNm")),
        actual=text(row.get("name")),
        tolerance=None,
    )
    active = text(source_row.get("ActiveStatus")).upper() != "I"
    check.add(
        source_id=source_id,
        source_table="CounterParty",
        source_field="ActiveStatus",
        source_value=text(source_row.get("ActiveStatus")),
        target_model="res.partner",
        target_field="active",
        expected=active,
        actual=bool(row.get("active")),
        tolerance=None,
    )
    role = _ROLE.get(text(source_row.get("Role")).upper())
    expected_role = role[0] if role else ""
    actual_role = text(row.get("company_role"))
    check.add(
        source_id=source_id,
        source_table="CounterParty",
        source_field="Role",
        source_value=text(source_row.get("Role")),
        target_model="res.partner",
        target_field="company_role",
        expected=expected_role,
        actual=actual_role,
        tolerance=None,
    )
    supplier, customer = (role[1], role[2]) if role else (0, 0)
    for field_name, expected, column in (
        ("supplier_rank", supplier, "supplier_rank"),
        ("customer_rank", customer, "customer_rank"),
    ):
        check.add(
            source_id=source_id,
            source_table="CounterParty",
            source_field="Role",
            source_value=text(source_row.get("Role")),
            target_model="res.partner",
            target_field=field_name,
            expected=expected,
            actual=int(row.get(column) or 0),
            tolerance=0,
        )
    ref = text(source_row.get("OurCustNo"))
    if ref or text(row.get("ref")):
        check.add(
            source_id=source_id,
            source_table="CounterParty",
            source_field="OurCustNo",
            source_value=ref,
            target_model="res.partner",
            target_field="ref",
            expected=ref,
            actual=text(row.get("ref")),
            tolerance=None,
        )
    email = text(source_row.get("APEMail"))
    if email:
        actual_email = text(row.get("email"))
        kwargs = {
            "source_id": source_id,
            "source_table": "CounterParty",
            "source_field": "APEMail",
            "source_value": email,
            "target_model": "res.partner",
            "target_field": "email",
            "expected": email,
            "actual": actual_email,
            "tolerance": None,
        }
        if email.casefold() == actual_email.casefold():
            _mapped(check.rows, **kwargs)
        else:
            check.miss(detail="company email differs from the source mailbox", **kwargs)
    website = text(source_row.get("WebSite"))
    if website:
        kwargs = {
            "source_id": source_id,
            "source_table": "CounterParty",
            "source_field": "WebSite",
            "source_value": website,
            "target_model": "res.partner",
            "target_field": "website",
            "expected": bare_url(website),
            "actual": bare_url(row.get("website")),
            "tolerance": "scheme",
        }
        if bare_url(website) == bare_url(row.get("website")):
            classification = "precision" if bare_url(website) != text(row.get("website")).casefold() else "mapped"
            detail = "Odoo stores the website with a scheme" if classification == "precision" else ""
            check.rows.append(_row(result="PASS", classification=classification, detail=detail, **kwargs))
        else:
            check.miss(detail="website host differs", **kwargs)
    credit = as_float(source_row.get("CreditLimit"))
    if credit:
        actual_credit = company_number(row.get("credit_limit"))
        kwargs = {
            "source_id": source_id,
            "source_table": "CounterParty",
            "source_field": "CreditLimit",
            "source_value": text(source_row.get("CreditLimit")),
            "target_model": "res.partner",
            "target_field": "credit_limit",
            "expected": credit,
            "actual": actual_credit,
            "tolerance": MONEY_TOLERANCE,
        }
        if actual_credit is None:
            check.miss(detail="credit limit was not persisted", **kwargs)
        elif _close(credit, actual_credit, MONEY_TOLERANCE):
            check.rows.append(_row(result="PASS", classification="mapped", detail="", **kwargs))
        else:
            check.miss(detail="credit limit differs", **kwargs)


def _address_fields(
    check: _Check, row: dict, source_row: dict, source_id: str, company: dict | None, candidates=None
) -> None:
    if company is not None:
        filled, sources = folded_company_address(candidates or [], company.get("name"))
        target = company
        for source_field, target_field, column in (
            ("Addr2", "street", "street"),
            ("Addr3", "street2", "street2"),
            ("City", "city", "city"),
            ("PostalCd", "zip", "zip"),
        ):
            expected = filled.get(source_field, "")
            actual = text(target.get(column))
            if not expected and not actual:
                continue
            check.add(
                source_id=sources.get(source_field, source_id),
                source_table="Address",
                source_field=source_field,
                source_value=expected,
                target_model="res.partner",
                target_field=target_field,
                expected=expected,
                actual=actual,
                tolerance=None,
            )
        return
    for source_field, target_field, column in (
        ("Addr2", "street", "street"),
        ("Addr3", "street2", "street2"),
        ("City", "city", "city"),
        ("PostalCd", "zip", "zip"),
    ):
        expected = text(source_row.get(source_field))
        actual = text(row.get(column))
        if not expected and not actual:
            continue
        check.add(
            source_id=source_id,
            source_table="Address",
            source_field=source_field,
            source_value=expected,
            target_model="res.partner",
            target_field=target_field,
            expected=expected,
            actual=actual,
            tolerance=None,
        )


def _contacts(check: _Check) -> None:
    grouped: dict[int, list[tuple[str, dict, dict]]] = {}
    for xmlid, row in check.partners.items():
        if not xmlid.startswith("legacy_erp_contact_") or xmlid.startswith("legacy_erp_contact_role_"):
            continue
        contact_id = xmlid.removeprefix("legacy_erp_contact_")
        source_row = (check.source.get("contacts") or {}).get(contact_id)
        if not isinstance(source_row, dict):
            check.miss(
                source_id=contact_id,
                source_table="Contact",
                source_field="CT_ID",
                source_value=None,
                target_model="res.partner",
                target_field="name",
                expected=None,
                actual=text(row.get("name")),
                tolerance=None,
                detail="imported contact has no source row",
            )
            continue
        if not explicit_active(source_row.get("IsActive")):
            check.miss(
                source_id=contact_id,
                source_table="Contact",
                source_field="IsActive",
                source_value=text(source_row.get("IsActive")),
                target_model="res.partner",
                target_field="active",
                expected="not imported",
                actual=text(row.get("name")),
                tolerance=None,
                detail="an inactive or blank contact flag was imported",
            )
            continue
        partner_id = row.get("partner_id")
        if isinstance(partner_id, int):
            grouped.setdefault(partner_id, []).append((contact_id, source_row, row))
    for members in grouped.values():
        members = sorted(members, key=lambda item: (0, int(item[0])) if item[0].isdigit() else (1, item[0]))
        stored = text(members[0][2].get("name"))
        names = [text(source_row.get("ContactNm")) for _contact_id, source_row, _partner in members]
        emails = [external_email(source_row.get("Email")) for _contact_id, source_row, _partner in members]
        keys = {person_key(name) for name in names if name}
        anchor = min(members, key=lambda item: (0, int(item[0])) if item[0].isdigit() else (1, item[0]))
        expected_name = text(anchor[1].get("ContactNm"))
        name_ok = stored == expected_name or (stored in names and len(keys) == 1)
        for contact_id, source_row, _partner in members:
            check.rows.append(
                _row(
                    source_id=contact_id,
                    source_table="Contact",
                    source_field="ContactNm",
                    source_value=text(source_row.get("ContactNm")),
                    target_model="res.partner",
                    target_field="name",
                    expected=expected_name,
                    actual=stored,
                    tolerance=None,
                    result="PASS" if name_ok else "FAIL",
                    classification="mapped" if stored == expected_name else "precision" if name_ok else "defect",
                    detail="" if stored == expected_name else "same person, anchor name kept" if name_ok else "",
                )
            )
        populated = [email for email in emails if email]
        actual_email = text(members[0][2].get("email"))
        if populated:
            email_ok = actual_email.casefold() in {email.casefold() for email in populated}
            for contact_id, source_row, _partner in members:
                source_email = external_email(source_row.get("Email"))
                if not source_email:
                    continue
                check.rows.append(
                    _row(
                        source_id=contact_id,
                        source_table="Contact",
                        source_field="Email",
                        source_value=text(source_row.get("Email")),
                        target_model="res.partner",
                        target_field="email",
                        expected=populated[0],
                        actual=actual_email,
                        tolerance=None,
                        result="PASS" if email_ok else "FAIL",
                        classification="mapped" if email_ok else "defect",
                        detail="" if actual_email.casefold() == populated[0].casefold() else "first grouped mailbox",
                    )
                )


def _orders(check: _Check) -> None:
    for kind, model, prefix, states in (
        ("sale_orders", "sale.order", "legacy_erp_so_", _OPEN_SALE),
        ("purchase_orders", "purchase.order", "legacy_erp_po_", _OPEN_PURCHASE),
    ):
        for order in check.odoo.get(kind) or []:
            if not isinstance(order, dict):
                continue
            xmlid = text(order.get("xmlid"))
            name = text(order.get("name"))
            header = (check.source.get("orders") or {}).get(f"{name}|{'SO' if model == 'sale.order' else 'PO'}")
            if not isinstance(header, dict):
                check.miss(
                    source_id=name,
                    source_table="PO",
                    source_field="PONumber",
                    source_value=None,
                    target_model=model,
                    target_field="name",
                    expected=None,
                    actual=name,
                    tolerance=None,
                    detail="imported order has no source PO header",
                )
                continue
            check.add(
                source_id=name,
                source_table="PO",
                source_field="PONumber",
                source_value=text(header.get("PONumber")),
                target_model="ir.model.data",
                target_field="name",
                expected=f"{prefix}{source_token(header.get('PONumber'))}",
                actual=xmlid,
                tolerance=None,
            )
            check.add(
                source_id=name,
                source_table="PO",
                source_field="PONumber",
                source_value=text(header.get("PONumber")),
                target_model=model,
                target_field="name",
                expected=text(header.get("PONumber")),
                actual=name,
                tolerance=None,
            )
            when = text(header.get("PODate"))
            if not when:
                numbers = [token.strip() for token in text(order.get("origin")).split(",") if token.strip()]
                buysell = (check.source.get("buysell") or {}).get(numbers[0]) if numbers else None
                when = text((buysell or {}).get("OrderDt"))
            check.rows.append(
                _row(
                    source_id=name,
                    source_table="PO",
                    source_field="PODate",
                    source_value=text(header.get("PODate")),
                    target_model=model,
                    target_field="date_order",
                    expected=when,
                    actual=text(order.get("date_order")),
                    tolerance=None,
                    result="PASS" if same_when(when, order.get("date_order")) else "FAIL",
                    classification="mapped" if same_when(when, order.get("date_order")) else "defect",
                    detail="",
                )
            )
            if model == "sale.order":
                ref = text(header.get("POReference"))
                if ref or text(order.get("client_order_ref")):
                    check.add(
                        source_id=name,
                        source_table="PO",
                        source_field="POReference",
                        source_value=ref,
                        target_model=model,
                        target_field="client_order_ref",
                        expected=ref,
                        actual=text(order.get("client_order_ref")),
                        tolerance=None,
                    )
            else:
                _approve(check, order, name)
            _basis(check, order, header, model, name)
            state = text(order.get("state"))
            allowed = _OPEN_SALE if model == "sale.order" else states
            expected_state = "draft|sent|sale" if model == "sale.order" else "draft|sent|to approve"
            if state in allowed:
                detail = ""
                if model == "sale.order" and state == "sale":
                    detail = "confirmed so the worksheet transaction can compile"
                elif model == "sale.order":
                    detail = "confirmation did not run; the order stayed open"
                check.rows.append(
                    _row(
                        source_id=name,
                        source_table="PO",
                        source_field="PONumber",
                        source_value=name,
                        target_model=model,
                        target_field="state",
                        expected=expected_state,
                        actual=state,
                        tolerance=None,
                        result="PASS",
                        classification="mapped",
                        detail=detail,
                    )
                )
            else:
                check.miss(
                    source_id=name,
                    source_table="PO",
                    source_field="PONumber",
                    source_value=name,
                    target_model=model,
                    target_field="state",
                    expected=expected_state,
                    actual=state,
                    tolerance=None,
                    detail="historical sale order left the import states"
                    if model == "sale.order"
                    else "historical purchase order is confirmed",
                )


def _approve(check: _Check, order: dict, name: str) -> None:
    numbers = [token.strip() for token in text(order.get("origin")).split(",") if token.strip()]
    found: list[datetime] = []
    for number in numbers:
        for raw in (check.source.get("ledger") or {}).get(number) or []:
            parsed = parse_when(raw)
            if parsed is not None:
                found.append(parsed)
    actual = text(order.get("date_approve"))
    if not found:
        if actual:
            check.miss(
                source_id=name,
                source_table="GPLedger",
                source_field="TradeDt",
                source_value=None,
                target_model="purchase.order",
                target_field="date_approve",
                expected=None,
                actual=actual,
                tolerance=None,
                detail="date_approve was set without a source trade date",
            )
        else:
            check.rows.append(
                _row(
                    source_id=name,
                    source_table="GPLedger",
                    source_field="TradeDt",
                    source_value=None,
                    target_model="purchase.order",
                    target_field="date_approve",
                    expected=None,
                    actual=None,
                    tolerance=None,
                    result="PASS",
                    classification="unmapped",
                    detail="no source trade date; approval date stays empty",
                )
            )
        return
    earliest = min(found).strftime("%Y-%m-%d %H:%M:%S")
    check.rows.append(
        _row(
            source_id=name,
            source_table="GPLedger",
            source_field="TradeDt",
            source_value=earliest,
            target_model="purchase.order",
            target_field="date_approve",
            expected=earliest,
            actual=actual,
            tolerance=None,
            result="PASS" if same_when(earliest, actual) else "FAIL",
            classification="mapped" if same_when(earliest, actual) else "defect",
            detail="earliest worksheet trade date",
        )
    )


def _basis_effect(basis: str) -> str:
    """How one price basis changes an Incoterm already written on the order.

    This is the importer's write, copied here so the verifier does not call it.
    A blank basis and a basis with no Incoterm leave the stored value. ``delivered``
    clears it. A domestic shipping-point basis is declined: it leaves the stored
    value and is the reported basis only when nothing else applies. A mapped
    basis replaces it.
    """
    folded = text(basis).lower()
    if not folded or "do not use" in folded:
        return "keep"
    if folded in _DOMESTIC_BASES:
        return "decline"
    if folded in _DECLINED_BASES:
        return "clear"
    if folded in _INCOTERM:
        return "map"
    return "keep"


def effective_price_basis(header: dict, origin, buysells) -> tuple[str, str, str]:
    """``(basis, source_table, worksheet)`` after the importer's precedence.

    A non-empty ``PO.PriceBasis`` is the only basis applied. Otherwise each
    worksheet named on ``origin`` is applied in lexicographic worksheet-number
    order, the order ``SourceIndex.buysell_numbers`` imports them. A mapped or
    declined worksheet basis replaces the previous one. A blank worksheet does not.
    """
    header_basis = text((header or {}).get("PriceBasis"))
    if header_basis:
        if _basis_effect(header_basis) == "keep":
            return "", "PO", ""
        return header_basis, "PO", ""
    chosen = ""
    table = "PO"
    winner = ""
    declined = ("", "PO", "")
    numbers = sorted(part.strip() for part in text(origin).split(",") if part.strip())
    indexed = buysells if isinstance(buysells, dict) else {}
    for number in numbers:
        row = indexed.get(number)
        basis = text((row or {}).get("PriceBasis")) if isinstance(row, dict) else ""
        effect = _basis_effect(basis)
        if effect == "keep":
            continue
        if effect == "decline":
            declined = (basis, "BuySell", number)
            continue
        chosen = basis
        table = "BuySell"
        winner = number
    if not chosen:
        return declined
    return chosen, table, winner


def _basis(check: _Check, order: dict, header: dict, model: str, name: str) -> None:
    basis, table, winner = effective_price_basis(header, order.get("origin"), check.source.get("buysell") or {})
    expected = incoterm_of(basis)
    actual = text(order.get("incoterm_code"))
    where = f"worksheet {winner} price basis" if winner else ""
    if expected is None and not actual:
        if basis:
            check.rows.append(
                _row(
                    source_id=name,
                    source_table=table,
                    source_field="PriceBasis",
                    source_value=basis,
                    target_model=model,
                    target_field="incoterm",
                    expected=None,
                    actual=None,
                    tolerance=None,
                    result="PASS",
                    classification="unmapped",
                    detail=where or "price basis has no supported Incoterm",
                )
            )
        return
    kwargs = {
        "source_id": name,
        "source_table": table,
        "source_field": "PriceBasis",
        "source_value": basis,
        "target_model": model,
        "target_field": "incoterm",
        "expected": expected or "",
        "actual": actual,
        "tolerance": None,
    }
    if expected and actual == expected:
        check.rows.append(_row(result="PASS", classification="mapped", detail=where, **kwargs))
    else:
        detail = "Incoterm does not match the source price basis"
        if where:
            detail = f"{detail} ({where})"
        check.miss(detail=detail, **kwargs)


def _line_terms(line: dict, side: str) -> tuple[float, str, float, float | None]:
    prefix = "S" if side == "sale" else "P"
    quantity, code = native_quantity(line.get(f"{prefix}Weight"), line.get(f"{prefix}WeightUOM"))
    amount = as_float(line.get(f"{prefix}Amount"))
    price = unit_price(amount, quantity, line.get(f"{prefix}Price"))
    return quantity, code, price, amount


def _lines(check: _Check, kind: str, side: str, model: str, qty_field: str) -> None:
    prefix = "legacy_erp_sol_" if side == "sale" else "legacy_erp_pol_"
    for line in check.odoo.get(kind) or []:
        if not isinstance(line, dict):
            continue
        xmlid = text(line.get("xmlid"))
        if not xmlid.startswith(prefix):
            continue
        token = xmlid.removeprefix(prefix)
        detail = (check.source.get("details_by_token") or {}).get(token)
        detail_id = text((detail or {}).get("DetailID")) or token
        if isinstance(detail, dict) and detail.get("_ambiguous"):
            check.miss(
                source_id=token,
                source_table="WKSDetail",
                source_field="DetailID",
                source_value=None,
                target_model=model,
                target_field=qty_field,
                expected=None,
                actual=line.get("qty"),
                tolerance=None,
                detail="more than one source detail shares this identity token",
            )
            continue
        if not isinstance(detail, dict):
            check.miss(
                source_id=token,
                source_table="WKSDetail",
                source_field="DetailID",
                source_value=None,
                target_model=model,
                target_field=qty_field,
                expected=None,
                actual=line.get("qty"),
                tolerance=None,
                detail="imported line has no source worksheet detail",
            )
            continue
        quantity, code, price, amount = _line_terms(detail, side)
        weight_field = "SWeight" if side == "sale" else "PWeight"
        uom_field = "SWeightUOM" if side == "sale" else "PWeightUOM"
        actual_qty = as_float(line.get("qty"))
        qty_kwargs = {
            "source_id": detail_id,
            "source_table": "WKSDetail",
            "source_field": weight_field,
            "source_value": text(detail.get(weight_field)),
            "target_model": model,
            "target_field": qty_field,
            "expected": quantity,
            "actual": actual_qty,
            "tolerance": QTY_TOLERANCE,
        }
        if actual_qty is None:
            check.miss(detail="quantity was not persisted", **qty_kwargs)
        elif _close(quantity, actual_qty, QTY_TOLERANCE):
            check.rows.append(_row(result="PASS", classification="mapped", detail="", **qty_kwargs))
        else:
            check.miss(detail="quantity conversion differs", **qty_kwargs)
        expected_uom = _UOM_XMLID.get(code)
        actual_uom = text(line.get("uom_xml"))
        if expected_uom:
            check.add(
                source_id=detail_id,
                source_table="WKSDetail",
                source_field=uom_field,
                source_value=text(detail.get(uom_field)),
                target_model=model,
                target_field="product_uom_id",
                expected=expected_uom,
                actual=actual_uom,
                tolerance=None,
            )
        elif actual_uom == "uom.product_uom_unit":
            check.rows.append(
                _row(
                    source_id=detail_id,
                    source_table="WKSDetail",
                    source_field=uom_field,
                    source_value=text(detail.get(uom_field)),
                    target_model=model,
                    target_field="product_uom_id",
                    expected=None,
                    actual=actual_uom,
                    tolerance=None,
                    result="PASS",
                    classification="unmapped",
                    detail="source unit code is not seeded; the product default unit remains",
                )
            )
        elif actual_uom:
            check.miss(
                source_id=detail_id,
                source_table="WKSDetail",
                source_field=uom_field,
                source_value=text(detail.get(uom_field)),
                target_model=model,
                target_field="product_uom_id",
                expected="",
                actual=actual_uom,
                tolerance=None,
                detail="a unit was written for a code the importer does not seed",
            )
        actual_price = as_float(line.get("price"))
        price_kwargs = {
            "source_id": detail_id,
            "source_table": "WKSDetail",
            "source_field": "SAmount" if side == "sale" else "PAmount",
            "source_value": text(detail.get("SAmount" if side == "sale" else "PAmount")),
            "target_model": model,
            "target_field": "price_unit",
            "expected": price,
            "actual": actual_price,
            "tolerance": PRICE_TOLERANCE,
        }
        if actual_price is None:
            check.miss(detail="unit price was not persisted", **price_kwargs)
        elif _close(price, actual_price, PRICE_TOLERANCE):
            check.rows.append(_row(result="PASS", classification="mapped", detail="", **price_kwargs))
        elif (
            amount is not None
            and actual_qty is not None
            and abs(round(actual_qty * actual_price, 2) - round(amount, 2)) <= MONEY_TOLERANCE
        ):
            check.rows.append(
                _row(
                    result="PASS",
                    classification="precision",
                    detail="stored quantity x stored price reproduces the source amount to the cent",
                    **price_kwargs,
                )
            )
        else:
            check.miss(detail="unit price does not reproduce the source amount", **price_kwargs)
        description = text(detail.get("InvoiceDesc"))
        if description:
            check.add(
                source_id=detail_id,
                source_table="WKSDetail",
                source_field="InvoiceDesc",
                source_value=description,
                target_model=model,
                target_field="name",
                expected=description,
                actual=text(line.get("name")),
                tolerance=None,
            )
        if side == "purchase":
            planned = text(line.get("date_planned"))
            order_when = text(line.get("order_date"))
            check.rows.append(
                _row(
                    source_id=detail_id,
                    source_table="PO",
                    source_field="PODate",
                    source_value=order_when,
                    target_model=model,
                    target_field="date_planned",
                    expected=order_when,
                    actual=planned,
                    tolerance=None,
                    result="PASS" if same_when(order_when, planned) else "FAIL",
                    classification="mapped" if same_when(order_when, planned) else "defect",
                    detail="planned date follows the order date",
                )
            )


def _customer_invoices(check: _Check) -> None:
    details_by_worksheet: dict[str, list[dict]] = {}
    for detail in (check.source.get("details") or {}).values():
        if isinstance(detail, dict):
            details_by_worksheet.setdefault(text(detail.get("BuySellNo")), []).append(detail)
    for move in check.odoo.get("invoices") or []:
        if not isinstance(move, dict) or not text(move.get("xmlid")).startswith("legacy_erp_outinv_"):
            continue
        number = text(move.get("invoice_origin")) or text(move.get("xmlid")).removeprefix("legacy_erp_outinv_")
        buysell = (check.source.get("buysell") or {}).get(number)
        if not isinstance(buysell, dict):
            check.miss(
                source_id=number,
                source_table="BuySell",
                source_field="BuySellNo",
                source_value=None,
                target_model="account.move",
                target_field="invoice_origin",
                expected=None,
                actual=number,
                tolerance=None,
                detail="customer invoice has no source worksheet",
            )
            continue
        _document_state(check, number, "BuySell", move)
        invoice_date = text(buysell.get("InvoiceDt"))[:10]
        actual_date = text(move.get("invoice_date"))[:10]
        if not invoice_date and not actual_date:
            check.rows.append(
                _row(
                    source_id=number,
                    source_table="BuySell",
                    source_field="InvoiceDt",
                    source_value=None,
                    target_model="account.move",
                    target_field="invoice_date",
                    expected=None,
                    actual=None,
                    tolerance=None,
                    result="PASS",
                    classification="unmapped",
                    detail="no source invoice date; customer invoice stays undated",
                )
            )
        else:
            check.rows.append(
                _row(
                    source_id=number,
                    source_table="BuySell",
                    source_field="InvoiceDt",
                    source_value=text(buysell.get("InvoiceDt")),
                    target_model="account.move",
                    target_field="invoice_date",
                    expected=invoice_date,
                    actual=actual_date,
                    tolerance=None,
                    result="PASS" if invoice_date == actual_date else "FAIL",
                    classification="mapped" if invoice_date == actual_date else "defect",
                    detail="",
                )
            )
        check.add(
            source_id=number,
            source_table="BuySell",
            source_field="BuySellNo",
            source_value=number,
            target_model="account.move",
            target_field="ref",
            expected=number,
            actual=text(move.get("ref")),
            tolerance=None,
        )
        signed = 0.0
        for detail in details_by_worksheet.get(number) or []:
            quantity, _code, price, _amount = _line_terms(detail, "sale")
            if not quantity:
                quantity = _exact_each_quantity(detail.get("SAmount"), detail.get("SPrice")) or 0.0
                price = as_float(detail.get("SPrice")) or 0.0
            if not quantity:
                continue
            if not sale_line_included(detail, check.source):
                check.rows.append(
                    _row(
                        source_id=text(detail.get("DetailID")),
                        source_table="WKSDetail",
                        source_field="SPO_ID",
                        source_value=text(detail.get("SPO_ID")) or None,
                        target_model="account.move",
                        target_field="amount_total",
                        expected=None,
                        actual=None,
                        tolerance=None,
                        result="PASS",
                        classification="rejected",
                        detail="sale side has no single sale-order header; omitted from the customer invoice",
                    )
                )
                continue
            signed += quantity * price
        move_type = "out_refund" if signed < 0 else "out_invoice"
        check.add(
            source_id=number,
            source_table="WKSDetail",
            source_field="SAmount",
            source_value=round(signed, 2),
            target_model="account.move",
            target_field="move_type",
            expected=move_type,
            actual=text(move.get("move_type")),
            tolerance=None,
        )
        actual_total = as_float(move.get("amount_total"))
        expected_money = round(abs(signed), 2)
        kwargs = {
            "source_id": number,
            "source_table": "WKSDetail",
            "source_field": "SAmount",
            "source_value": round(signed, 2),
            "target_model": "account.move",
            "target_field": "amount_total",
            "expected": expected_money,
            "actual": actual_total,
            "tolerance": MONEY_TOLERANCE,
        }
        if actual_total is None:
            check.miss(detail="invoice total was not persisted", **kwargs)
        elif abs(actual_total - expected_money) <= MONEY_TOLERANCE:
            check.rows.append(_row(result="PASS", classification="mapped", detail="", **kwargs))
        else:
            check.miss(detail="invoice total differs from the converted sale amount", **kwargs)


def _bills(check: _Check) -> None:
    for move in check.odoo.get("bills") or []:
        if not isinstance(move, dict) or not text(move.get("xmlid")).startswith("legacy_erp_ininv_"):
            continue
        token = text(move.get("xmlid")).removeprefix("legacy_erp_ininv_")
        payable = (check.source.get("payables_by_token") or {}).get(token)
        payable_id = text((payable or {}).get("PayableID")) or token
        if not isinstance(payable, dict):
            check.miss(
                source_id=token,
                source_table="Payables",
                source_field="PayableID",
                source_value=None,
                target_model="account.move",
                target_field="amount_total",
                expected=None,
                actual=move.get("amount_total"),
                tolerance=None,
                detail="vendor bill has no source payable",
            )
            continue
        batch = (check.source.get("batches") or {}).get(text(payable.get("APBatchNo"))) or {}
        invoice_date = (text(batch.get("InvoiceDt")) or text(payable.get("InvoiceDt")))[:10]
        actual_date = text(move.get("invoice_date"))[:10]
        if not invoice_date and not actual_date:
            check.rows.append(
                _row(
                    source_id=payable_id,
                    source_table="Payables",
                    source_field="InvoiceDt",
                    source_value=None,
                    target_model="account.move",
                    target_field="invoice_date",
                    expected=None,
                    actual=None,
                    tolerance=None,
                    result="PASS",
                    classification="unmapped",
                    detail="no source invoice date; vendor bill stays undated",
                )
            )
        else:
            passed = invoice_date == actual_date
            check.rows.append(
                _row(
                    source_id=payable_id,
                    source_table="PayablesBatch" if text(batch.get("InvoiceDt")) else "Payables",
                    source_field="InvoiceDt",
                    source_value=text(batch.get("InvoiceDt")) or text(payable.get("InvoiceDt")),
                    target_model="account.move",
                    target_field="invoice_date",
                    expected=invoice_date,
                    actual=actual_date,
                    tolerance=None,
                    result="PASS" if passed else "FAIL",
                    classification="mapped" if passed else "defect",
                    detail="",
                )
            )
        ref = text(batch.get("InvoiceNo")) or text(payable.get("InvoiceNo")) or payable_id
        check.add(
            source_id=payable_id,
            source_table="Payables",
            source_field="InvoiceNo",
            source_value=text(payable.get("InvoiceNo")),
            target_model="account.move",
            target_field="ref",
            expected=ref,
            actual=text(move.get("ref")),
            tolerance=None,
        )
        amount = as_float(payable.get("Amount")) or 0.0
        origin = text(payable.get("BuySellNo"))
        worksheet_details = [
            item
            for item in (check.source.get("details") or {}).values()
            if isinstance(item, dict) and text(item.get("BuySellNo")) == origin
        ]
        signed_purchase, absolute_purchase, any_purchase_line = purchase_bill_absolute(worksheet_details)
        if (
            text(payable.get("GLAcct")) == _MATERIAL_GL
            and any_purchase_line
            and abs(abs(amount) - abs(signed_purchase)) < 0.02
        ):
            expected_money = round(absolute_purchase, 2)
        else:
            expected_money = round(abs(amount), 2)
        check.add(
            source_id=payable_id,
            source_table="Payables",
            source_field="Amount",
            source_value=text(payable.get("Amount")),
            target_model="account.move",
            target_field="move_type",
            expected="in_refund" if amount < 0 else "in_invoice",
            actual=text(move.get("move_type")),
            tolerance=None,
        )
        actual_total = as_float(move.get("amount_total"))
        kwargs = {
            "source_id": payable_id,
            "source_table": "Payables",
            "source_field": "Amount",
            "source_value": text(payable.get("Amount")),
            "target_model": "account.move",
            "target_field": "amount_total",
            "expected": expected_money,
            "actual": actual_total,
            "tolerance": MONEY_TOLERANCE,
        }
        if actual_total is None:
            check.miss(detail="bill total was not persisted", **kwargs)
        elif abs(actual_total - expected_money) <= MONEY_TOLERANCE:
            detail = ""
            if expected_money != round(abs(amount), 2):
                detail = "material bill stores each purchase line as an absolute amount"
            check.rows.append(_row(result="PASS", classification="mapped", detail=detail, **kwargs))
        else:
            check.miss(detail="bill total differs from the purchase lines or the payable amount", **kwargs)
        _document_state(check, payable_id, "Payables", move)
        origin = text(payable.get("BuySellNo"))
        if origin:
            check.add(
                source_id=payable_id,
                source_table="Payables",
                source_field="BuySellNo",
                source_value=origin,
                target_model="account.move",
                target_field="invoice_origin",
                expected=origin,
                actual=text(move.get("invoice_origin")),
                tolerance=None,
            )


def _ledger_moves(check: _Check) -> None:
    for move in check.odoo.get("ledger_moves") or []:
        if not isinstance(move, dict):
            continue
        token = text(move.get("xmlid")).removeprefix("legacy_erp_ledger_")
        row = (check.source.get("ledger_rows") or {}).get(token)
        ledger_id = text((row or {}).get("LedgerID")) or token
        if not isinstance(row, dict):
            check.miss(
                source_id=token,
                source_table="GPLedger",
                source_field="LedgerID",
                source_value=None,
                target_model="account.move",
                target_field="amount_total",
                expected=None,
                actual=move.get("amount_total"),
                tolerance=None,
                detail="ledger document has no source row",
            )
            continue
        kind = ledger_kind(row)
        if kind not in {"customer_credit", "customer_debit"}:
            check.miss(
                source_id=ledger_id,
                source_table="GPLedger",
                source_field="Source",
                source_value=text(row.get("Source")),
                target_model="account.move",
                target_field="move_type",
                expected="not a customer memo",
                actual=text(move.get("move_type")),
                tolerance=None,
                detail=f"a {kind} ledger row was written as a customer document",
            )
            continue
        amount = as_float(row.get("Sale")) or 0.0
        invoice_date = text(row.get("TradeDt"))[:10]
        actual_date = text(move.get("invoice_date"))[:10]
        passed = invoice_date == actual_date or (not invoice_date and not actual_date)
        check.rows.append(
            _row(
                source_id=ledger_id,
                source_table="GPLedger",
                source_field="TradeDt",
                source_value=text(row.get("TradeDt")),
                target_model="account.move",
                target_field="invoice_date",
                expected=invoice_date or None,
                actual=actual_date or None,
                tolerance=None,
                result="PASS" if passed else "FAIL",
                classification="mapped" if invoice_date and passed else "unmapped" if passed else "defect",
                detail="" if invoice_date else "no trade date on the adjustment",
            )
        )
        ref = text(row.get("AdjMemoNo")) or f"GPLedger {ledger_id}"
        check.add(
            source_id=ledger_id,
            source_table="GPLedger",
            source_field="AdjMemoNo",
            source_value=text(row.get("AdjMemoNo")),
            target_model="account.move",
            target_field="ref",
            expected=ref,
            actual=text(move.get("ref")),
            tolerance=None,
        )
        check.add(
            source_id=ledger_id,
            source_table="GPLedger",
            source_field="Sale",
            source_value=text(row.get("Sale")),
            target_model="account.move",
            target_field="move_type",
            expected="out_refund" if kind == "customer_credit" else "out_invoice",
            actual=text(move.get("move_type")),
            tolerance=None,
        )
        actual_total = as_float(move.get("amount_total"))
        kwargs = {
            "source_id": ledger_id,
            "source_table": "GPLedger",
            "source_field": "Sale",
            "source_value": text(row.get("Sale")),
            "target_model": "account.move",
            "target_field": "amount_total",
            "expected": round(abs(amount), 2),
            "actual": actual_total,
            "tolerance": MONEY_TOLERANCE,
        }
        if actual_total is None or abs(actual_total - round(abs(amount), 2)) > MONEY_TOLERANCE:
            check.miss(detail="ledger document amount differs from Sale", **kwargs)
        else:
            check.rows.append(_row(result="PASS", classification="mapped", detail="", **kwargs))
        _document_state(check, ledger_id, "GPLedger", move)


def _document_state(check: _Check, source_id: str, table: str, move: dict) -> None:
    state = text(move.get("state"))
    if state and state != "draft":
        check.miss(
            source_id=source_id,
            source_table=table,
            source_field="state",
            source_value="draft",
            target_model="account.move",
            target_field="state",
            expected="draft",
            actual=state,
            tolerance=None,
            detail="historical accounting document is posted",
        )


def _rejected(rows: list, unresolved) -> None:
    for item in unresolved or []:
        if not isinstance(item, dict):
            continue
        if not (item.get("table") and item.get("kind") and item.get("key")):
            rows.append(
                _row(
                    source_id=text(item.get("key")),
                    source_table=text(item.get("table")),
                    source_field=text(item.get("kind")),
                    source_value=item.get("detail"),
                    target_model="",
                    target_field="",
                    expected=None,
                    actual=None,
                    tolerance=None,
                    result="FAIL",
                    classification="defect",
                    detail="rejected-row evidence is incomplete",
                )
            )
            continue
        rows.append(
            _row(
                source_id=item.get("key"),
                source_table=item.get("table"),
                source_field=item.get("kind"),
                source_value=item.get("detail"),
                target_model="",
                target_field="",
                expected=None,
                actual=None,
                tolerance=None,
                result="PASS",
                classification="rejected",
                detail="source row correctly left unresolved",
            )
        )


def _source_fingerprint(source: dict) -> str:
    """Identity of the source rows compared, without their success-row dump."""
    blob = json.dumps(source, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(blob.encode()).hexdigest()


def evaluate(odoo: dict, source: dict, unresolved=None, *, retain_passes: bool = True) -> dict:
    """Compare one persisted clone snapshot with the source rows it came from."""
    if odoo.get("evidence") != "complete" or source.get("evidence") != "complete":
        reason = (
            text(odoo.get("missing_reason"))
            or text(source.get("missing_reason"))
            or "source or target evidence is incomplete"
        )
        report = finish([], "missing", reason)
        report["source_fingerprint"] = None
        return report
    check = _Check(odoo, source, retain_passes=retain_passes)
    companies = {row.get("partner_id"): row for row in check.companies()}
    for row in check.companies():
        source_id = text(row.get("xmlid")).removeprefix("legacy_erp_cp_")
        source_row = (source.get("counterparties") or {}).get(source_id)
        if not isinstance(source_row, dict):
            check.miss(
                source_id=source_id,
                source_table="CounterParty",
                source_field="CpID",
                source_value=None,
                target_model="res.partner",
                target_field="name",
                expected=None,
                actual=text(row.get("name")),
                tolerance=None,
                detail="imported counterparty has no source row",
            )
            continue
        if not text(source_row.get("CompanyNm")):
            check.miss(
                source_id=source_id,
                source_table="CounterParty",
                source_field="CompanyNm",
                source_value="",
                target_model="res.partner",
                target_field="name",
                expected="rejected blank name",
                actual=text(row.get("name")),
                tolerance=None,
                detail="a blank company name was imported",
            )
            continue
        _partner_fields(check, row, source_row, source_id)
    seen_company_billing: set[int] = set()
    for xmlid, row in check.partners.items():
        if not xmlid.startswith("legacy_erp_address_"):
            continue
        address_id = xmlid.removeprefix("legacy_erp_address_")
        source_row = (source.get("addresses") or {}).get(address_id)
        if not isinstance(source_row, dict):
            check.miss(
                source_id=address_id,
                source_table="Address",
                source_field="AddressID",
                source_value=None,
                target_model="res.partner",
                target_field="street",
                expected=None,
                actual=text(row.get("street")),
                tolerance=None,
                detail="imported address has no source row",
            )
            continue
        company = companies.get(row.get("partner_id"))
        if company is not None:
            if row.get("partner_id") in seen_company_billing:
                continue
            seen_company_billing.add(row.get("partner_id"))
            cp_id = text(company.get("xmlid")).removeprefix("legacy_erp_cp_")
            candidates = [
                (item_id, item)
                for item_id, item in (source.get("addresses") or {}).items()
                if isinstance(item, dict) and text(item.get("CpID")) == cp_id
            ]
            _address_fields(check, row, {}, "", company, candidates)
        else:
            _address_fields(check, row, source_row, address_id, None)
    _contacts(check)
    _orders(check)
    _lines(check, "sale_lines", "sale", "sale.order.line", "product_uom_qty")
    _lines(check, "purchase_lines", "purchase", "purchase.order.line", "product_qty")
    _customer_invoices(check)
    _bills(check)
    _ledger_moves(check)
    _rejected(check.rows, unresolved)
    report = finish(check.rows, "complete", "")
    report["source_fingerprint"] = _source_fingerprint(source)
    if not retain_passes:
        report["rows_retained"] = "failures"
    return report


def finish(rows, evidence: str, missing_reason: str) -> dict:
    if isinstance(rows, _Rows):
        stored = rows.rows
        compared_n = rows.compared
        failed_n = rows.failed
        rejected_n = rows.rejected
        unmapped_n = rows.unmapped
        precision_n = rows.precision
    else:
        stored = list(rows)
        failed_rows = [row for row in stored if row.get("result") == "FAIL"]
        compared_rows = [
            row
            for row in stored
            if row.get("result") == "PASS" and row.get("classification") in {"mapped", "precision"}
        ]
        compared_n = len(compared_rows)
        failed_n = len(failed_rows)
        rejected_n = sum(1 for row in stored if row.get("classification") == "rejected")
        unmapped_n = sum(1 for row in stored if row.get("classification") == "unmapped")
        precision_n = sum(1 for row in stored if row.get("classification") == "precision")
    if evidence != "complete":
        status = "FAIL"
        if failed_n == 0:
            stored = [
                _row(
                    source_id="",
                    source_table="",
                    source_field="",
                    source_value=None,
                    target_model="",
                    target_field="",
                    expected=None,
                    actual=None,
                    tolerance=None,
                    result="FAIL",
                    classification="defect",
                    detail=missing_reason or "source or target evidence is incomplete",
                )
            ]
            failed_n = 1
    elif failed_n or not compared_n:
        status = "FAIL"
        evidence = "complete" if compared_n or failed_n else "missing"
        if not compared_n and not failed_n:
            missing_reason = missing_reason or "no mapped field was compared"
            evidence = "missing"
    else:
        status = "PASS"
    return {
        "schema": SCHEMA,
        "evidence": evidence,
        "status": status,
        "missing_reason": missing_reason,
        "compared": compared_n,
        "failed": failed_n,
        "rejected": rejected_n,
        "unmapped": unmapped_n,
        "precision": precision_n,
        "rows": stored,
        "coverage": COVERAGE,
    }


def fixture_bundles() -> tuple[dict, dict]:
    """One consistent clone snapshot and its source rows, for the kit tests."""
    odoo = {
        "evidence": "complete",
        "partners": [
            {
                "xmlid": "legacy_erp_cp_10",
                "partner_id": 10,
                "name": "Acme",
                "ref": "C10",
                "email": "a@b.com",
                "website": "https://acme.example",
                "active": True,
                "supplier_rank": 1,
                "customer_rank": 0,
                "company_role": "supplier",
                "credit_limit": 500,
                "street": "1 Main",
                "street2": "",
                "city": "Austin",
                "zip": "78701",
                "is_company": True,
                "parent_id": None,
            },
            {
                "xmlid": "legacy_erp_address_70",
                "partner_id": 10,
                "name": "Acme",
                "street": "1 Main",
                "street2": "",
                "city": "Austin",
                "zip": "78701",
                "is_company": True,
                "parent_id": None,
                "active": True,
            },
            {
                "xmlid": "legacy_erp_address_77",
                "partner_id": 77,
                "name": "Yard",
                "street": "9 Dock",
                "street2": "",
                "city": "Austin",
                "zip": "78702",
                "is_company": True,
                "parent_id": 10,
                "active": True,
            },
            {
                "xmlid": "legacy_erp_contact_5",
                "partner_id": 5,
                "name": "Ann Lee",
                "email": "ann@b.com",
                "is_company": False,
                "parent_id": 10,
                "active": True,
            },
        ],
        "sale_orders": [
            {
                "xmlid": "legacy_erp_so_PO100",
                "name": "PO100",
                "origin": "100",
                "date_order": "2024-03-01 00:00:00",
                "client_order_ref": "REF",
                "incoterm_code": "",
                "state": "draft",
            }
        ],
        "purchase_orders": [
            {
                "xmlid": "legacy_erp_po_PO200",
                "name": "PO200",
                "origin": "100",
                "date_order": "2024-03-01 00:00:00",
                "date_approve": "2024-03-02 06:00:00",
                "incoterm_code": "",
                "state": "draft",
            }
        ],
        "sale_lines": [
            {
                "xmlid": "legacy_erp_sol_900",
                "qty": 2000,
                "price": 0.5,
                "name": "HDPE",
                "uom_xml": "uom.product_uom_lb",
            }
        ],
        "purchase_lines": [
            {
                "xmlid": "legacy_erp_pol_900",
                "qty": 400,
                "price": 1,
                "name": "HDPE",
                "uom_xml": "uom.product_uom_lb",
                "date_planned": "2024-03-01 00:00:00",
                "order_date": "2024-03-01 00:00:00",
            }
        ],
        "invoices": [
            {
                "xmlid": "legacy_erp_outinv_100",
                "move_type": "out_invoice",
                "invoice_date": "2024-03-04",
                "invoice_origin": "100",
                "ref": "100",
                "amount_total": 1000,
                "state": "draft",
            }
        ],
        "bills": [
            {
                "xmlid": "legacy_erp_ininv_55",
                "move_type": "in_invoice",
                "invoice_date": "2024-03-05",
                "invoice_origin": "100",
                "ref": "INV9",
                "amount_total": 400,
                "state": "draft",
            }
        ],
        "ledger_moves": [],
    }
    source = {
        "evidence": "complete",
        "counterparties": {
            "10": {
                "CpID": "10",
                "CompanyNm": "Acme",
                "Role": "V",
                "ActiveStatus": "A",
                "OurCustNo": "C10",
                "APEMail": "a@b.com",
                "WebSite": "acme.example",
                "CreditLimit": "500",
            }
        },
        "addresses": {
            "70": {
                "AddressID": "70",
                "CpID": "10",
                "Type": "INVOICE",
                "Addr2": "1 Main",
                "City": "Austin",
                "PostalCd": "78701",
                "RemitToAddress": "1",
            },
            "77": {
                "AddressID": "77",
                "CpID": "10",
                "Type": "DELIVERY ADDRESS",
                "Addr2": "9 Dock",
                "City": "Austin",
                "PostalCd": "78702",
            },
        },
        "contacts": {"5": {"CT_ID": "5", "CpID": "10", "ContactNm": "Ann Lee", "Email": "ann@b.com", "IsActive": "Y"}},
        "details": {
            "900": {
                "DetailID": "900",
                "BuySellNo": "100",
                "InvoiceDesc": "HDPE",
                "SWeight": "1",
                "SWeightUOM": "S",
                "SPrice": "1000",
                "SAmount": "1000",
                "SPO_ID": "SO900",
                "PWeight": "400",
                "PWeightUOM": "L",
                "PPrice": "1",
                "PAmount": "400",
            }
        },
        "details_by_token": {},
        "orders": {
            "PO100|SO": {
                "PONumber": "PO100",
                "Source": "SO",
                "PODate": "2024-03-01 00:00:00",
                "POReference": "REF",
                "PriceBasis": "fob",
            },
            "PO200|PO": {"PONumber": "PO200", "Source": "PO", "PODate": "2024-03-01 00:00:00", "PriceBasis": "fob"},
        },
        "order_lines": {"SO900": "PO100"},
        "sale_header_count": {"PO100": 1},
        "buysell": {
            "100": {
                "BuySellNo": "100",
                "InvoiceDt": "2024-03-04 00:00:00",
                "OrderDt": "2024-03-01 00:00:00",
                "PriceBasis": "fob",
            }
        },
        "ledger": {"100": ["2024-03-02 06:00:00"]},
        "ledger_rows": {},
        "payables_by_token": {
            "55": {
                "PayableID": "55",
                "BuySellNo": "100",
                "Amount": "400",
                "InvoiceDt": "2024-03-05",
                "InvoiceNo": "INV9",
                "APBatchNo": "B1",
            }
        },
        "batches": {"B1": {"APBatchNo": "B1", "InvoiceDt": "2024-03-05", "InvoiceNo": "INV9"}},
    }
    source["details_by_token"]["900"] = source["details"]["900"]
    return odoo, source
