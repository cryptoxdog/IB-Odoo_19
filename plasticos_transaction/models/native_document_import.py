"""Write sale orders, purchase orders, invoices, and bills from the ERP source index.

The importer does not create a transaction record. Confirming the sale order
lets the sales hook compile one per worksheet. Source identity is
``ir.model.data``. A second run finds the same documents and writes nothing.

Historical documents are left in draft. QuickBooks owns their settlement; the
import creates no payment, no clearing entry, and no posted balance.
"""

from __future__ import annotations

import logging

from odoo import Command

_logger = logging.getLogger(__name__)

XMLID_MODULE = "plasticos_transaction"
# L pounds, E each. E is a count (gaylords), not a ton. S (short ton, 2,000 lb)
# is converted to pounds by ``native_quantity``: Odoo's seeded ton is metric.
_UOM_XMLID = {"L": "uom.product_uom_lb", "E": "uom.product_uom_unit"}
_PRODUCT_PRICE = "Product Price"
_OPEN_SALE_STATES = ("draft", "sent")
_OPEN_PURCHASE_STATES = ("draft", "sent", "to approve")


def realize(importer, index, report, partner_by_cp, limit, commit, dry_run) -> bool:
    """Realize native documents. Returns true so the caller does not commit twice.

    Every indexed payable leaves this function on exactly one side of the
    census: written as a native bill, quarantined with its identity and
    reason, or excluded by name (a diagnostic limit, a dry run). The run
    never returns before that accounting is complete.
    """
    from odoo.addons.plasticos_partner_import.erp.native_orders import (  # noqa: PLC0415
        reconciliation_gap,
        selected_worksheets,
    )
    from odoo.addons.plasticos_partner_import.erp.summary import PAYABLES_RECONCILIATION_REF  # noqa: PLC0415

    numbers = index.buysell_numbers()
    context = _load_context(importer)
    if not index.orders:
        # The source carries no order header at all, so no worksheet can
        # link to a native document. Nothing is written; every worksheet is
        # skipped and every one of its payables is reported on its own.
        for number in numbers:
            report.skip("transactions")
            report.skip("transaction_lines", len(index.detail_ids(number)))
            _quarantine_worksheet_payables(
                index,
                context,
                report,
                number,
                "source carries no order headers; no document to attach the bill to",
                "no_order_link_not_realized",
            )
        selected_set = set(numbers)
    else:
        selected = selected_worksheets(numbers, limit)
        selected_set = set(selected)
        pending_sales: dict[int, list[str]] = {}
        for position, number in enumerate(selected, start=1):
            if dry_run:
                report.skip("transactions")
                report.skip("transaction_lines", len(index.detail_ids(number)))
                _exclude_worksheet_payables(index, context, number, "dry_run")
                continue
            try:
                with importer.env.cr.savepoint():
                    sale_ids, trailers = _realize_one(importer, index, report, partner_by_cp, context, number)
            except Exception as exc:  # noqa: BLE001 - one worksheet must not abort the load
                _logger.info("ERP worksheet %s was not written: %s", number, exc)
                report.anomaly("BuySell", number, type(exc).__name__)
                report.reject("transactions")
                report.reject("transaction_lines", len(index.detail_ids(number)))
                _discard_worksheet(context, number)
                # Everything the attempt routed was rolled back with it; the
                # worksheet's payables are quarantined afresh so each one is
                # reported and the reconciliation still covers them.
                _quarantine_worksheet_payables(
                    index,
                    context,
                    report,
                    number,
                    f"worksheet rolled back ({type(exc).__name__}); no document of it exists",
                    "worksheet_rolled_back_not_realized",
                )
                continue
            for sale_id in sale_ids:
                pending_sales.setdefault(sale_id, []).extend(trailers)
            if commit and position % 200 == 0:
                _confirm_sales(importer, report, pending_sales, context)
                pending_sales.clear()
                importer.env.cr.commit()
                _logger.info("ERP import committed through worksheet %s", position)
        if not dry_run:
            _confirm_sales(importer, report, pending_sales, context)
    for number in numbers:
        if number in selected_set:
            continue
        report.skip("transactions")
        report.skip("transaction_lines", len(index.detail_ids(number)))
        _exclude_worksheet_payables(index, context, number, "diagnostic_limit")
    _quarantine_outside_universe(importer, index, report, context, partner_by_cp, numbers, dry_run)
    report.census = _census(index, context)
    reconciliation = report.census["payables_reconciliation"]
    if not reconciliation["closes"]:
        # The identity reconciliation is mandatory: a gap is a failure of the
        # run (summary ``failed``, nonzero exit), reported as itself. No row
        # is relabelled to balance it; the census keeps every exception.
        gap = reconciliation_gap(reconciliation)
        report.anomaly("Payables", "reconciliation", gap)
        report.fail(PAYABLES_RECONCILIATION_REF, f"payables identity reconciliation does not close: {gap}")
    if commit and not dry_run:
        importer.env.cr.commit()
    return True


def _discard_worksheet(context, number: str) -> None:
    """Forget everything a rolled-back worksheet routed: its documents, bills, pending verdicts and rows."""
    context["documents"].pop(number, None)
    context["rejected"].add(number)
    context["pending_transactions"].pop(number, None)
    context["pending_costs"].pop(number, None)
    context["billed_payables"] = [item for item in context["billed_payables"] if item[0] != number]
    context["expense_rows"] = [item for item in context["expense_rows"] if item[0] != number]
    context["quarantine"] = [entry for entry in context["quarantine"] if entry["worksheet"] != number]


def _exclude_worksheet_payables(index, context, number: str, reason: str) -> None:
    """A worksheet the run deliberately did not visit: its payables are named as excluded, never claimed."""
    from odoo.addons.plasticos_partner_import.erp.native_orders import payable_identity  # noqa: PLC0415

    for row in index.payables_by_buysell.get(number, []):
        context["excluded_payables"].append((number, payable_identity(row), reason, _qty(row.get("Amount"))))


def _census(index, context) -> dict:
    """Source exceptions of this run, grouped by root cause with their dollar exposure."""
    from odoo.addons.plasticos_partner_import.erp.native_orders import (  # noqa: PLC0415
        link_census,
        payables_reconciliation,
        source_payable_identities,
    )

    inventory_rows = list(context.get("inventory_inbound") or [])
    inventory_numbers = {row["number"] for row in inventory_rows}
    commercial_links = {
        number: flags
        for number, flags in (context.get("worksheet_links") or {}).items()
        if number not in inventory_numbers
    }
    commercial_failures = [
        failure
        for failure in (context.get("link_failures") or [])
        if failure.get("number") not in inventory_numbers or failure.get("side") != "sale"
    ]
    census = link_census(index, commercial_failures, commercial_links)
    census["inventory_inbound"] = _inventory_inbound_census(inventory_rows)
    drift = dict(context.get("price_drift") or _new_price_drift(context.get("price_digits")))
    drift["display_digits"] = context.get("display_digits")
    drift["net_drift"] = round(drift["net_drift"], 2)
    drift["abs_drift"] = round(drift["abs_drift"], 2)
    drift["max_abs_drift"] = round(drift["max_abs_drift"], 2)
    census["price_precision"] = drift
    rejected = context.get("rejected") or set()
    tallies: dict[str, dict] = {}
    for number, bucket, amount in context.get("expense_rows") or []:
        tally = tallies.setdefault(bucket, {"rows": 0, "worksheets": set(), "amount": 0.0})
        tally["rows"] += 1
        tally["worksheets"].add(number)
        tally["amount"] += amount
    census["payables"] = {
        key: {"rows": tally["rows"], "worksheets": len(tally["worksheets"]), "amount": round(tally["amount"], 2)}
        for key, tally in sorted(tallies.items())
    }
    quarantine = sorted(context.get("quarantine") or [], key=lambda entry: (entry["worksheet"], entry["payable_id"]))
    census["unresolved_bills"] = quarantine
    excluded = context.get("excluded_payables") or []
    census["payables_reconciliation"] = payables_reconciliation(
        context.get("expense_rows") or [],
        quarantine,
        source_ids=source_payable_identities(index),
        billed_ids=[identity for _number, identity in context.get("billed_payables") or []],
        excluded_ids=[identity for _number, identity, _reason, _amount in excluded],
    )
    # Payables of worksheets the run deliberately did not visit (a diagnostic
    # limit, a dry run) are neither billed nor quarantined; they are named
    # here, by reason, so the exclusion never hides them and the identity
    # reconciliation above still accounts for them.
    by_reason: dict[str, dict] = {}
    for _number, _identity, reason, amount in excluded:
        tally = by_reason.setdefault(reason, {"rows": 0, "amount": 0.0})
        tally["rows"] += 1
        tally["amount"] += amount
    census["payables_excluded"] = {
        "rows": len(excluded),
        "amount": round(sum(item[3] for item in excluded), 2),
        "by_reason": {
            reason: {"rows": tally["rows"], "amount": round(tally["amount"], 2)}
            for reason, tally in sorted(by_reason.items())
        },
    }
    limited = census["payables_excluded"]["by_reason"].get("diagnostic_limit")
    census["payables_unselected"] = dict(limited) if limited else {"rows": 0, "amount": 0.0}
    census["worksheets_rejected"] = sorted(rejected)
    return census


