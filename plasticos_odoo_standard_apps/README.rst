PlasticOS — Standard Odoo Apps (auto)
=======================================

Purpose
-------
Thin module with **no Python models**. It declares **native Odoo addons** you use
on the home dashboard so they **auto-install** on new databases when ``base`` is
available (``auto_install`` on ``base``).

Tiles covered (CE-safe ``depends``)
-----------------------------------
===================  =========================
Home label           Technical module
===================  =========================
Discuss              ``mail``
Calendar             ``calendar``
Contacts             ``contacts``
CRM                  ``crm``
Sales                ``sale_management``
Dashboards           ``spreadsheet_dashboard``
Accounting           ``account``
Purchase             ``purchase``
Inventory            ``stock``
Barcode              ``barcodes`` (product / GS1 foundations)
===================  =========================

**Not** in ``depends`` (avoid breaking non-Enterprise / CI trees):

- **AI** — often Enterprise-only; add e.g. ``ai`` when that module exists on your build.
- **Inventory Barcode app** — Enterprise ``stock_barcode``; add if you use the scanner app.
- **Full accounting** — some builds use Enterprise ``account_accountant``.

Odoo.sh (Enterprise)
--------------------
Edit ``__manifest__.py`` ``depends`` and append, as needed::

    "ai",
    "stock_barcode",

Then upgrade this module. PlasticOS modules stay separate (already auto-installed).
