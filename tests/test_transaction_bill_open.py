"""Vendor and freight bills on a transaction open like the customer invoice."""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
VIEW_PATH = REPO_ROOT / "plasticos_transaction" / "views" / "transaction_views.xml"
WIDGET_PATH = REPO_ROOT / "plasticos_transaction" / "static" / "src" / "fields" / "many2many_tags_open.js"
MANIFEST_PATH = REPO_ROOT / "plasticos_transaction" / "__manifest__.py"


def test_bill_tags_use_open_widget():
    view = VIEW_PATH.read_text()
    assert 'name="vendor_bill_ids" widget="many2many_tags_open"' in view
    assert 'name="freight_bill_ids" widget="many2many_tags_open"' in view


def test_open_widget_uses_formview_action():
    source = WIDGET_PATH.read_text()
    assert 'registry.category("fields").add("many2many_tags_open"' in source
    assert '"get_formview_action"' in source


def test_open_widget_is_in_backend_assets():
    manifest = MANIFEST_PATH.read_text()
    assert "plasticos_transaction/static/src/fields/many2many_tags_open.js" in manifest
    assert "plasticos_transaction/static/src/fields/many2many_tags_open.scss" in manifest