def _new_price_drift(digits, quantity_digits=None) -> dict:
    return {
        "digits": digits,
        "quantity_digits": quantity_digits,
        "display_digits": None,
        "lines": 0,
        "net_drift": 0.0,
        "abs_drift": 0.0,
        "max_abs_drift": 0.0,
    }


def _stored_digits(env, model_name: str, field_name: str):
    """Decimal places a stored ``Float`` field rounds to, or ``None`` when it keeps the full value."""
    digits = env[model_name]._fields[field_name].get_digits(env)
    return digits[1] if digits else None


def _load_context(importer) -> dict:
    """Accounts and journals the documents post to. No company, account, or product setting is written."""
    env = importer.env
    material = env.ref("plasticos_accounting.account_50100_material_cost", raise_if_not_found=False)
    income = env.ref("plasticos_accounting.account_40050_sales_income", raise_if_not_found=False)
    freight = env.ref("plasticos_accounting.account_50200_freight_cost", raise_if_not_found=False)
    if not freight:
        freight = (
            env["account.account"].search(
                [("code", "=", "50200"), ("account_type", "=", "expense_direct_cost")], limit=1
            )
            or None
        )
    # Storage precision of the document line fields, read from the fields
    # themselves: ``None`` when the field keeps the full value (Odoo 19
    # ``price_unit`` is declared with ``min_display_digits`` only).
    price_digits = _stored_digits(env, "account.move.line", "price_unit")
    quantity_digits = _stored_digits(env, "account.move.line", "quantity")
    return {
        "material_account": material,
        "income_account": income,
        "freight_account": freight,
        "sale_journal": env["account.journal"].search([("type", "=", "sale")], limit=1),
        "purchase_journal": env["account.journal"].search([("type", "=", "purchase")], limit=1),
        "product_cache": {},
        "uom_cache": {},
        "incoterm_cache": {},
        "payment_term_cache": {},
        "documents": {},
        "price_digits": price_digits,
        "quantity_digits": quantity_digits,
        "display_digits": env["decimal.precision"].precision_get(_PRODUCT_PRICE),
        "price_drift": _new_price_drift(price_digits, quantity_digits),
        "link_failures": [],
        "worksheet_links": {},
        "expense_rows": [],
        "quarantine": [],
        # Identity of every payable written as a native bill, per worksheet.
        "billed_payables": [],
        # (worksheet, PayableID, reason, amount) of rows the run deliberately did not visit.
        "excluded_payables": [],
        # Worksheets whose transaction verdict waits for the sale order to be
        # confirmed and its transaction compiled: number -> sale order ids.
        "pending_transactions": {},
        # Payable rows whose disposition depends on that verdict.
        "pending_costs": {},
        "rejected": set(),
        # (INV) worksheet outcomes. The commercial sale-link census does not
        # count these worksheets a second time.
        "inventory_inbound": [],
    }


def _new_documents() -> dict:
    return {"sales": [], "purchases": [], "invoice": False, "credits": [], "bills": [], "freight_bills": []}


def _header_for_posted_number(index, number, source):
    """One ``PO`` header whose number is the worksheet's posted order number, or ``None``.

    ``WKSDetail.PPo`` is that number. Zero headers and several headers stay unresolved.
    """
    number = (number or "").strip()
    if not number:
        return None
    matches = index.orders_by_source_number.get((source, number), [])
    if len(matches) != 1:
        return None
    return index.orders.get(matches[0])


def _realize_one(importer, index, report, partner_by_cp, context, number):
    from odoo.addons.plasticos_partner_import.erp.header_forensics import trade_date  # noqa: PLC0415
    from odoo.addons.plasticos_partner_import.erp.native_orders import (  # noqa: PLC0415
        header_for_line,
        incoterm_code,
        worksheet_log,
        worksheet_outcome,
    )

    buysell = index.buysells.get(number, {})
    documents = _new_documents()
    context["documents"][number] = documents
    _remember_salesperson(importer, report, context, number, buysell)
    context.setdefault("notes", {})[number] = worksheet_log(
        buysell.get("ProblemNotes"), buysell.get("Notes"), buysell.get("BookingNo")
    )
    context.setdefault("states", {})[number] = worksheet_outcome(buysell.get("status"))
    context.setdefault("raw_states", {})[number] = (buysell.get("status") or "").strip()
    context.setdefault("order_days", {})[number] = (_date(buysell.get("OrderDt")) or "")[:10]
    context.setdefault("trade_dates", {})[number] = trade_date(index, number)
    _remember_carrier(importer, context, partner_by_cp, number, index.deliveries_by_buysell.get(number, []))
    sale_groups: dict[str, list] = {}
    purchase_groups: dict[str, list] = {}
    line_outcomes = []
    links = context["worksheet_links"].setdefault(number, {"sale": False, "purchase": False})
    for detail_id in index.detail_ids(number):
        line = index.lines[detail_id]
        sale_key = (line.get("SPO_ID") or "").strip()
        purchase_key = (line.get("PPO_ID") or "").strip()
        sale_header, sale_reason = header_for_line(index, sale_key, "SO")
        purchase_header, purchase_reason = header_for_line(index, purchase_key, "PO")
        # PPO_ID is the line key. When it does not resolve, the worksheet still
        # carries the purchase-order number it was opened from (PPo).
        if purchase_header is None:
            purchase_header = _header_for_posted_number(index, line.get("PPo"), "PO")
        # Each side that resolves no header is recorded with its own reason, so
        # a line that still links on the other side is not a silent half-link.
        for side, key, header, reason in (
            ("sale", sale_key, sale_header, sale_reason),
            ("purchase", purchase_key, purchase_header, purchase_reason),
        ):
            if header is None:
                context["link_failures"].append(
                    {"number": number, "detail_id": detail_id, "side": side, "key": key, "reason": reason}
                )
                report.anomaly("WKSDetail", detail_id, f"{side} link: {reason}")
        if sale_header is None and purchase_header is None:
            line_outcomes.append("rejected")
            continue
        if sale_header is not None:
            links["sale"] = True
            sale_groups.setdefault(sale_header["POID"], []).append((detail_id, line, sale_header))
        if purchase_header is not None:
            links["purchase"] = True
            purchase_groups.setdefault(purchase_header["POID"], []).append((detail_id, line, purchase_header))
        line_outcomes.append(detail_id)

    if _is_inventory_customer(buysell):
        return _realize_inventory_inbound(
            importer,
            index,
            report,
            partner_by_cp,
            context,
            number,
            buysell,
            purchase_groups,
            line_outcomes,
        )

    if not sale_groups and not purchase_groups:
        report.reject("transactions")
        report.reject("transaction_lines", len(line_outcomes) or len(index.detail_ids(number)))
        # No native document can own this worksheet's bills; each payable is
        # reported on its own so the reconciliation covers it.
        _quarantine_worksheet_payables(
            index,
            context,
            report,
            number,
            "worksheet has no valid sale or purchase order link; no document to attach the bill to",
            "no_order_link_not_realized",
        )
        return [], []
    if not sale_groups:
        # No native sale order can be compiled, so no transaction exists for the
        # worksheet. Its purchase documents and vendor bills are still realized
        # on their own identity; nothing manufactures a sale order for it, and
        # the worksheet is counted as a rejected transaction, never a created one.
        report.anomaly("BuySell", number, "no sale order link: purchase documents realized, no transaction compiled")

    trailers = _trailers(index, number)
    new_lines: set[str] = set()
    for _po_id, rows in sale_groups.items():
        header = rows[0][2]
        xml_id = f"legacy_erp_so_{_token(header.get('PONumber'))}"
        order = _upsert_order(
            importer, context, report, partner_by_cp, header, buysell, number, "sale.order", xml_id, incoterm_code
        )
        if order is not None:
            documents["sales"].append(order.id)
            for detail_id, line, _header in rows:
                if (
                    order.state in _OPEN_SALE_STATES
                    and _existing(importer, "sale.order.line", f"legacy_erp_sol_{_token(detail_id)}") is None
                ):
                    new_lines.add(detail_id)
                _upsert_sale_line(importer, context, report, order, detail_id, line)
    if len(documents["sales"]) > 1:
        report.anomaly("BuySell", number, f"worksheet carries {len(documents['sales'])} sale orders")
    _realize_purchase_groups(
        importer, context, report, partner_by_cp, buysell, number, purchase_groups, documents, new_lines, incoterm_code
    )
    invoice = _customer_invoice(importer, report, context, partner_by_cp, number, buysell, sale_groups)
    documents["invoice"] = invoice.id if invoice is not None else False
    _customer_adjustments(importer, index, report, context, partner_by_cp, number, invoice, documents)
    _vendor_bills(importer, index, report, context, partner_by_cp, number, documents)
    if not sale_groups:
        report.reject("transactions")
    else:
        # A linked sale order is not a transaction. The verdict (created,
        # skipped, rejected) is settled in ``_settle_transactions`` once the
        # order has been confirmed and its transaction compiled, or not.
        context["pending_transactions"][number] = list(documents["sales"])
    for outcome in line_outcomes:
        if outcome == "rejected":
            report.bump("transaction_lines", "rejected")
        else:
            report.bump("transaction_lines", "created" if outcome in new_lines else "skipped")
    return list(documents["sales"]), trailers


