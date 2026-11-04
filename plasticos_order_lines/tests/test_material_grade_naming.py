"""The material grade is named after the polymer and before the form."""

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestMaterialGradeNaming(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.polymer = cls.env["plasticos.polymer"].search([("code", "=", "HDPE")], limit=1)
        cls.grade = cls.env["plasticos.material.grade"].search([("code", "=", "DRUMS")], limit=1)
        cls.form = cls.env["plasticos.material.form"].search([("code", "=", "REGRIND")], limit=1)
        cls.product = cls.env["product.product"].create({"name": "HDPE", "list_price": 0.5})
        company = cls.env["res.partner"].create({"name": "Grade Naming Co", "is_company": True})
        cls.facility = cls.env["res.partner"].create(
            {"name": "Grade Naming Plant", "is_company": True, "parent_id": company.id}
        )
        cls.expected = f"HDPE - {cls.grade.name} - {cls.form.name}"

    def _line_vals(self):
        return {
            "product_id": self.product.id,
            "material_grade_id": self.grade.id,
            "form_id": self.form.id,
        }

    def test_profile_name_puts_grade_between_polymer_and_form(self):
        profile = self.env["plasticos.material.profile"].create(
            {
                "partner_id": self.facility.id,
                "polymer_id": self.polymer.id,
                "material_grade_id": self.grade.id,
                "form_id": self.form.id,
            }
        )
        self.assertEqual(profile.display_name, f"{self.polymer.name} {self.grade.name} {self.form.name}")

    def test_sale_line_description_and_name(self):
        order = self.env["sale.order"].create({"partner_id": self.facility.id})
        line = self.env["sale.order.line"].create({"order_id": order.id, **self._line_vals()})
        self.assertEqual(line.material_description, self.expected)
        self.assertEqual(line.name.splitlines()[0], self.expected)
        self.assertIn("HDPE", line.name.splitlines()[1:])

    def test_purchase_line_description_and_name(self):
        order = self.env["purchase.order"].create({"partner_id": self.facility.id})
        line = self.env["purchase.order.line"].create({"order_id": order.id, **self._line_vals()})
        self.assertEqual(line.material_description, self.expected)
        self.assertEqual(line.name.splitlines()[0], self.expected)

    def test_purchase_order_from_profile_names_the_grade(self):
        profile = self.env["plasticos.material.profile"].create(
            {
                "partner_id": self.facility.id,
                "polymer_id": self.polymer.id,
                "material_grade_id": self.grade.id,
                "form_id": self.form.id,
            }
        )
        action = profile.action_create_purchase_order()
        line_vals = action["context"]["default_order_line"][0][2]
        self.assertEqual(line_vals["material_grade_id"], self.grade.id)
        self.assertTrue(line_vals["name"].endswith(f" - {self.grade.name} - {self.form.name} - Grade Naming Plant"))
