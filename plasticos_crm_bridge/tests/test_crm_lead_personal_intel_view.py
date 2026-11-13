"""The Personal Intel page follows the opportunity partner's kind: individuals only.

The page modifier reads only fields present in the form. A dotted path such as
``partner_id.is_company`` cannot be evaluated by Odoo 19: the many2one is an id
in the evaluation context, so the form crashed on save and the web client never
hid the page.
"""

from __future__ import annotations

import re

from lxml import etree

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.tests import Form
from odoo.tests.common import tagged

PAGE_XPATH = "//page[@name='personal_intel_tab']"
MODIFIERS = ("invisible", "readonly", "required", "column_invisible")
# A name followed by an attribute access, outside string literals; parent.* and context.* are evaluable.
DOTTED_PATH = re.compile(r"(?<![\w'])(?!parent\.|context\.)[a-z_]\w*\.[a-z_]\w*")


@tagged("post_install", "-at_install", "plasticos", "crm_bridge", "opportunity")
class TestCrmLeadPersonalIntelView(PlasticosTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls._create_partner("Personal Intel Company Co")
        cls.person = cls.env["res.partner"].create({"name": "Personal Intel Person", "is_company": False})

    def _form(self, partner=None):
        form = Form(self.env["crm.lead"].with_context(default_type="opportunity", default_name="Personal Intel"))
        if partner:
            form.partner_id = partner
        return form

    def _page_hidden(self, form):
        # The page's invisible modifier is folded into every field it contains.
        return form._get_modifier("partner_personal_intel", "invisible")

    def test_page_is_hidden_for_a_company_partner(self):
        self.assertTrue(self._page_hidden(self._form(self.company)))

    def test_page_is_shown_for_an_individual_partner(self):
        self.assertFalse(self._page_hidden(self._form(self.person)))

    def test_page_is_hidden_without_a_partner(self):
        self.assertTrue(self._page_hidden(self._form()))

    def test_page_modifier_reads_only_fields_of_the_form(self):
        arch = etree.fromstring(self.env["crm.lead"].get_view(view_type="form")["arch"])
        [page] = arch.xpath(PAGE_XPATH)
        self.assertEqual(page.get("invisible"), "not partner_id or partner_is_company")
        self.assertTrue(arch.xpath("//field[@name='partner_is_company']"))

    def test_opportunity_form_saves_with_a_partner(self):
        for partner in (self.company, self.person):
            with self.subTest(partner=partner.name):
                lead = self._form(partner).save()
                self.assertEqual(lead.partner_id, partner)
                self.assertEqual(lead.partner_is_company, partner.is_company)

    def test_bridge_views_use_no_dotted_path_in_a_modifier(self):
        view_ids = (
            self.env["ir.model.data"]
            .search([("module", "=", "plasticos_crm_bridge"), ("model", "=", "ir.ui.view")])
            .mapped("res_id")
        )
        self.assertTrue(view_ids)
        offenders = []
        for view in self.env["ir.ui.view"].browse(view_ids):
            for node in etree.fromstring(view.arch_db.encode()).iter(tag=etree.Element):
                for modifier in MODIFIERS:
                    expression = node.get(modifier) or ""
                    if DOTTED_PATH.search(re.sub(r"'[^']*'", "", expression)):
                        offenders.append(f"{view.name}: {node.tag} {modifier}={expression!r}")
        self.assertFalse(offenders)