_INVENTORY_RECOGNIZED = "recognized"
_INVENTORY_HELD_PURCHASE = "held_missing_purchase"
_INVENTORY_HELD_DESTINATION = "held_missing_destination"
_INVENTORY_CANCELLED = "cancelled"
_INVENTORY_CANCELLED_REASON = "inventory inbound cancelled"
_INVENTORY_HELD_PURCHASE_REASON = "inventory inbound held: missing purchase"
_INVENTORY_HELD_DESTINATION_REASON = "inventory inbound held: missing destination"


def _is_inventory_customer(buysell) -> bool:
    from odoo.addons.plasticos_partner_import.erp.source_index import (  # noqa: PLC0415
        INVENTORY_COUNTERPARTY,
    )

    return (buysell.get("CustID") or "").strip() == INVENTORY_COUNTERPARTY


def _inventory_inbound_census(rows: list[dict]) -> dict:
    grouped = {
        _INVENTORY_RECOGNIZED: [],
        _INVENTORY_HELD_PURCHASE: [],
        _INVENTORY_HELD_DESTINATION: [],
        _INVENTORY_CANCELLED: [],
    }
    for row in rows:
        grouped[row["outcome"]].append(
            {
                "number": row["number"],
                "address_id": row["address_id"],
                "location_xmlid": row["location_xmlid"],
            }
        )
    return {key: sorted(grouped[key], key=lambda item: item["number"]) for key in grouped}


def _record_inventory(context, number: str, outcome: str, address_id: str, location_xmlid: str) -> None:
    context["inventory_inbound"].append(
        {
            "number": number,
            "outcome": outcome,
            "address_id": address_id,
            "location_xmlid": location_xmlid,
        }
    )


def _drop_expected_inventory_sale_link(index, report, context, number: str) -> None:
    """A missing customer SO is the inventory case, not a commercial sale-link failure."""
    detail_ids = set(index.detail_ids(number))
    context["link_failures"] = [
        failure
        for failure in context["link_failures"]
        if not (failure.get("number") == number and failure.get("side") == "sale")
    ]
    report.anomalies = [
        item
        for item in report.anomalies
        if not (item["key"] in detail_ids and str(item["detail"]).startswith("sale link:"))
    ]


def _bump_inventory_lines(report, line_outcomes, new_lines: set[str], written_lines: set[str]) -> None:
    """Count only purchase lines that were stored. A sale-only line is not a skipped purchase."""
    for outcome in line_outcomes:
        if outcome == "rejected" or outcome not in written_lines:
            report.bump("transaction_lines", "rejected")
        else:
            report.bump("transaction_lines", "created" if outcome in new_lines else "skipped")


def _realize_purchase_groups(
    importer, context, report, partner_by_cp, buysell, number, purchase_groups, documents, new_lines, incoterm_code
) -> set[str]:
    written: set[str] = set()
    for _po_id, rows in purchase_groups.items():
        header = rows[0][2]
        xml_id = f"legacy_erp_po_{_token(header.get('PONumber'))}"
        order = _upsert_order(
            importer, context, report, partner_by_cp, header, buysell, number, "purchase.order", xml_id, incoterm_code
        )
        if order is None:
            continue
        documents["purchases"].append(order.id)
        for detail_id, line, _header in rows:
            existing_line = _existing(importer, "purchase.order.line", f"legacy_erp_pol_{_token(detail_id)}")
            if order.state not in _OPEN_PURCHASE_STATES:
                if existing_line is not None:
                    _fill_existing_line(
                        importer,
                        context,
                        report,
                        "purchase.order.line",
                        f"legacy_erp_pol_{_token(detail_id)}",
                        detail_id,
                        line,
                    )
                    written.add(detail_id)
                continue
            if existing_line is None:
                new_lines.add(detail_id)
            _upsert_purchase_line(importer, context, report, order, detail_id, line)
            written.add(detail_id)
    return written


def _inventory_location(importer, index, address_id: str):
    """The source-keyed inbound site. Created under the company's warehouse stock location.

    Replay only refreshes the label: the parent and company an existing site
    already has are never rewritten from the ambient company.
    """
    row = index.inventory_destinations.get(address_id) or index.addresses.get(address_id) or {}
    label = (row.get("Type") or "").strip() or f"ERP inventory {address_id}"
    xml_id = f"legacy_erp_inv_addr_{_token(address_id)}"
    model = importer.env["stock.location"].with_context(**_import_context())
    values = {"name": label}
    if _existing(importer, model._name, xml_id) is None:
        company = importer.env.company
        warehouse = importer.env["stock.warehouse"].search([("company_id", "=", company.id)], order="id", limit=1)
        if not warehouse.lot_stock_id:
            raise ValueError(f"company {company.name} has no warehouse stock location to hold inventory {address_id}")
        values.update({"usage": "internal", "company_id": company.id, "location_id": warehouse.lot_stock_id.id})
    return importer._upsert(model, xml_id, values, _silent(), None)


def _bind_inventory_worksheet(importer, number: str, location) -> None:
    """Point the worksheet marker at the resolved site, including after a ShipToID correction."""
    xml_id = f"legacy_erp_inv_wks_{_token(number)}"
    model = importer.env["stock.location"]
    data = importer.env["ir.model.data"].search(
        [("module", "=", XMLID_MODULE), ("name", "=", xml_id), ("model", "=", model._name)],
        limit=1,
    )
    if data and data.res_id == location.id and model.browse(data.res_id).exists():
        return
    if data:
        data.write({"res_id": location.id})
        return
    importer._ensure_identity_marker(model, xml_id, location)


def _keep_inventory_destination(importer, index, number: str, address_id: str) -> str:
    location = _inventory_location(importer, index, address_id)
    _bind_inventory_worksheet(importer, number, location)
    return f"legacy_erp_inv_addr_{_token(address_id)}"


def _realize_inventory_inbound(
    importer, index, report, partner_by_cp, context, number, buysell, purchase_groups, line_outcomes
):
    """Draft purchase and a location marker. No sale, invoice, quant, or transaction."""
    from odoo.addons.plasticos_partner_import.erp.native_orders import (  # noqa: PLC0415
        WORKSHEET_CANCELLED,
        incoterm_code,
        worksheet_outcome,
    )

    _drop_expected_inventory_sale_link(index, report, context, number)
    matches = index.inventory_destination_ids(buysell.get("CustID"), buysell.get("ShipToID"))
    destination = matches[0] if len(matches) == 1 else ""
    documents = context["documents"][number]
    if worksheet_outcome(buysell.get("status")) == WORKSHEET_CANCELLED:
        _record_inventory(context, number, _INVENTORY_CANCELLED, "", "")
        report.anomaly("BuySell", number, _INVENTORY_CANCELLED_REASON)
        report.reject("transactions")
        _bump_inventory_lines(report, line_outcomes, set(), set())
        _quarantine_worksheet_payables(
            index,
            context,
            report,
            number,
            "inventory inbound cancelled; no stock event and no new purchase document",
            "no_order_link_not_realized",
        )
        return [], []
    if not purchase_groups:
        location_xmlid = _keep_inventory_destination(importer, index, number, destination) if destination else ""
        _record_inventory(context, number, _INVENTORY_HELD_PURCHASE, destination, location_xmlid)
        report.anomaly("BuySell", number, _INVENTORY_HELD_PURCHASE_REASON)
        report.reject("transactions")
        _bump_inventory_lines(report, line_outcomes, set(), set())
        _quarantine_worksheet_payables(
            index,
            context,
            report,
            number,
            "inventory inbound has no purchase order; no document to attach the bill to",
            "no_order_link_not_realized",
        )
        return [], []
    new_lines: set[str] = set()
    written_lines = _realize_purchase_groups(
        importer, context, report, partner_by_cp, buysell, number, purchase_groups, documents, new_lines, incoterm_code
    )
    _vendor_bills(importer, index, report, context, partner_by_cp, number, documents)
    if not destination:
        _record_inventory(context, number, _INVENTORY_HELD_DESTINATION, "", "")
        report.anomaly("BuySell", number, _INVENTORY_HELD_DESTINATION_REASON)
        report.reject("transactions")
    else:
        location_xmlid = _keep_inventory_destination(importer, index, number, destination)
        _record_inventory(context, number, _INVENTORY_RECOGNIZED, destination, location_xmlid)
        report.skip("transactions")
    _bump_inventory_lines(report, line_outcomes, new_lines, written_lines)
    return [], []


