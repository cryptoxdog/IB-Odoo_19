"""Profit snapshot is the only margin display on the transaction form."""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
FORM = REPO_ROOT / "plasticos_transaction" / "views" / "transaction_views.xml"
BULK = REPO_ROOT / "plasticos_transaction" / "views" / "transaction_bulk_update_wizard_views.xml"
UX = REPO_ROOT / "plasticos_transaction" / "views" / "transaction_ux.xml"
CLAIMS = REPO_ROOT / "plasticos_claims" / "views" / "transaction_claims_bridge_views.xml"
MODEL = REPO_ROOT / "plasticos_transaction" / "models" / "transaction.py"


def test_form_groups_are_snapshot_freight_and_material():
    form = FORM.read_text()
    assert 'string="Profit Snapshot"' in form
    assert 'string="Freight"' in form
    assert 'name="material"' in form
    assert 'name="purchase_cost_total" string="Material Cost"' in form
    assert 'name="material_unit_cost"' in form
    assert 'name="final_weight" string="Material Weight"' in form
    assert 'name="lightweight_penalties" string="Weight Penalty"' in form
    assert 'name="other_expenses" string="Additional Costs"' in form
    assert "Recoveries" not in form
    assert 'widget="many2many_tags_open"' in form
    assert 'name="net_margin" class="o_plasticos_net_margin"' in form
    orders = form.split('name="orders"', 1)[1].split("</group>", 1)[0]
    assert orders.index('name="user_id"') < orders.index('name="product_id"')
    assert orders.index('name="product_id"') < orders.index('name="supplier_id"')
    assert orders.index('name="supplier_id"') < orders.index('name="buyer_id"')
    assert orders.index('name="buyer_id"') < orders.index('name="sale_order_id"')
    assert orders.index('name="sale_order_id"') < orders.index('name="purchase_order_ids"')
    delivery = form.split('name="delivery_order"', 1)[1].split("</group>", 1)[0]
    assert 'name="carrier_id"' in delivery
    assert 'name="freight_actual"' in delivery
    assert delivery.index('name="carrier_id"') < delivery.index('name="freight_actual"')
    assert delivery.index('name="freight_actual"') < delivery.index('name="delivery_order_id"')


def test_transaction_list_keeps_optional_columns():
    form = FORM.read_text()
    listing = form.split("<list", 1)[1].split("</list>", 1)[0]
    assert 'name="user_id" optional="show"' in listing
    assert 'name="sale_order_id" optional="show"' in listing
    assert 'name="purchase_order_ids" string="Purchase Orders" optional="hide"' in listing
    assert 'name="historical_margin" optional="show"' in listing
    assert 'name="revenue_total" optional="hide"' in listing
    assert 'id="action_transaction_view_list"' in form
    assert 'ref="view_transaction_tree"' in form
    bulk = BULK.read_text()
    assert 'id="view_plasticos_transaction_bulk_wizard_tree"' in bulk
    assert 'eval="99"' in bulk


def test_margin_banner_and_stat_button_are_gone():
    ux = UX.read_text()
    assert "Gross Margin:" not in ux
    assert "Negative Margin:" not in ux
    assert ">Margin</span>" not in ux
    assert "alert-success" not in ux
    assert 'name="carrier_id"' not in ux
    assert 'decoration-danger">gross_margin' in ux


def test_quality_penalty_is_yes_no_on_the_material_group():
    bridge = CLAIMS.read_text()
    assert 'name="has_quality_claim" string="Quality Penalty"' in bridge
    assert "group[@name='material']" in bridge


def test_material_unit_cost_divides_material_cost_by_weight():
    source = MODEL.read_text()
    assert 'compute="_compute_material_unit_cost"' in source
    assert '@api.depends("purchase_cost_total", "final_weight")' in source
    assert "rec.material_unit_cost = (rec.purchase_cost_total or 0.0) / weight if weight else 0.0" in source
