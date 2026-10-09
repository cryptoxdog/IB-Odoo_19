"""Write sale orders, purchase orders, and invoices from the ERP source index.

The importer does not create a transaction record. Confirming the sale order
lets the sales hook compile one. Source identity is ``ir.model.data``. A second
run updates the same documents.
"""

from __future__ import annotations

import logging

from odoo import Command

_logger = logging.getLogger(__name__)

XMLID_MODULE = "plasticos_transaction"
# L pounds, S short tons, E each. E is a count (gaylords), not a ton.
_UOM_XMLID = {"L": "uom.product_uom_lb", "S": "uom.product_uom_ton", "E": "uom.product_uom_unit"}


def realize(importer, index, report, partner_by_cp, limit, commit, dry_run) -> bool:
    """Realize native documents. Returns true so the caller does not commit twice."""
    numbers = index.buysell_numbers()
    if not index.orders:
        for number in numbers:
            report.skip("transactions")
            report.skip("transaction_lines", len(index.detail_ids(number)))
        return True

    from odoo.addons.plasticos_partner_import.erp.native_orders import newest_numbers  # noqa: PLC0415

    selected = newest_numbers(numbers, limit)
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
            continue
        for sale_id in sale_ids:
            pending_sales.setdefault(sale_id, []).extend(trailers)
        if commit and not dry_run and position % 200 == 0:
            _confirm_sales(importer, index, pending_sales, context)
            pending_sales.clear()
            importer.env.cr.commit()
            _logger.info("ERP import committed through worksheet %s", position)

    if not dry_run:
        _confirm_sales(importer, index, pending_sales, context)
    for number in numbers:
        if number in selected_set:
            continue
        report.skip("transactions")
        report.skip("transaction_lines", len(index.detail_ids(number)))
    if commit and not dry_run:
        importer.env.cr.commit()
    return True


def _clear_default_taxes(env) -> None:
    """Wholesale reseller. No sales tax and no purchase tax on imported documents."""
    company = env.company
    tax_fields = [name for name in ("account_sale_tax_id", "account_purchase_tax_id") if name in company._fields]
    if tax_fields:
        company.sudo().write(dict.fromkeys(tax_fields, False))  # sudo: company tax defaults are a system setting
    accounts = env["account.account"].search([("tax_ids", "!=", False)])
    if accounts:
        accounts.with_context(**_import_context()).write({"tax_ids": [Command.clear()]})
    products = env["product.template"].search(["|", ("taxes_id", "!=", False), ("supplier_taxes_id", "!=", False)])
    if products:
        products.with_context(**_import_context()).write(
            {"taxes_id": [Command.clear()], "supplier_taxes_id": [Command.clear()]}
        )


def _load_context(importer) -> dict:
    env = importer.env
    material = env.ref("plasticos_accounting.account_50100_material_cost", raise_if_not_found=False)
    income = env.ref("plasticos_accounting.account_40050_sales_income", raise_if_not_found=False)
    _clear_default_taxes(env)
    return {
        "material_account": material,
        "income_account": income,
        "sale_journal": env["account.journal"].search([("type", "=", "sale")], limit=1),
        "purchase_journal": env["account.journal"].search([("type", "=", "purchase")], limit=1),
        "product_cache": {},
        "uom_cache": {},
        "incoterm_cache": {},
    }


def _realize_one(importer, index, report, partner_by_cp, context, number):
    from odoo.addons.plasticos_partner_import.erp.native_orders import (  # noqa: PLC0415
        header_for_line,
        incoterm_code,
        unit_price,
        worksheet_commission,
        worksheet_log,
        worksheet_outcome,
    )

    buysell = index.buysells.get(number, {})
    _remember_salesperson(importer, context, number, buysell, worksheet_commission)
    context.setdefault("notes", {})[number] = worksheet_log(
        buysell.get("ProblemNotes"), buysell.get("Notes"), buysell.get("BookingNo")
    )
    context.setdefault("states", {})[number] = worksheet_outcome(buysell.get("status"))
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
    sale_ids = []
    fresh_document = False
    new_lines: set[str] = set()
    for _po_id, rows in sale_groups.items():
        header = rows[0][2]
        xml_id = f"legacy_erp_so_{_token(header.get('PONumber'))}"
        fresh_document = fresh_document or _existing(importer, "sale.order", xml_id) is None
        order = _upsert_order(
            importer,
            context,
            partner_by_cp,
            header,
            buysell,
            number,
            "sale.order",
            xml_id,
            incoterm_code,
        )
        if order is not None:
            sale_ids.append(order.id)
            for detail_id, line, _header in rows:
                if (
                    order.state in ("draft", "sent")
                    and _existing(importer, "sale.order.line", f"legacy_erp_sol_{_token(detail_id)}") is None
                ):
                    new_lines.add(detail_id)
                _upsert_sale_line(importer, context, order, detail_id, line, unit_price)
    for _po_id, rows in purchase_groups.items():
        header = rows[0][2]
        xml_id = f"legacy_erp_po_{_token(header.get('PONumber'))}"
        fresh_document = fresh_document or _existing(importer, "purchase.order", xml_id) is None
        order = _upsert_order(
            importer,
            context,
            partner_by_cp,
            header,
            buysell,
            number,
            "purchase.order",
            xml_id,
            incoterm_code,
        )
        if order is not None:
            for detail_id, line, _header in rows:
                if (
                    order.state in ("draft", "sent", "to approve")
                    and _existing(importer, "purchase.order.line", f"legacy_erp_pol_{_token(detail_id)}") is None
                ):
                    new_lines.add(detail_id)
                _upsert_purchase_line(importer, context, order, detail_id, line, unit_price)
    _customer_invoice(importer, context, partner_by_cp, number, buysell, sale_groups, unit_price)
    _vendor_bills(importer, index, report, context, partner_by_cp, number)
    report.bump("transactions", "created" if fresh_document else "skipped")
    for outcome in line_outcomes:
        if outcome == "rejected":
            report.bump("transaction_lines", "rejected")
        else:
            report.bump("transaction_lines", "created" if outcome in new_lines else "skipped")
    return sale_ids, trailers