def _upsert_order(importer, context, report, partner_by_cp, header, buysell, number, model_name, xml_id, incoterm_code):
    """One native order per source ``PONumber``. Every worksheet it serves is listed on ``origin``.

    A purchase order's ``date_approve`` is the earliest trade date
    (``GPLedger.TradeDt``) of the worksheets it serves (ADR-021 Decision 7).
    Writing it does not confirm the order: it stays a draft, with no picking.
    """
    from odoo.addons.plasticos_partner_import.erp.native_orders import (  # noqa: PLC0415
        clears_incoterm,
        declined_price_basis,
        with_worksheet,
    )

    env = importer.env
    model = env[model_name].with_context(**_import_context())
    partner_field = "CustID" if model_name == "sale.order" else "VendorID"
    partner_id = _partner_id(importer, partner_by_cp, header.get("CpID")) or _partner_id(
        importer, partner_by_cp, buysell.get(partner_field)
    )
    if not partner_id:
        raise ValueError(f"{model_name} {header.get('PONumber')} has no partner")
    existing = _existing(importer, model_name, xml_id)
    origin = with_worksheet(existing.origin if existing is not None else "", number)
    open_states = _OPEN_SALE_STATES if model_name == "sale.order" else _OPEN_PURCHASE_STATES
    if existing is not None and existing.state not in open_states:
        if (existing.origin or "") != origin:
            existing.with_context(**_import_context()).write({"origin": origin})
        return existing
    basis = (header.get("PriceBasis") or "").strip() or (buysell.get("PriceBasis") or "")
    values = {
        "partner_id": partner_id,
        "name": (header.get("PONumber") or "").strip(),
        "origin": origin,
        "date_order": _date(header.get("PODate") or buysell.get("OrderDt")),
        "user_id": (context.get("salesperson") or {}).get(number) or False,
    }
    if model_name == "sale.order":
        values["client_order_ref"] = (header.get("POReference") or "").strip() or False
        incoterm_field = "incoterm"
    else:
        incoterm_field = "incoterm_id"
        approved, missing = (context.get("trade_dates") or {}).get(number) or (None, [])
        current = existing.date_approve if existing is not None else False
        if approved and (not current or approved < current):
            values["date_approve"] = approved
        elif not approved:
            report.anomaly(
                "BuySell",
                number,
                f"purchase.order {values['name']}: date_approve not set ({'; '.join(missing) or 'no trade date'})",
            )
    if incoterm_field in model._fields:
        incoterm = _incoterm(env, context, incoterm_code(basis))
        if incoterm:
            values[incoterm_field] = incoterm
        elif declined_price_basis(basis):
            stored = existing[incoterm_field] if existing is not None else False
            if clears_incoterm(basis) or not stored:
                # ``delivered`` clears an Incoterm an earlier run wrote; nothing is set either way.
                values[incoterm_field] = False
                outcome = "none set"
            else:
                # A domestic shipping-point basis never rewrites an order already imported
                # (ADR-021 amendment 2026-11-12): the stored Incoterm is reported, not changed.
                outcome = f"stored Incoterm {stored.code or stored.name!s} left unchanged"
            report.anomaly(
                "BuySell",
                number,
                f"{model_name} {values['name']}: price basis {basis.strip()!r} has no supported Incoterm; {outcome}",
            )
    return importer._upsert(model, xml_id, values, _silent(), None)


class _SilentReport:
    def bump(self, *_args, **_kwargs):
        return None


def _silent():
    return _SilentReport()


def _line_terms(context, report, detail_id, line, side):
    """Quantity, unit code, and unit price of one worksheet side, with its precision drift.

    ``SWeight`` / ``PWeight`` are the quantity. A short ton becomes 2,000 lb.
    The unit price is ``amount / quantity``. When the quantity and price the
    document line fields store no longer reproduce the source amount to the
    cent, the line is reported and tallied; the source amount is never
    silently replaced. ``Product Price`` governs only how the price displays.
    """
    from odoo.addons.plasticos_partner_import.erp.native_orders import (  # noqa: PLC0415
        amount_drift,
        native_quantity,
        unit_price,
    )

    prefix = "S" if side == "sale" else "P"
    quantity, uom_code = native_quantity(line.get(f"{prefix}Weight"), line.get(f"{prefix}WeightUOM"))
    amount = line.get(f"{prefix}Amount")
    price = unit_price(amount, str(quantity) if quantity else "", line.get(f"{prefix}Price"))
    recorded = context.setdefault("drift_recorded", set())
    if (detail_id, side) not in recorded:
        recorded.add((detail_id, side))
        drift = amount_drift(amount, quantity, price, context["price_digits"], context.get("quantity_digits"))
        if drift:
            tally = context["price_drift"]
            tally["lines"] += 1
            tally["net_drift"] += drift
            tally["abs_drift"] += abs(drift)
            tally["max_abs_drift"] = max(tally["max_abs_drift"], abs(drift))
            digits = context["price_digits"]
            precision = f"{digits} price decimals" if digits is not None else "the stored quantity and price"
            report.anomaly(
                "WKSDetail",
                detail_id,
                f"{side} amount {_qty(amount):.2f} stored as {_qty(amount) + drift:.2f} at {precision}",
            )
    return quantity, uom_code, price


def _upsert_sale_line(importer, context, report, order, detail_id, line):
    quantity, uom_code, price = _line_terms(context, report, detail_id, line, "sale")
    if order.state not in _OPEN_SALE_STATES:
        _fill_existing_line(
            importer,
            context,
            report,
            "sale.order.line",
            f"legacy_erp_sol_{_token(detail_id)}",
            detail_id,
            line,
        )
        return
    normalized = _normalize_line(importer, context, line.get("GradeID"), line.get("InvoiceDesc"))
    product = _product(importer, context, line.get("GradeID"), line.get("InvoiceDesc"), normalized)
    uom = _uom(importer, context, uom_code)
    xml_id = f"legacy_erp_sol_{_token(detail_id)}"
    values = {
        "order_id": order.id,
        "product_id": product.id,
        "name": (line.get("InvoiceDesc") or "").strip() or product.display_name,
        "product_uom_qty": quantity,
        "price_unit": price,
        "tax_ids": [Command.clear()],
    }
    if uom:
        values["product_uom_id"] = uom.id
    values.update(
        _material_line_values(
            importer,
            report,
            "sale.order.line",
            _existing(importer, "sale.order.line", xml_id),
            detail_id,
            normalized,
        )
    )
    model = importer.env["sale.order.line"].with_context(**_import_context())
    importer._upsert(model, xml_id, values, _silent(), None)


def _upsert_purchase_line(importer, context, report, order, detail_id, line):
    quantity, uom_code, price = _line_terms(context, report, detail_id, line, "purchase")
    if order.state not in _OPEN_PURCHASE_STATES:
        return
    normalized = _normalize_line(importer, context, line.get("GradeID"), line.get("InvoiceDesc"))
    product = _product(importer, context, line.get("GradeID"), line.get("InvoiceDesc"), normalized)
    uom = _uom(importer, context, uom_code)
    xml_id = f"legacy_erp_pol_{_token(detail_id)}"
    values = {
        "order_id": order.id,
        "product_id": product.id,
        "name": (line.get("InvoiceDesc") or "").strip() or product.display_name,
        "product_qty": quantity,
        "price_unit": price,
        "date_planned": _date(order.date_order),
        "tax_ids": [Command.clear()],
    }
    if uom:
        values["product_uom_id"] = uom.id
    values.update(
        _material_line_values(
            importer,
            report,
            "purchase.order.line",
            _existing(importer, "purchase.order.line", xml_id),
            detail_id,
            normalized,
        )
    )
    model = importer.env["purchase.order.line"].with_context(**_import_context())
    importer._upsert(model, xml_id, values, _silent(), None)


