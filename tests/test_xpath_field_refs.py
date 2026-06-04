"""
XPath Field Reference Integrity Test
=====================================

Validates that every  //field[@name='X']  expression inside an XPath block
in a plasticos_* view actually references a field that exists on the view's
model.

Why this matters
----------------
Odoo raises a hard error at module-load time if an XPath targets a field
that does not exist in the parent view's arch, e.g.:

    <xpath expr="//field[@name='purchase_group_method']" position="attributes">

…when `purchase_group_method` is not present in `purchase.view_partner_property_form`.
That kills the whole registry load with "XPath expression found no nodes".

What this test catches
-----------------------
1. Wrong field name in XPath against an Odoo standard view
   (like the purchase_group_method incident).
2. Typos in field names in any inherited view.
3. Fields that were renamed or removed from a model.

What it does NOT catch
-----------------------
- XPaths that target elements other than <field> (e.g. <group>, <page>).
  Those require the parent view's arch to validate, not just the model's
  field registry. A separate static CI check handles structural XPaths.
- Optional "if model not installed" scenarios — if the model isn't
  registered at all we skip gracefully.

Usage
-----
Runs automatically as part of the post-install test suite.
To run manually:
    odoo-bin -u plasticos_base --test-tags xpath_field_refs --stop-after-init
"""

import re

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.tests import tagged

# Match   //field[@name='foo']   or   //field[@name="foo"]
# (also handles leading path segments like  //page/field[@name='...'])
_FIELD_NAME_RE = re.compile(r'field\[@name=[\'"](\w+)[\'"]\]')

# These field names appear in XPath expressions but live on *related* models
# reached through a relational field — not directly on the view's model.
# Add entries here only with a comment explaining why.
_KNOWN_RELATIONAL_XPATHS: set[str] = {
    # e.g.  //field[@name='product_id']/field[@name='standard_price']
    # standard_price lives on product.product, not the parent model
}


def _extract_xpath_field_names(arch_xml: str) -> list[tuple[str, str]]:
    """Return [(field_name, full_expr), ...] for every field[@name=X] in xpaths."""
    results = []
    # Find every <xpath ...> block in the arch
    for xpath_block in re.finditer(r'<xpath\s[^>]*expr=[\'"]([^\'"]+)[\'"]', arch_xml):
        expr = xpath_block.group(1)
        for m in _FIELD_NAME_RE.finditer(expr):
            results.append((m.group(1), expr))
    return results


@tagged("post_install", "-at_install", "xpath_field_refs")
class TestXPathFieldReferences(PlasticosTestCase):
    """All field[@name=X] in plasticos XPath expressions must name real model fields."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Collect all ir.ui.view records owned by a plasticos_* module
        cls.plasticos_views = (
            cls.env["ir.ui.view"]
            .search(
                [
                    ("model", "!=", False),
                    ("arch_db", "like", "xpath"),
                ]
            )
            .filtered(lambda v: cls._is_plasticos_view(v))
        )

    @staticmethod
    def _is_plasticos_view(view) -> bool:
        """True if this view was installed by one of our plasticos_* modules."""
        try:
            xml_id = view.get_xml_id().get(view.id, "") or ""
            return xml_id.startswith("plasticos_")
        except Exception:
            return False

    def test_xpath_field_names_exist_on_model(self):
        """Every field[@name=X] in a plasticos XPath must be a field on the view model."""
        errors: list[str] = []

        for view in self.plasticos_views:
            if not view.arch_db or not view.model:
                continue

            # Skip if model isn't installed (shouldn't happen in normal builds)
            if view.model not in self.env:
                continue

            model_fields = self.env[view.model]._fields
            xml_id = view.get_xml_id().get(view.id, view.name or str(view.id))

            for field_name, expr in _extract_xpath_field_names(view.arch_db):
                if field_name in _KNOWN_RELATIONAL_XPATHS:
                    continue
                if field_name not in model_fields:
                    errors.append(
                        f"  [{xml_id}] model={view.model}\n"
                        f"    XPath expr: {expr}\n"
                        f"    Field '{field_name}' does not exist on {view.model}\n"
                        f"    → Either the field was removed/renamed, or the XPath is wrong."
                    )

        if errors:
            self.fail(
                f"\n\n{'=' * 70}\n"
                f"INVALID XPATH FIELD REFERENCES IN PLASTICOS VIEWS\n"
                f"{'=' * 70}\n"
                f"Found {len(errors)} broken XPath field reference(s):\n\n" + "\n".join(errors) + f"\n{'=' * 70}\n"
                f"Fix: verify the field name is correct and exists on the model.\n"
                f"For external views (purchase, sale, etc.), check the parent\n"
                f"view's arch to confirm the field is actually there.\n"
            )