def _upsert_order(importer, context, partner_by_cp, header, buysell, number, model_name, xml_id, incoterm_code):
    env = importer.env
    model = env[model_name].with_context(**_import_context())
    partner_field = "CustID" if model_name == "sale.order" else "VendorID"
    partner_id = _partner_id(importer, partner_by_cp, header.get("CpID")) or _partner_id(
        importer, partner_by_cp, buysell.get(partner_field)
    )
    if not partner_id:
        raise ValueError(f"{model_name} {header.get('PONumber')} has no partner")
    basis = (header.get("PriceBasis") or "").strip() or (buysell.get("PriceBasis") or "")
    values = {
        "partner_id": partner_id,
        "name": (header.get("PONumber") or "").strip(),
        "origin": number,
        "date_order": _date(header.get("PODate") or buysell.get("OrderDt")),
    }
    values["user_id"] = (context.get("salesperson") or {}).get(number) or False
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
    existing = _existing(importer, model_name, xml_id)
    if existing is not None and existing.state not in ("draft", "sent"):
        return existing
    return importer._upsert(model, xml_id, values, _silent(), None)


def _silent():
    class _Report:
        def bump(self, *_args, **_kwargs):
            return None

    return _Report()


def _upsert_sale_line(importer, context, order, detail_id, line, unit_price):
    if order.state not in ("draft", "sent"):
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
    if order.state not in ("draft", "sent", "to approve"):
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
        return
    header = next(iter(sale_groups.values()))[0][2]
    partner_id = _partner_id(importer, partner_by_cp, header.get("CpID")) or _partner_id(
        importer, partner_by_cp, buysell.get("CustID")
    )
    if not partner_id:
        return
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
        return
    signed = sum(item[2]["quantity"] * item[2]["price_unit"] for item in commands)
    if signed < 0:
        for item in commands:
            item[2]["price_unit"] = abs(item[2]["price_unit"])
    invoice_date = _date(buysell.get("InvoiceDt") or buysell.get("OrderDt"))
    _move(
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


def _vendor_bills(importer, index, report, context, partner_by_cp, number):
    from odoo.addons.plasticos_partner_import.erp.native_orders import (  # noqa: PLC0415
        EXPENSE_GL,
        FREIGHT_GL,
        MATERIAL_GL,
    )

    material = context["material_account"]
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
        if gl_acct == FREIGHT_GL:
            costs["freight"][number] = costs["freight"].get(number, 0.0) + amount
            report.anomaly("Payables", payable_id or number, "Inland Freight is not posted to Material Cost")
            continue
        if gl_acct in EXPENSE_GL:
            costs["other"][number] = costs["other"].get(number, 0.0) + amount
            continue
        if gl_acct != MATERIAL_GL:
            report.anomaly("Payables", payable_id or number, f"GL lookup {gl_acct or 'blank'} has no native account")
            continue
        partner_id = _partner_id(importer, partner_by_cp, row.get("CpID"))
        if material is None or not journal or not partner_id or not payable_id or not amount:
            continue
        invoice_date = _date(row.get("InvoiceDt")) or _date(index.buysells.get(number, {}).get("OrderDt"))
        _move(
            importer,
            f"legacy_erp_ininv_{_token(payable_id)}",
            {
                "move_type": "in_refund" if amount < 0 else "in_invoice",
                "partner_id": partner_id,
                "journal_id": journal.id,
                "invoice_date": (invoice_date or "")[:10] or False,
                "invoice_origin": number,
                "ref": (row.get("InvoiceNo") or payable_id).strip(),
                "invoice_line_ids": _vendor_bill_lines(importer, context, index, material, number, amount, row),
            },
        )


def _move(importer, xml_id, values):
    existing = _existing(importer, "account.move", xml_id)
    if existing is not None:
        return existing
    model = importer.env["account.move"].with_context(**_import_context())
    record = model.create(values)
    importer._write_identity_marker(model, xml_id, record)
    _settle_historical(record)
    return record


def _confirm_sales(importer, index, pending_sales, context):
    del index
    orders = importer.env["sale.order"].browse(list(pending_sales)).exists()
    drafts = orders.filtered(lambda order: order.state in ("draft", "sent"))
    if drafts and "approved" in drafts._fields:
        drafts.write({"approved": True})
    if drafts:
        costs = context.get("costs") or {}
        confirm = drafts.with_context(**_confirm_context(context, costs))
        try:
            with importer.env.cr.savepoint():
                confirm.action_confirm()
        except Exception as exc:  # noqa: BLE001 - one blocked order must not drop the load
            _logger.info("ERP batch confirm failed (%s); confirming individually", type(exc).__name__)
            for order in drafts:
                if order.state not in ("draft", "sent"):
                    continue
                try:
                    with importer.env.cr.savepoint():
                        order.with_context(**_confirm_context(context, costs)).action_confirm()
                except Exception as one:  # noqa: BLE001 - keep the imported order even if confirm fails
                    _logger.info("ERP sale %s was not confirmed: %s", order.name, one)
    for order in orders:
        trailers = [item for item in pending_sales.get(order.id, []) if item]
        if trailers and order.picking_ids and "carrier_tracking_ref" in order.picking_ids._fields:
            order.picking_ids.write({"carrier_tracking_ref": ", ".join(dict.fromkeys(trailers))})


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
    if cached:
        return cached
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


def _remember_salesperson(importer, context, number, buysell, worksheet_commission) -> None:
    """Worksheet referrer, not the customer's current default rep."""
    from odoo.addons.plasticos_partner_import.erp.mapping import sales_rep_name  # noqa: PLC0415

    code, amount = worksheet_commission(buysell)
    context.setdefault("commission", {})[number] = amount
    user_id = False
    if code:
        name = sales_rep_name(code)
        cache = context.setdefault("users_by_name", {})
        if name and name not in cache:
            cache[name] = importer._user_ids_by_name({name}).get(name) or False
        user_id = cache.get(name) if name else False
    context.setdefault("salesperson", {})[number] = user_id or False


def _confirm_context(context, costs) -> dict:
    return {
        **_import_context(),
        "erp_freight_by_origin": costs.get("freight") or {},
        "erp_other_by_origin": costs.get("other") or {},
        "erp_salesperson_by_origin": context.get("salesperson") or {},
        "erp_commission_by_origin": context.get("commission") or {},
        "erp_note_by_origin": context.get("notes") or {},
        "erp_state_by_origin": context.get("states") or {},
        "erp_carrier_by_origin": context.get("carriers") or {},
    }


def _settle_historical(move) -> None:
    """Post the historical invoice and clear its open balance.

    QuickBooks already settled these documents. A draft or open bill would sit
    in the live vendor-bill queue. The offset lands on retained earnings, not
    on Material Cost, and no payment is created.
    """
    posted = move.with_context(**_import_context())
    if posted.state == "draft":
        posted.action_post()
    if posted.state != "posted" or posted.currency_id.is_zero(posted.amount_residual):
        return
    open_lines = posted.line_ids.filtered(
        lambda line: line.account_id.account_type in ("asset_receivable", "liability_payable") and not line.reconciled
    )
    clearing = _clearing_account(posted.env)
    journal = posted.env["account.journal"].search([("type", "=", "general")], limit=1)
    if not open_lines or not clearing or not journal:
        raise ValueError(f"historical move {posted.ref or posted.name} is still open")
    for line in open_lines:
        entry = (
            posted.env["account.move"]
            .with_context(**_import_context())
            .create(
                {
                    "move_type": "entry",
                    "date": posted.date,
                    "ref": posted.ref or posted.name,
                    "journal_id": journal.id,
                    "line_ids": [
                        Command.create(
                            {
                                "name": "Historical settlement",
                                "account_id": line.account_id.id,
                                "partner_id": line.partner_id.id,
                                "debit": line.credit,
                                "credit": line.debit,
                            }
                        ),
                        Command.create(
                            {
                                "name": "Historical settlement",
                                "account_id": clearing.id,
                                "debit": line.debit,
                                "credit": line.credit,
                            }
                        ),
                    ],
                }
            )
        )
        entry.action_post()
        account_id = line.account_id.id
        (
            line + entry.line_ids.filtered(lambda item, account_id=account_id: item.account_id.id == account_id)
        ).reconcile()


_RETAINED_EARNINGS_CODE = "999998"


def _clearing_account(env):
    accounts = env["account.account"].search([("account_type", "=", "equity_unaffected")])
    chosen = accounts.filtered(lambda account: (account.code or "") == _RETAINED_EARNINGS_CODE)[:1]
    return chosen or accounts[:1]


def _import_context() -> dict:
    return {
        "import_mode": True,
        "tracking_disable": True,
        "mail_create_nolog": True,
        "mail_notrack": True,
    }