def _customer_invoice(importer, report, context, partner_by_cp, number, buysell, sale_groups):
    if not sale_groups or not context["sale_journal"]:
        return None
    # One worksheet is one customer invoice on one transaction. Sale headers
    # that resolve to different customers cannot share it; the worksheet is
    # rejected rather than invoicing one customer's material to another.
    partner_ids = {
        _partner_id(importer, partner_by_cp, rows[0][2].get("CpID"))
        or _partner_id(importer, partner_by_cp, buysell.get("CustID"))
        for rows in sale_groups.values()
    }
    if len(partner_ids) > 1:
        raise ValueError(f"worksheet {number} sale orders belong to {len(partner_ids)} different customers")
    partner_id = partner_ids.pop()
    if not partner_id:
        return None
    commands = []
    for rows in sale_groups.values():
        for detail_id, line, _header in rows:
            product = _product(importer, context, line.get("GradeID"), line.get("InvoiceDesc"))
            weight, uom_code, price = _line_terms(context, report, detail_id, line, "sale")
            if not weight:
                continue
            vals = {
                "product_id": product.id,
                "name": (line.get("InvoiceDesc") or "").strip() or product.display_name,
                "quantity": weight,
                "price_unit": price,
                "tax_ids": [Command.clear()],
                "is_imported": True,
            }
            uom = _uom(importer, context, uom_code)
            if uom:
                vals["product_uom_id"] = uom.id
            if context["income_account"]:
                vals["account_id"] = context["income_account"].id
            commands.append(Command.create(vals))
    if not commands:
        return None
    signed = sum(item[2]["quantity"] * item[2]["price_unit"] for item in commands)
    if signed < 0:
        for item in commands:
            item[2]["price_unit"] = abs(item[2]["price_unit"])
    # A worksheet with no source invoice date gets an undated draft, never its order date.
    invoice_date = _date(buysell.get("InvoiceDt"))
    if not invoice_date:
        report.anomaly("BuySell", number, "no source invoice date; customer invoice left undated")
    return _move(
        importer,
        f"legacy_erp_outinv_{_token(number)}",
        {
            "move_type": "out_refund" if signed < 0 else "out_invoice",
            "partner_id": partner_id,
            "journal_id": context["sale_journal"].id,
            "invoice_date": (invoice_date or "")[:10] or False,
            "invoice_origin": number,
            "ref": number,
            "invoice_user_id": (context.get("salesperson") or {}).get(number) or False,
            "invoice_line_ids": commands,
        },
    )


def _customer_adjustments(importer, index, report, context, partner_by_cp, number, invoice, documents):
    """Approved sale-side ledger adjustments become customer credit notes and debit memos.

    One approved ``GPLedger`` row is one document, keyed by ``LedgerID``.
    Vendor-side adjustments are not written here: ``Payables`` carries each of
    them as its own row. Discount and fee rows belong to settlement and are
    reported, not realized.
    """
    from odoo.addons.plasticos_partner_import.erp.native_orders import (  # noqa: PLC0415
        BASE_TRADE,
        CARRIED_BY_PAYABLES,
        CUSTOMER_CREDIT,
        SETTLEMENT_EVIDENCE,
        UNAPPROVED,
        ledger_adjustment_kind,
    )

    journal = context["sale_journal"]
    income = context["income_account"]
    move_fields = importer.env["account.move"]._fields
    for row in index.ledger_by_buysell.get(number, []):
        kind = ledger_adjustment_kind(row)
        if kind in (BASE_TRADE, CARRIED_BY_PAYABLES):
            continue
        ledger_id = (row.get("LedgerID") or "").strip() or number
        if kind == UNAPPROVED:
            report.anomaly("GPLedger", ledger_id, "unapproved adjustment omitted")
            continue
        if kind == SETTLEMENT_EVIDENCE:
            report.anomaly(
                "GPLedger", ledger_id, f"Source {(row.get('Source') or '').strip()} row is settlement evidence"
            )
            continue
        amount = _qty(row.get("Sale"))
        partner_id = _partner_id(importer, partner_by_cp, row.get("AdjCpID")) or (
            invoice.partner_id.id if invoice is not None else None
        )
        if not amount or not partner_id or not journal or income is None:
            report.anomaly("GPLedger", ledger_id, "adjustment has no partner, amount, journal, or income account")
            continue
        memo = (row.get("AdjMemoNo") or "").strip()
        title = (row.get("AdjDocTitle") or "").strip()
        values = {
            "move_type": "out_refund" if kind == CUSTOMER_CREDIT else "out_invoice",
            "partner_id": partner_id,
            "journal_id": journal.id,
            "invoice_date": (_date(row.get("TradeDt")) or "")[:10] or False,
            "invoice_origin": number,
            "ref": memo or f"GPLedger {ledger_id}",
            "invoice_user_id": (context.get("salesperson") or {}).get(number) or False,
            "invoice_line_ids": [
                Command.create(
                    {
                        "name": " ".join(part for part in (title, memo) if part) or f"Adjustment {ledger_id}",
                        "quantity": 1.0,
                        "price_unit": abs(amount),
                        "account_id": income.id,
                        "tax_ids": [Command.clear()],
                        "is_imported": True,
                    }
                )
            ],
        }
        if invoice is not None and kind == CUSTOMER_CREDIT:
            values["reversed_entry_id"] = invoice.id
        elif invoice is not None and "debit_origin_id" in move_fields:
            values["debit_origin_id"] = invoice.id
        move = _move(importer, f"legacy_erp_ledger_{_token(ledger_id)}", values)
        documents["credits"].append(move.id)


def _vendor_bill_lines(importer, context, index, material, number, amount, row):
    """Worksheet buy quantity when this payable is the purchase total."""
    from odoo.addons.plasticos_partner_import.erp.native_orders import (  # noqa: PLC0415
        payable_matches_purchase,
        purchase_bill_lines,
    )

    item = (row.get("ItemID") or "").strip()
    details = [index.lines[detail_id] for detail_id in index.detail_ids(number)]
    specs = purchase_bill_lines(details) if item in ("", "0") and payable_matches_purchase(amount, details) else []
    if not specs:
        product, description = _worksheet_material(importer, context, index, number)
        label = description or (product.display_name if product else "") or (row.get("InvoiceNo") or "").strip()
        line_vals = {
            "name": label,
            "quantity": 1.0,
            "price_unit": abs(amount),
            "account_id": material.id,
            "tax_ids": [Command.clear()],
            "is_imported": True,
        }
        if product:
            line_vals["product_id"] = product.id
        return [Command.create(line_vals)]
    commands = []
    for spec in specs:
        product = _product(importer, context, spec["grade"], spec["description"])
        vals = {
            "product_id": product.id,
            "name": spec["description"] or product.display_name,
            "quantity": spec["quantity"],
            "price_unit": spec["price_unit"],
            "account_id": material.id,
            "tax_ids": [Command.clear()],
            "is_imported": True,
        }
        uom = _uom(importer, context, spec["uom"])
        if uom:
            vals["product_uom_id"] = uom.id
        po_line = _existing(importer, "purchase.order.line", f"legacy_erp_pol_{_token(spec.get('detail_id'))}")
        if po_line and "purchase_line_id" in importer.env["account.move.line"]._fields:
            vals["purchase_line_id"] = po_line.id
        commands.append(Command.create(vals))
    return commands


