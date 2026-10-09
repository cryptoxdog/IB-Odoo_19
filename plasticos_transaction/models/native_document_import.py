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
# L pounds, S short tons, E each. E is a count (gaylords), not a ton.
_UOM_XMLID = {"L": "uom.product_uom_lb", "S": "uom.product_uom_ton", "E": "uom.product_uom_unit"}
_OPEN_SALE_STATES = ("draft", "sent")
_OPEN_PURCHASE_STATES = ("draft", "sent", "to approve")


def realize(importer, index, report, partner_by_cp, limit, commit, dry_run) -> bool:
    """Realize native documents. Returns true so the caller does not commit twice."""
    numbers = index.buysell_numbers()
    if not index.orders:
        for number in numbers:
            report.skip("transactions")
            report.skip("transaction_lines", len(index.detail_ids(number)))
        return True

    from odoo.addons.plasticos_partner_import.erp.native_orders import selected_worksheets  # noqa: PLC0415

    selected = selected_worksheets(numbers, limit)
    selected_set = set(selected)
    context = _load_context(importer)
    pending_sales: dict[int, list[str]] = {}
    for position, number in enumerate(selected, start=1):
        if dry_run:
            report.skip("transactions")
            report.skip("transaction_lines", len(index.detail_ids(number)))
            continue
        try:
            with importer.env.cr.savepoint():
                sale_ids, trailers = _realize_one(importer, index, report, partner_by_cp, context, number)
        except Exception as exc:  # noqa: BLE001 - one worksheet must not abort the load
            _logger.info("ERP worksheet %s was not written: %s", number, exc)
            report.anomaly("BuySell", number, type(exc).__name__)
            report.reject("transactions")
            report.reject("transaction_lines", len(index.detail_ids(number)))
            context["documents"].pop(number, None)
            continue
        for sale_id in sale_ids:
            pending_sales.setdefault(sale_id, []).extend(trailers)
        if commit and not dry_run and position % 200 == 0:
            _confirm_sales(importer, pending_sales, context)
            pending_sales.clear()
            importer.env.cr.commit()
            _logger.info("ERP import committed through worksheet %s", position)

    if not dry_run:
        _confirm_sales(importer, pending_sales, context)
    for number in numbers:
        if number in selected_set:
            continue
        report.skip("transactions")
        report.skip("transaction_lines", len(index.detail_ids(number)))
    if commit and not dry_run:
        importer.env.cr.commit()
    return True


def _load_context(importer) -> dict:
    """Accounts and journals the documents post to. No company, account, or product setting is written."""
    env = importer.env
    material = env.ref("plasticos_accounting.account_50100_material_cost", raise_if_not_found=False)
    income = env.ref("plasticos_accounting.account_40050_sales_income", raise_if_not_found=False)
    freight = env.ref("plasticos_accounting.account_50200_freight_cost", raise_if_not_found=False)
    if freight is None:
        freight = (
            env["account.account"].search(
                [("code", "=", "50200"), ("account_type", "=", "expense_direct_cost")], limit=1
            )
            or None
        )
    return {
        "material_account": material,
        "income_account": income,
        "freight_account": freight,
        "sale_journal": env["account.journal"].search([("type", "=", "sale")], limit=1),
        "purchase_journal": env["account.journal"].search([("type", "=", "purchase")], limit=1),
        "product_cache": {},
        "uom_cache": {},
        "incoterm_cache": {},
        "documents": {},
    }


def _new_documents() -> dict:
    return {"sales": [], "purchases": [], "invoice": False, "credits": [], "bills": [], "freight_bills": []}


