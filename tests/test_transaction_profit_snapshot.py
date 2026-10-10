"""Transaction UI harvest: one margin presentation, real default list, no importer or security drift.

Source-level guards for the view files. Runtime view inheritance is proven by
``plasticos_transaction/tests/test_transaction_form_ui.py`` under ``odoo --test-enable``.
"""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
FORM = REPO_ROOT / "plasticos_transaction" / "views" / "transaction_views.xml"
BULK = REPO_ROOT / "plasticos_transaction" / "views" / "transaction_bulk_update_wizard_views.xml"
UX = REPO_ROOT / "plasticos_transaction" / "views" / "transaction_ux.xml"
CLAIMS = REPO_ROOT / "plasticos_claims" / "views" / "transaction_claims_bridge_views.xml"
LOGISTICS = REPO_ROOT / "plasticos_logistics" / "views" / "transaction_load_views.xml"
MODEL = REPO_ROOT / "plasticos_transaction" / "models" / "transaction.py"
RECORD_RULES = REPO_ROOT / "plasticos_security_base" / "security" / "record_rules.xml"
SCSS = REPO_ROOT / "plasticos_transaction" / "static" / "src" / "fields" / "many2many_tags_open.scss"


def _section(text: str, start: str, end: str) -> str:
    return text.split(start, 1)[1].split(end, 1)[0]


def test_form_groups_are_snapshot_freight_and_material():
    form = FORM.read_text()
    assert 'string="Profit Snapshot" name="profit_snapshot"' in form
    assert 'string="Freight" name="freight"' in form
    assert 'string="Material" name="material"' in form
    assert 'string="Delivery Order" name="delivery_order"' in form
    assert "Recoveries" not in form
    assert 'name="purchase_order_ids" widget="many2many_tags_open"' in form
    assert 'name="net_margin" class="o_plasticos_net_margin"' in form

    snapshot = _section(form, 'name="profit_snapshot"', "</group>")
    expected = [
        'name="revenue_total"',
        'name="purchase_cost_total" string="Material Cost"',
        'name="freight_cost_total" string="Freight Cost"',
        'name="cost_total"',
        'name="gross_margin"',
        'name="commission_amount" string="Commission"',
        'name="net_margin"',
    ]
    positions = [snapshot.index(marker) for marker in expected]
    assert positions == sorted(positions)

    orders = _section(form, 'name="orders"', "</group>")
    order_fields = ["user_id", "product_id", "supplier_id", "buyer_id", "sale_order_id", "purchase_order_ids"]
    order_positions = [orders.index(f'name="{name}"') for name in order_fields]
    assert order_positions == sorted(order_positions)

    material = _section(form, 'name="material"', "</group>")
    assert 'name="final_weight" string="Material Weight"' in material
    assert 'name="lightweight_penalties" string="Weight Penalty"' in material

    freight = _section(form, 'name="freight"', "</group>")
    assert 'name="freight_chargebacks"' in freight
    assert 'name="other_expenses" string="Additional Costs"' in freight

    delivery = _section(form, 'name="delivery_order"', "</group>")
    assert delivery.index('name="carrier_id"') < delivery.index('name="freight_actual"')
    assert delivery.index('name="freight_actual"') < delivery.index('name="delivery_order_id"')


def test_form_shows_each_margin_field_once():
    form = FORM.read_text()
    form_arch = _section(form, 'id="view_transaction_form"', "</record>")
    for name in ("revenue_total", "cost_total", "gross_margin", "net_margin", "purchase_cost_total"):
        assert form_arch.count(f'name="{name}"') == 1, name


def test_transaction_list_keeps_lifecycle_decorations_and_optional_columns():
    form = FORM.read_text()
    listing = _section(form, 'id="view_transaction_tree"', "</record>")
    assert "decoration-info=\"state == 'draft'\"" in listing
    assert "decoration-muted=\"state in ('closed', 'cancelled')\"" in listing
    assert 'name="user_id" optional="show"' in listing
    assert 'name="sale_order_id" optional="show"' in listing
    assert 'name="purchase_order_ids" string="Purchase Orders" optional="hide"' in listing
    assert 'name="historical_sale_total" optional="show"' in listing
    assert 'name="historical_purchase_total" optional="show"' in listing
    assert 'name="historical_margin" optional="show"' in listing
    assert 'name="revenue_total" optional="hide"' in listing
    assert 'name="cost_total" optional="hide"' in listing
    assert 'name="state" widget="badge"' in listing


def test_default_list_is_pinned_by_wizard_priority_not_an_action_view_record():
    # ir.ui.view orders by priority, name, id: the wizard list name sorts first at the
    # default priority, so it must opt out. No ir.actions.act_window.view record is
    # needed (that route also needed audit-baseline entries).
    bulk = BULK.read_text()
    wizard_tree = _section(bulk, 'id="view_plasticos_transaction_bulk_wizard_tree"', "</record>")
    assert '<field name="priority" eval="99"/>' in wizard_tree
    # Odoo 19 resolves an embedded x2many list from list_view_ref; a view_id attribute is inert.
    assert "'list_view_ref': 'plasticos_transaction.view_plasticos_transaction_bulk_wizard_tree'" in bulk
    assert 'view_id="ref(' not in bulk
    assert "ir.actions.act_window.view" not in FORM.read_text()


def test_margin_banners_are_gone_and_ux_keeps_list_search_helpers():
    ux = UX.read_text()
    assert "Gross Margin:" not in ux
    assert "Negative Margin:" not in ux
    assert "alert-success" not in ux
    assert "alert-danger" not in ux
    assert ">Margin</span>" not in ux
    assert ">Net Margin</span>" in ux
    assert 'name="gross_margin"' not in _section(ux, 'id="transaction_form_ux"', "</record>")
    # The base form now owns these; the UX view must not inject them a second time.
    assert "group[@name='orders']" not in ux
    assert 'name="carrier_id"' not in _section(ux, 'id="transaction_form_ux"', "</record>")
    # Kept: supplier/buyer/material columns, negative-margin highlight, filter, carrier grouping.
    assert 'decoration-danger">gross_margin &lt; 0' in ux
    assert 'name="filter_negative_margin"' in ux
    assert 'name="group_carrier"' in ux
    assert "'group_by': 'carrier_id'" in ux


def test_net_margin_styling_rides_the_existing_asset():
    scss = SCSS.read_text()
    assert ".o_plasticos_net_margin" in scss
    assert "--bs-success-text-emphasis" in scss


def test_dependent_views_target_the_new_groups():
    bridge = CLAIMS.read_text()
    assert "group[@name='material']" in bridge
    assert 'name="has_quality_claim"' in bridge
    logistics = LOGISTICS.read_text()
    assert "//group[@name='delivery_order']/field[@name='delivery_order_id']" in logistics
    assert "group[@name='orders']/field[@name='carrier_id']" not in logistics


def test_harvest_is_display_only():
    # material_unit_cost was rejected: final_weight is a manual scale/buyer/supplier
    # weight the ERP importer never writes, so cost / final_weight reads 0.00 on every
    # imported transaction and misrepresents historical costs.
    source = MODEL.read_text()
    assert "material_unit_cost" not in source
    assert "_check_override_pct_range" in source  # PR #231 model untouched
    assert "debit_note_ids" in source  # PR #231 revenue accounting untouched
    # PR #229's broad purchase-order rule stays out (least-privilege rule set from #231).
    assert "rule_purchase_order_all_documents" not in RECORD_RULES.read_text()