def _vendor_bills(importer, index, report, context, partner_by_cp, number, documents):
    """One bill or vendor credit per ``Payables`` row, routed by the source account lookup.

    Purchases (50100) bill Material Cost. Inland Freight (50200) bills Freight
    Cost and is never material cost. Handling and Equipment (50300, 50600) have
    no seeded account; their signed total is carried as the transaction's other
    expenses. Rows in a prepayment batch are never written. Every row that is
    not realized as a bill is tallied with its amount in the run census.
    """
    from odoo.addons.plasticos_partner_import.erp.native_orders import (  # noqa: PLC0415
        EXPENSE_GL,
        FREIGHT_GL,
        MATERIAL_GL,
        NOT_REALIZED,
        PREPAY_OMITTED,
        UNBILLABLE,
    )

    material = context["material_account"]
    freight_account = context["freight_account"]
    journal = context["purchase_journal"]
    costs = context.setdefault("costs", {"freight": {}, "other": {}})
    # A transaction is compiled from the worksheet's sale order once that
    # order is confirmed. Without a sale order there is nothing to carry a
    # transaction-only cost; with one, the cost is only carried if the
    # transaction actually comes to exist, so its disposition is settled in
    # ``_settle_transactions`` and never claimed here.
    may_compile = bool(documents["sales"])
    pending = context["pending_costs"].setdefault(number, [])
    unbilled_freight_rows: list[tuple[dict, str]] = []
    for row in index.payables_by_buysell.get(number, []):
        batch = (row.get("APBatchNo") or "").strip()
        payable_id = (row.get("PayableID") or "").strip()
        gl_acct = (row.get("GLAcct") or "").strip()
        amount = _qty(row.get("Amount"))
        if batch and batch in index.prepay_batches:
            _count_expense(context, "prepay_batch_omitted", number, amount)
            _quarantine(context, report, row, number, f"APBatchNo {batch} is a PrePay=1 batch", PREPAY_OMITTED)
            continue
        if gl_acct in EXPENSE_GL:
            # Handling (50300) and Equipment (50600) are not cost-of-goods
            # accounts in the mapping SSOT and have no seeded account. With a
            # transaction the amount is carried once as its other expenses;
            # without one it is carried nowhere. The bill itself is quarantined
            # with its full source identity either way.
            if may_compile:
                costs["other"][number] = costs["other"].get(number, 0.0) + amount
                pending.append(
                    (
                        row,
                        f"gl_{gl_acct}_as_other_expenses",
                        f"GL {gl_acct} has no native account in the crosswalk; amount carried once as other expenses",
                        f"gl_{gl_acct}_not_realized",
                        f"GL {gl_acct} has no native account in the crosswalk and no transaction exists to carry it",
                    )
                )
            else:
                _count_expense(context, f"gl_{gl_acct}_not_realized", number, amount)
                _quarantine(
                    context,
                    report,
                    row,
                    number,
                    f"GL {gl_acct} has no native account in the crosswalk and no transaction exists to carry it",
                    NOT_REALIZED,
                )
            continue
        if gl_acct not in (MATERIAL_GL, FREIGHT_GL):
            _count_expense(context, f"gl_{gl_acct or 'blank'}_not_realized", number, amount)
            _quarantine(
                context,
                report,
                row,
                number,
                f"GL lookup {gl_acct or 'blank'} resolves no native account; not realized, not counted",
                NOT_REALIZED,
            )
            continue
        account = freight_account if gl_acct == FREIGHT_GL else material
        partner_id = _partner_id(importer, partner_by_cp, row.get("CpID"))
        if account is None or not journal or not partner_id or not payable_id or not amount:
            if account is None:
                reason = f"native account for GL {gl_acct} is not seeded on this database"
            elif not journal:
                reason = "no purchase journal on this database"
            elif not partner_id:
                reason = f"vendor {(row.get('CpID') or '').strip() or 'blank'} is not an imported counterparty"
            elif not payable_id:
                reason = "blank PayableID"
            else:
                reason = "zero amount"
            _count_expense(context, f"gl_{gl_acct}_unbilled", number, amount)
            if gl_acct == FREIGHT_GL and amount:
                # Its economic disposition depends on the rest of the worksheet
                # (freight bills, a transaction); decided after the loop.
                unbilled_freight_rows.append((row, reason))
            else:
                _quarantine(context, report, row, number, f"{reason}; not counted", UNBILLABLE)
            continue
        _write_purchase_bill(
            importer,
            index,
            report,
            context,
            number,
            row,
            amount,
            account,
            partner_id,
            f"gl_{gl_acct}_billed",
            documents,
            gl_acct == FREIGHT_GL,
        )
    if not unbilled_freight_rows:
        return
    unbilled_freight = sum(_qty(row.get("Amount")) for row, _reason in unbilled_freight_rows)
    if documents["freight_bills"]:
        # Freight is counted once: the bills are the freight cost of this
        # worksheet. A freight row that could not be billed is not folded
        # into ``freight_actual`` beside them, where it would be ignored or
        # counted twice; it stays an exception with its amount.
        report.anomaly(
            "BuySell", number, f"unbilled freight {unbilled_freight:.2f} not counted: worksheet has freight bills"
        )
        for row, reason in unbilled_freight_rows:
            _quarantine(context, report, row, number, f"{reason}; not counted: worksheet has freight bills", UNBILLABLE)
    elif may_compile:
        # No freight bill exists, so the transaction's actual freight cost
        # carries the amount once (``freight_actual`` → ``freight_cost_total``)
        # if, and only if, the transaction is compiled.
        costs["freight"][number] = round(unbilled_freight, 2)
        for row, reason in unbilled_freight_rows:
            pending.append(
                (
                    row,
                    None,
                    f"{reason}; amount carried once as the transaction's actual freight cost",
                    None,
                    f"{reason}; no transaction exists to carry it",
                )
            )
    else:
        for row, reason in unbilled_freight_rows:
            _quarantine(context, report, row, number, f"{reason}; no transaction exists to carry it", NOT_REALIZED)


def _vendor_due_terms(importer, context, report, batch: str, facts: dict) -> dict:
    """The bill's payment term or explicit due date (``native_orders.vendor_bill_due_terms``). A term is never created."""
    from odoo.addons.plasticos_partner_import.erp.native_orders import vendor_bill_due_terms  # noqa: PLC0415

    return vendor_bill_due_terms(facts, _payment_term(importer.env, context, report, batch, facts["terms"]))


def _payment_term(env, context, report, batch: str, name: str):
    """Existing ``account.payment.term`` for an ERP term name. An unmatched name is reported once."""
    from odoo.addons.plasticos_partner_import.erp.mapping import payment_term_name  # noqa: PLC0415

    name = payment_term_name(name)
    if not name:
        return None
    cache = context.setdefault("payment_term_cache", {})
    if name not in cache:
        record = env["account.payment.term"].search([("name", "=", name)], limit=1)
        cache[name] = record.id if record else None
        if not record:
            report.anomaly(
                "PayablesBatch", batch, f"no account.payment.term named {name!r}; bills carry the header DueDate"
            )
    return cache[name]


def _count_expense(context, bucket: str, number: str, amount: float) -> None:
    """One payable row's routing, tallied when the worksheet is not rolled back."""
    context["expense_rows"].append((number, bucket, amount))


def _quarantine_worksheet_payables(index, context, report, number: str, reason: str, bucket: str) -> None:
    """Every payable of a worksheet that realized no document: reported one by one, nothing counted."""
    from odoo.addons.plasticos_partner_import.erp.native_orders import NOT_REALIZED  # noqa: PLC0415

    for row in index.payables_by_buysell.get(number, []):
        _count_expense(context, bucket, number, _qty(row.get("Amount")))
        _quarantine(context, report, row, number, reason, NOT_REALIZED)


def _write_purchase_bill(
    importer, index, report, context, number, row, amount, account, partner_id, bucket, documents, freight: bool
) -> None:
    """One draft vendor bill or credit. A negative amount is a vendor credit.

    Material bills and blank-account bills are this same document. Freight is
    the one named exception: its line is freight, not material.
    """
    from odoo.addons.plasticos_partner_import.erp.native_orders import vendor_bill_header_facts  # noqa: PLC0415

    payable_id = (row.get("PayableID") or "").strip()
    batch = (row.get("APBatchNo") or "").strip()
    facts = vendor_bill_header_facts(row, index.payables_batches.get(batch) if batch else None)
    invoice_date = facts["invoice_date"]
    if not invoice_date:
        report.anomaly("Payables", payable_id, "no source invoice date; vendor bill left undated")
    if freight:
        lines = [
            Command.create(
                {
                    "name": " ".join(part for part in ("Inland Freight", (row.get("InvoiceNo") or "").strip()) if part),
                    "quantity": 1.0,
                    "price_unit": abs(amount),
                    "account_id": account.id,
                    "tax_ids": [Command.clear()],
                    "is_imported": True,
                }
            )
        ]
    else:
        lines = _vendor_bill_lines(importer, context, index, account, number, amount, row)
    move = _move(
        importer,
        f"legacy_erp_ininv_{_token(payable_id)}",
        {
            "move_type": "in_refund" if amount < 0 else "in_invoice",
            "partner_id": partner_id,
            "journal_id": context["purchase_journal"].id,
            "invoice_date": invoice_date or False,
            "invoice_origin": number,
            "ref": facts["ref"],
            "invoice_line_ids": lines,
            **_vendor_due_terms(importer, context, report, batch, facts),
        },
    )
    if documents is not None:
        documents["freight_bills" if freight else "bills"].append(move.id)
    context["billed_payables"].append((number, payable_id))
    _count_expense(context, bucket, number, amount)


def _quarantine_outside_universe(importer, index, report, context, partner_by_cp, numbers, dry_run: bool) -> None:
    """Payables whose ``BuySellNo`` is no worksheet with lines.

    A blank account code with a vendor and an amount is written as a normal
    purchase bill. A negative amount is a vendor credit. Every other row is
    reported and not written.
    """
    from odoo.addons.plasticos_partner_import.erp.native_orders import (  # noqa: PLC0415
        FREIGHT_GL,
        MATERIAL_GL,
        NOT_REALIZED,
        outside_universe_payables,
    )

    material = context["material_account"]
    journal = context["purchase_journal"]
    for key, row in outside_universe_payables(index, numbers):
        gl_acct = (row.get("GLAcct") or "").strip()
        amount = _qty(row.get("Amount"))
        partner_id = _partner_id(importer, partner_by_cp, row.get("CpID"))
        payable_id = (row.get("PayableID") or "").strip()
        if (
            not gl_acct
            and key
            and not dry_run
            and material is not None
            and journal
            and partner_id
            and payable_id
            and amount
        ):
            _write_purchase_bill(
                importer,
                index,
                report,
                context,
                key,
                row,
                amount,
                material,
                partner_id,
                f"gl_{MATERIAL_GL}_billed",
                None,
                False,
            )
            continue
        if not key:
            reason = "blank BuySellNo; the bill names no worksheet"
        else:
            reason = f"BuySellNo {key!r} is not a worksheet with lines; no transaction to attach the bill to"
        if gl_acct in (MATERIAL_GL, FREIGHT_GL):
            reason += f" (GL {gl_acct} has a native account; realizing it standalone is an operator decision)"
        _count_expense(context, "outside_worksheet_universe_not_realized", key, amount)
        _quarantine(context, report, row, key, reason, NOT_REALIZED)