def _realize_one(importer, index, report, partner_by_cp, context, number):
    from odoo.addons.plasticos_partner_import.erp.native_orders import (  # noqa: PLC0415
        header_for_line,
        incoterm_code,
        unit_price,
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
    context.setdefault("order_days", {})[number] = (_date(buysell.get("OrderDt")) or "")[:10]
    _remember_carrier(importer, context, partner_by_cp, number, index.deliveries_by_buysell.get(number, []))
    sale_groups: dict[str, list] = {}
    purchase_groups: dict[str, list] = {}
    line_outcomes = []
    for detail_id in index.detail_ids(number):
        line = index.lines[detail_id]
        sale_header, sale_reason = header_for_line(index, (line.get("SPO_ID") or "").strip(), "SO")
        purchase_header, purchase_reason = header_for_line(index, (line.get("PPO_ID") or "").strip(), "PO")
        if sale_header is None and purchase_header is None:
            report.anomaly("WKSDetail", detail_id, sale_reason or purchase_reason)
            line_outcomes.append("rejected")
            continue
        if sale_header is not None:
            sale_groups.setdefault(sale_header["POID"], []).append((detail_id, line, sale_header))
        if purchase_header is not None:
            purchase_groups.setdefault(purchase_header["POID"], []).append((detail_id, line, purchase_header))
        line_outcomes.append(detail_id)

    if not sale_groups and not purchase_groups:
        report.reject("transactions")
        report.reject("transaction_lines", len(line_outcomes) or len(index.detail_ids(number)))
        return [], []

    trailers = _trailers(index, number)
    fresh_document = False
    new_lines: set[str] = set()
    for _po_id, rows in sale_groups.items():
        header = rows[0][2]
        xml_id = f"legacy_erp_so_{_token(header.get('PONumber'))}"
        fresh_document = fresh_document or _existing(importer, "sale.order", xml_id) is None
        order = _upsert_order(
            importer, context, partner_by_cp, header, buysell, number, "sale.order", xml_id, incoterm_code
        )
        if order is not None:
            documents["sales"].append(order.id)
            for detail_id, line, _header in rows:
                if (
                    order.state in _OPEN_SALE_STATES
                    and _existing(importer, "sale.order.line", f"legacy_erp_sol_{_token(detail_id)}") is None
                ):
                    new_lines.add(detail_id)
                _upsert_sale_line(importer, context, order, detail_id, line, unit_price)
    if len(documents["sales"]) > 1:
        report.anomaly("BuySell", number, f"worksheet carries {len(documents['sales'])} sale orders")
    for _po_id, rows in purchase_groups.items():
        header = rows[0][2]
        xml_id = f"legacy_erp_po_{_token(header.get('PONumber'))}"
        fresh_document = fresh_document or _existing(importer, "purchase.order", xml_id) is None
        order = _upsert_order(
            importer, context, partner_by_cp, header, buysell, number, "purchase.order", xml_id, incoterm_code
        )
        if order is not None:
            documents["purchases"].append(order.id)
            for detail_id, line, _header in rows:
                if (
                    order.state in _OPEN_PURCHASE_STATES
                    and _existing(importer, "purchase.order.line", f"legacy_erp_pol_{_token(detail_id)}") is None
                ):
                    new_lines.add(detail_id)
                _upsert_purchase_line(importer, context, order, detail_id, line, unit_price)
    invoice = _customer_invoice(importer, context, partner_by_cp, number, buysell, sale_groups, unit_price)
    documents["invoice"] = invoice.id if invoice is not None else False
    _customer_adjustments(importer, index, report, context, partner_by_cp, number, invoice, documents)
    _vendor_bills(importer, index, report, context, partner_by_cp, number, documents)
    report.bump("transactions", "created" if fresh_document else "skipped")
    for outcome in line_outcomes:
        if outcome == "rejected":
            report.bump("transaction_lines", "rejected")
        else:
            report.bump("transaction_lines", "created" if outcome in new_lines else "skipped")
    return list(documents["sales"]), trailers


def _upsert_order(importer, context, partner_by_cp, header, buysell, number, model_name, xml_id, incoterm_code):
    """One native order per source ``PONumber``. Every worksheet it serves is listed on ``origin``."""
    from odoo.addons.plasticos_partner_import.erp.native_orders import with_worksheet  # noqa: PLC0415

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
        if "incoterm" in model._fields:
            incoterm = _incoterm(env, context, incoterm_code(basis))
            if incoterm:
                values["incoterm"] = incoterm
    elif "incoterm_id" in model._fields:
        incoterm = _incoterm(env, context, incoterm_code(basis))
        if incoterm:
            values["incoterm_id"] = incoterm
    return importer._upsert(model, xml_id, values, _silent(), None)


def _silent():
    class _Report:
        def bump(self, *_args, **_kwargs):
            return None

    return _Report()


def _upsert_sale_line(importer, context, order, detail_id, line, unit_price):
    if order.state not in _OPEN_SALE_STATES:
        return
    product = _product(importer, context, line.get("GradeID"), line.get("InvoiceDesc"))
    uom = _uom(importer, context, line.get("SWeightUOM"))
    values = {
        "order_id": order.id,
        "product_id": product.id,
        "name": (line.get("InvoiceDesc") or "").strip() or product.display_name,
        "product_uom_qty": _qty(line.get("SWeight")),
        "price_unit": unit_price(line.get("SAmount"), line.get("SWeight"), line.get("SPrice")),
        "tax_ids": [Command.clear()],
    }
    if uom:
        values["product_uom_id"] = uom.id
    model = importer.env["sale.order.line"].with_context(**_import_context())
    importer._upsert(model, f"legacy_erp_sol_{_token(detail_id)}", values, _silent(), None)


def _upsert_purchase_line(importer, context, order, detail_id, line, unit_price):
    if order.state not in _OPEN_PURCHASE_STATES:
        return
    product = _product(importer, context, line.get("GradeID"), line.get("InvoiceDesc"))
    uom = _uom(importer, context, line.get("PWeightUOM"))
    values = {
        "order_id": order.id,
        "product_id": product.id,
        "name": (line.get("InvoiceDesc") or "").strip() or product.display_name,
        "product_qty": _qty(line.get("PWeight")),
        "price_unit": unit_price(line.get("PAmount"), line.get("PWeight"), line.get("PPrice")),
        "date_planned": _date(order.date_order),
        "tax_ids": [Command.clear()],
    }
    if uom:
        values["product_uom_id"] = uom.id
    model = importer.env["purchase.order.line"].with_context(**_import_context())
    importer._upsert(model, f"legacy_erp_pol_{_token(detail_id)}", values, _silent(), None)


def _customer_invoice(importer, context, partner_by_cp, number, buysell, sale_groups, unit_price):
    if not sale_groups or not context["sale_journal"]:
        return None
    header = next(iter(sale_groups.values()))[0][2]
    partner_id = _partner_id(importer, partner_by_cp, header.get("CpID")) or _partner_id(
        importer, partner_by_cp, buysell.get("CustID")
    )
    if not partner_id:
        return None
    commands = []
    for rows in sale_groups.values():
        for _detail_id, line, _header in rows:
            product = _product(importer, context, line.get("GradeID"), line.get("InvoiceDesc"))
            weight = _qty(line.get("SWeight"))
            if not weight:
                continue
            vals = {
                "product_id": product.id,
                "name": (line.get("InvoiceDesc") or "").strip() or product.display_name,
                "quantity": weight,
                "price_unit": unit_price(line.get("SAmount"), line.get("SWeight"), line.get("SPrice")),
                "tax_ids": [Command.clear()],
                "is_imported": True,
            }
            uom = _uom(importer, context, line.get("SWeightUOM"))
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
    invoice_date = _date(buysell.get("InvoiceDt") or buysell.get("OrderDt"))
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
    expenses. Rows in a prepayment batch are never written.
    """
    from odoo.addons.plasticos_partner_import.erp.native_orders import (  # noqa: PLC0415
        EXPENSE_GL,
        FREIGHT_GL,
        MATERIAL_GL,
    )

    material = context["material_account"]
    freight_account = context["freight_account"]
    journal = context["purchase_journal"]
    costs = context.setdefault("costs", {"freight": {}, "other": {}})
    for row in index.payables_by_buysell.get(number, []):
        batch = (row.get("APBatchNo") or "").strip()
        payable_id = (row.get("PayableID") or "").strip()
        if batch and batch in index.prepay_batches:
            report.anomaly("Payables", payable_id or number, "prepay batch omitted")
            continue
        gl_acct = (row.get("GLAcct") or "").strip()
        amount = _qty(row.get("Amount"))
        if gl_acct in EXPENSE_GL:
            costs["other"][number] = costs["other"].get(number, 0.0) + amount
            continue
        if gl_acct not in (MATERIAL_GL, FREIGHT_GL):
            report.anomaly("Payables", payable_id or number, f"GL lookup {gl_acct or 'blank'} has no native account")
            continue
        account = freight_account if gl_acct == FREIGHT_GL else material
        partner_id = _partner_id(importer, partner_by_cp, row.get("CpID"))
        if account is None or not journal or not partner_id or not payable_id or not amount:
            if gl_acct == FREIGHT_GL and amount:
                costs["freight"][number] = costs["freight"].get(number, 0.0) + amount
            reason = "no native account" if account is None else "no vendor, journal, or amount"
            report.anomaly("Payables", payable_id or number, f"GL lookup {gl_acct} {reason}")
            continue
        invoice_date = _date(row.get("InvoiceDt")) or _date(index.buysells.get(number, {}).get("OrderDt"))
        if gl_acct == FREIGHT_GL:
            lines = [
                Command.create(
                    {
                        "name": " ".join(
                            part for part in ("Inland Freight", (row.get("InvoiceNo") or "").strip()) if part
                        ),
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
                "journal_id": journal.id,
                "invoice_date": (invoice_date or "")[:10] or False,
                "invoice_origin": number,
                "ref": (row.get("InvoiceNo") or payable_id).strip(),
                "invoice_line_ids": lines,
            },
        )
        documents["freight_bills" if gl_acct == FREIGHT_GL else "bills"].append(move.id)


def _move(importer, xml_id, values):
    """Create the document once. It stays in draft; settlement is not inferred from the source."""
    existing = _existing(importer, "account.move", xml_id)
    if existing is not None:
        return existing
    model = importer.env["account.move"].with_context(**_import_context())
    record = model.create(values)
    importer._write_identity_marker(model, xml_id, record)
    return record


def _confirm_sales(importer, pending_sales, context):
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


def _product(importer, context, grade_id, description):
    grade = (grade_id or "").strip() or "unspecified"
    cached = context["product_cache"].get(grade)
    # A product created inside a worksheet savepoint vanishes when that
    # worksheet is rolled back; the cache must not hand out the dead record.
    if cached and cached.exists():
        return cached
    context["product_cache"].pop(grade, None)
    xml_id = f"legacy_erp_grade_{_token(grade)}"
    existing = _existing(importer, "product.product", xml_id)
    if existing is not None:
        context["product_cache"][grade] = existing
        return existing
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
    context["product_cache"][grade] = product
    return product


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
        "erp_freight_by_origin": costs.get("freight") or {},
        "erp_other_by_origin": costs.get("other") or {},
        "erp_salesperson_by_origin": context.get("salesperson") or {},
        "erp_commission_by_origin": context.get("commission") or {},
        "erp_commission_slots_by_origin": context.get("commission_slots") or {},
        "erp_note_by_origin": context.get("notes") or {},
        "erp_state_by_origin": context.get("states") or {},
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