def _quarantine(context, report, row, number: str, reason: str, disposition: str) -> None:
    """A source bill the import did not write, kept with its identity and reported."""
    from odoo.addons.plasticos_partner_import.erp.native_orders import quarantined_payable  # noqa: PLC0415

    entry = quarantined_payable(row, number, reason, disposition)
    context["quarantine"].append(entry)
    report.anomaly(
        "Payables",
        entry["payable_id"] or number,
        f"{disposition}: {reason}; vendor {entry['vendor'] or 'blank'} invoice {entry['invoice_no'] or 'blank'}"
        f" dated {entry['invoice_date'] or 'blank'} amount {entry['amount']:.2f} worksheet {number}",
    )


def _move(importer, xml_id, values):
    """Create the document once. It stays in draft; settlement is not inferred from the source."""
    existing = _existing(importer, "account.move", xml_id)
    if existing is not None:
        return existing
    model = importer.env["account.move"].with_context(**_import_context())
    record = model.create(values)
    importer._write_identity_marker(model, xml_id, record)
    return record


def _confirm_sales(importer, report, pending_sales, context):
    """Confirm the batch's sale orders, compile their transactions, then settle every pending verdict."""
    existing_before = _existing_transactions(importer, context["pending_transactions"])
    _confirm_and_compile(importer, pending_sales, context)
    _settle_transactions(importer, report, context, existing_before)


def _existing_transactions(importer, pending: dict[str, list[int]]) -> set[str]:
    """Worksheets of ``pending`` that already own a transaction on one of their sale orders."""
    found: set[str] = set()
    for number, sale_ids in pending.items():
        if _worksheet_transaction(importer, number, sale_ids) is not None:
            found.add(number)
    return found


def _worksheet_transaction(importer, number: str, sale_ids: list[int]):
    """The transaction compiled for this worksheet from one of its own sale orders, or ``None``."""
    transaction = importer.env["plasticos.transaction"].search(
        [("name", "=", number), ("sale_order_id", "in", sale_ids)], limit=1
    )
    return transaction or None


def _settle_transactions(importer, report, context, existing_before: set[str]) -> None:
    """Count a transaction only once it exists; route every cost that depended on it accordingly.

    ``created`` is a worksheet whose transaction came to exist in this run,
    ``skipped`` one whose transaction already existed, ``rejected`` one whose
    sale order was not confirmed or whose transaction was not compiled. A
    pending cost row is ``transaction_only_cost`` only in the first two cases;
    otherwise nothing carries it and it is ``not_realized``, saying why.
    """
    from odoo.addons.plasticos_partner_import.erp.native_orders import (  # noqa: PLC0415
        NOT_REALIZED,
        TRANSACTION_ONLY_COST,
    )

    pending = context["pending_transactions"]
    for number in list(pending):
        sale_ids = pending.pop(number)
        transaction = _worksheet_transaction(importer, number, sale_ids)
        if transaction is not None:
            report.bump("transactions", "skipped" if number in existing_before else "created")
            failure = ""
        else:
            report.reject("transactions")
            failure = _transaction_failure(importer, number, sale_ids)
            report.anomaly("BuySell", number, f"{failure}; no transaction compiled")
        for row, carried_bucket, carried_reason, uncarried_bucket, uncarried_reason in context["pending_costs"].pop(
            number, []
        ):
            amount = _qty(row.get("Amount"))
            if transaction is not None:
                if carried_bucket:
                    _count_expense(context, carried_bucket, number, amount)
                _quarantine(context, report, row, number, carried_reason, TRANSACTION_ONLY_COST)
            else:
                if uncarried_bucket:
                    _count_expense(context, uncarried_bucket, number, amount)
                _quarantine(context, report, row, number, f"{uncarried_reason} ({failure})", NOT_REALIZED)


def _transaction_failure(importer, number: str, sale_ids: list[int]) -> str:
    """Why no transaction exists for the worksheet: an unconfirmed order, a foreign transaction, or no compile."""
    if not sale_ids:
        return "no sale order was written for the worksheet"
    orders = importer.env["sale.order"].browse(sale_ids).exists()
    unconfirmed = orders.filtered(lambda order: order.state != "sale")
    if unconfirmed:
        return "sale order " + ", ".join(f"{order.name} not confirmed ({order.state})" for order in unconfirmed)
    foreign = importer.env["plasticos.transaction"].search([("name", "=", number)], limit=1)
    if foreign:
        return f"transaction {number} exists on sale order {foreign.sale_order_id.name or foreign.sale_order_id.id}"
    return "sale order confirmed but no transaction was compiled"


def _confirm_and_compile(importer, pending_sales, context):
    orders = importer.env["sale.order"].browse(list(pending_sales)).exists()
    drafts = orders.filtered(lambda order: order.state in _OPEN_SALE_STATES)
    if drafts and "approved" in drafts._fields:
        drafts.write({"approved": True})
    costs = context.get("costs") or {}
    confirm_context = _confirm_context(context, costs)
    if drafts:
        confirm = drafts.with_context(**confirm_context)
        try:
            with importer.env.cr.savepoint():
                confirm.action_confirm()
        except Exception as exc:  # noqa: BLE001 - one blocked order must not drop the load
            _logger.info("ERP batch confirm failed (%s); confirming individually", type(exc).__name__)
            for order in drafts:
                if order.state not in _OPEN_SALE_STATES:
                    continue
                try:
                    with importer.env.cr.savepoint():
                        order.with_context(**confirm_context).action_confirm()
                except Exception as one:  # noqa: BLE001 - keep the imported order even if confirm fails
                    _logger.info("ERP sale %s was not confirmed: %s", order.name, one)
    # A worksheet added to an order confirmed in an earlier batch still needs its transaction.
    confirmed = orders.filtered(lambda order: order.state == "sale")
    if confirmed:
        try:
            with importer.env.cr.savepoint():
                confirmed.with_context(**confirm_context)._compile_worksheet_transactions()
        except Exception as exc:  # noqa: BLE001 - compile per order so one worksheet cannot drop the batch
            _logger.info("ERP batch compile failed (%s); compiling individually", type(exc).__name__)
            for order in confirmed:
                try:
                    with importer.env.cr.savepoint():
                        order.with_context(**confirm_context)._compile_worksheet_transactions()
                except Exception as one:  # noqa: BLE001 - keep the imported order even if compile fails
                    _logger.info("ERP sale %s transaction was not compiled: %s", order.name, one)
    for order in orders:
        trailers = [item for item in pending_sales.get(order.id, []) if item]
        if trailers and order.picking_ids and "carrier_tracking_ref" in order.picking_ids._fields:
            reference = ", ".join(dict.fromkeys(trailers))
            stale = order.picking_ids.filtered(lambda picking, ref=reference: picking.carrier_tracking_ref != ref)
            if stale:
                stale.write({"carrier_tracking_ref": reference})


def _trailers(index, number) -> list[str]:
    found = []
    for row in index.deliveries_by_buysell.get(number, []):
        trailer = (row.get("TrailerNo") or "").strip()
        if trailer and trailer not in found:
            found.append(trailer)
    return found


def _worksheet_material(importer, context, index, number):
    """Grade on the worksheet line. The payable number is the bill reference, not the product."""
    cached = context.setdefault("materials", {}).get(number)
    if cached is not None:
        return cached
    found = (None, "")
    for detail_id in index.detail_ids(number):
        line = index.lines[detail_id]
        description = (line.get("InvoiceDesc") or "").strip()
        grade = (line.get("GradeID") or "").strip()
        if description or grade:
            found = (_product(importer, context, grade, description), description)
            break
    context["materials"][number] = found
    return found


def _remember_carrier(importer, context, partner_by_cp, number, deliveries) -> None:
    from odoo.addons.plasticos_partner_import.erp.native_orders import freight_vendor_id  # noqa: PLC0415

    vendor = freight_vendor_id(deliveries)
    partner_id = _partner_id(importer, partner_by_cp, vendor) if vendor else None
    context.setdefault("carriers", {})[number] = partner_id or False


def _normalize_line(importer, context, _grade_id, description):
    """Classify the description. GradeID identifies the historical product, not the material.

    One description is classified once per import, including the confirmed-line fill.
    """
    key = " ".join(str(description or "").split())
    cache = context.setdefault("normalized", {})
    if key not in cache:
        from odoo.addons.plasticos_material_profile.models.material_normalizer import (  # noqa: PLC0415
            normalize_material,
        )

        cache[key] = normalize_material(importer.env, description)
    return cache[key]


def _fill_existing_line(importer, context, report, model_name, xml_id, detail_id, line):
    """Fill empty material fields on a confirmed line. Product, quantity, price, and taxes stay."""
    existing = _existing(importer, model_name, xml_id)
    if existing is None:
        return
    normalized = _normalize_line(importer, context, line.get("GradeID"), line.get("InvoiceDesc"))
    values = _material_line_values(importer, report, model_name, existing, detail_id, normalized)
    if values:
        existing.with_context(**_import_context()).write(values)


def _product(importer, context, grade_id, description, normalized=None):
    """One product per GradeID and compatible classification.

    A second supported classification keeps the GradeID on ``default_code`` and
    gets its own external id. An unresolved description does not clear a polymer
    already stored on the grade product, and it does not reuse that product.
    """
    if normalized is None:
        normalized = _normalize_line(importer, context, grade_id, description)
    grade = (grade_id or "").strip() or "unspecified"
    polymer = normalized.polymer
    code = polymer.code if polymer else ""
    cache_key = f"{grade}|{code}"
    cached = context["product_cache"].get(cache_key)
    # A product created inside a worksheet savepoint vanishes when that
    # worksheet is rolled back; the cache must not hand out the dead record.
    if cached and cached.exists():
        return cached
    context["product_cache"].pop(cache_key, None)
    base_xml = f"legacy_erp_grade_{_token(grade)}"
    product = _grade_product(importer, base_xml, polymer)
    if product is None:
        xml_id = base_xml
        if _existing(importer, "product.product", base_xml) is not None:
            xml_id = f"{base_xml}_{_token(code or 'other')}"
        product = _existing(importer, "product.product", xml_id)
        if product is None:
            product = _create_grade_product(importer, xml_id, grade, description)
    _fill_polymer(importer, product, polymer)
    context["product_cache"][cache_key] = product
    return product


def _grade_product(importer, xml_id, polymer):
    existing = _existing(importer, "product.product", xml_id)
    if existing is not None and _polymer_compatible(existing, polymer):
        return existing
    return None


def _polymer_compatible(product, polymer) -> bool:
    current = product.product_tmpl_id.polymer_id
    if bool(current) != bool(polymer):
        return False
    if not current:
        return True
    return current == polymer


def _fill_polymer(importer, product, polymer) -> None:
    if not polymer:
        return
    template = product.product_tmpl_id
    if template.polymer_id:
        return
    template.with_context(**_import_context()).write({"polymer_id": polymer.id})


def _create_grade_product(importer, xml_id, grade, description):
    values = {
        "name": (description or "").strip() or grade,
        "default_code": grade,
        "type": "consu",
        "sale_ok": True,
        "purchase_ok": True,
        "taxes_id": [Command.clear()],
        "supplier_taxes_id": [Command.clear()],
    }
    if "is_storable" in importer.env["product.product"]._fields:
        values["is_storable"] = False
    product = importer.env["product.product"].with_context(**_import_context()).create(values)
    importer._write_identity_marker(product, xml_id, product)
    return product


def _color_set_label(records):
    labels = []
    for record in records:
        label = getattr(record, "code", None) or record.display_name
        if label:
            labels.append(label)
    return ", ".join(labels)


def _material_line_values(importer, report, model_name, existing, detail_id, normalized):
    """Fill empty material fields. A stored value that disagrees is kept and reported.

    An empty attribute set is unspecified. It does not clear attributes already
    stored on the line, and a replay that already has the resolved attributes
    does not write the relation again.
    """
    values = {}
    fields = importer.env[model_name]._fields
    for field_name, attr in (
        ("material_grade_id", "material_grade"),
        ("form_id", "form"),
        ("source_type_id", "source_type"),
        ("packaging_type_id", "packaging_type"),
        ("filler_type_id", "filler_type"),
    ):
        if field_name not in fields:
            continue
        resolved = getattr(normalized, attr, None)
        if not resolved or len(resolved) != 1:
            continue
        current = existing[field_name] if existing is not None else resolved.browse()
        if not current:
            values[field_name] = resolved.id
        elif current != resolved:
            stored = getattr(current, "code", None) or current.display_name
            wanted = getattr(resolved, "code", None) or resolved.display_name
            report.anomaly("WKSDetail", detail_id, f"{field_name} stored {stored}, normalizer {wanted}; kept")
    process = getattr(normalized, "process_type", None)
    if process and "origin_process_type" in fields:
        current = existing.origin_process_type if existing is not None else False
        if not current:
            values["origin_process_type"] = process
        elif current != process:
            report.anomaly(
                "WKSDetail",
                detail_id,
                f"origin_process_type stored {current}, normalizer {process}; kept",
            )
    resolved_colors = getattr(normalized, "color", None)
    if resolved_colors and "color_ids" in fields:
        current_colors = existing.color_ids if existing is not None else resolved_colors.browse()
        if not current_colors:
            values["color_ids"] = [Command.set(list(resolved_colors.ids))]
        elif set(current_colors.ids) != set(resolved_colors.ids):
            stored = _color_set_label(current_colors)
            wanted = _color_set_label(resolved_colors)
            report.anomaly("WKSDetail", detail_id, f"color_ids stored {stored}, normalizer {wanted}; kept")
    if normalized.attributes and "material_attribute_ids" in fields:
        current = existing.material_attribute_ids if existing is not None else normalized.attributes.browse()
        missing = normalized.attributes - current
        if missing:
            values["material_attribute_ids"] = [Command.link(attribute_id) for attribute_id in missing.ids]
    return values


def _uom(importer, context, code):
    token = (code or "").strip().upper()
    if not token:
        return None
    if token in context["uom_cache"]:
        return context["uom_cache"][token]
    xml_id = _UOM_XMLID.get(token)
    record = importer.env.ref(xml_id, raise_if_not_found=False) if xml_id else None
    context["uom_cache"][token] = record
    return record


def _incoterm(env, context, code):
    if not code:
        return None
    cached = context["incoterm_cache"].get(code)
    if cached:
        return cached.id
    record = env["account.incoterms"].search([("code", "=", code)], limit=1)
    if record:
        context["incoterm_cache"][code] = record
    return record.id if record else None


def _partner_id(importer, partner_by_cp, cp_id):
    token = (cp_id or "").strip()
    if not token:
        return None
    stored = partner_by_cp.get(token)
    if stored:
        return stored
    record = _existing(importer, "res.partner", f"legacy_erp_cp_{token}")
    return record.id if record else None


def _existing(importer, model_name, xml_id):
    data = importer.env["ir.model.data"].search(
        [("module", "=", XMLID_MODULE), ("name", "=", xml_id), ("model", "=", model_name)],
        limit=1,
    )
    if not data or not data.res_id:
        return None
    record = importer.env[model_name].browse(data.res_id).exists()
    return record or None


def _token(value) -> str:
    text = "".join(ch if ch.isalnum() else "_" for ch in str(value or "").strip())
    return text or "blank"


def _qty(value) -> float:
    text = (value or "").strip() if isinstance(value, str) else str(value or "").strip()
    if not text:
        return 0.0
    return float(text)


def _date(value):
    text = (value or "").strip() if isinstance(value, str) else str(value or "").strip()
    return text or False


def _remember_salesperson(importer, report, context, number, buysell) -> None:
    """Worksheet commission recipient, not the customer's current default rep.

    The recipient keeps the initials the worksheet stored. A former
    representative with no user leaves the salesperson blank and is reported.
    A second recipient with an amount is reported and written to the
    transaction log; the transaction model holds one salesperson.
    """
    from odoo.addons.plasticos_partner_import.erp.mapping import SALES_REP_NAMES  # noqa: PLC0415
    from odoo.addons.plasticos_partner_import.erp.native_orders import (  # noqa: PLC0415
        commission_recipients,
        worksheet_commission,
    )

    code, amount, slots = worksheet_commission(buysell)
    context.setdefault("commission", {})[number] = amount
    context.setdefault("commission_slots", {})[number] = slots
    recipients = commission_recipients(slots)
    if len(recipients) > 1:
        report.anomaly("BuySell", number, f"two commission recipients: {', '.join(recipients)}")
    user_id = False
    if code:
        name = SALES_REP_NAMES.get(code)
        cache = context.setdefault("users_by_name", {})
        if name and name not in cache:
            cache[name] = importer._user_ids_by_name({name}).get(name) or False
        user_id = cache.get(name) if name else False
        if not user_id:
            report.anomaly("BuySell", number, f"commission recipient {code} has no user")
    context.setdefault("salesperson", {})[number] = user_id or False


def _confirm_context(context, costs) -> dict:
    return {
        **_import_context(),
        # A historical sale is not shipped again: confirming it launches no
        # procurement, so no delivery picking or stock move is created
        # (sale_stock ``_action_launch_stock_rule`` honours this key).
        "skip_procurement": True,
        "erp_freight_by_origin": costs.get("freight") or {},
        "erp_other_by_origin": costs.get("other") or {},
        "erp_salesperson_by_origin": context.get("salesperson") or {},
        "erp_commission_by_origin": context.get("commission") or {},
        "erp_commission_slots_by_origin": context.get("commission_slots") or {},
        "erp_note_by_origin": context.get("notes") or {},
        "erp_state_by_origin": context.get("states") or {},
        "erp_raw_status_by_origin": context.get("raw_states") or {},
        "erp_carrier_by_origin": context.get("carriers") or {},
        "erp_order_day_by_origin": context.get("order_days") or {},
        "erp_documents_by_origin": context.get("documents") or {},
    }


def _import_context() -> dict:
    return {
        "import_mode": True,
        "tracking_disable": True,
        "mail_create_nolog": True,
        "mail_notrack": True,
    }
