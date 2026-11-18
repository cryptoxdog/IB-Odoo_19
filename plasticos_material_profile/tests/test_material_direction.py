"""Create-time direction and the partner + polymer + form + grade + direction key."""

import uuid

from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


def _code(prefix):
    return f"{prefix}-{uuid.uuid4().hex[:8].upper()}"


@tagged("post_install", "-at_install")
class TestMaterialDirection(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.profile = cls.env["plasticos.material.profile"]
        cls.polymer = cls.env["plasticos.polymer"].create({"name": "Direction Polymer", "code": _code("DIR")})
        cls.form = cls.env["plasticos.material.form"].create({"name": "Direction Form", "code": _code("DF")})

    def _site(self, name, *, supplier_rank=0, customer_rank=0, label=None):
        company = self.env["res.partner"].create(
            {
                "name": name,
                "is_company": True,
                "supplier_rank": supplier_rank,
                "customer_rank": customer_rank,
            }
        )
        values = {"name": f"{name} Site", "parent_id": company.id, "type": "delivery", "is_company": False}
        if label and "erp_address_label" in self.env["res.partner"]._fields:
            values["erp_address_label"] = label
        return self.env["res.partner"].create(values)

    def _create(self, partner, **extra):
        values = {"partner_id": partner.id, "polymer_id": self.polymer.id, "form_id": self.form.id}
        values.update(extra)
        return self.profile.create(values)

    def test_direction_defaults_from_ranks_and_a_pickup_label(self):
        supplier = self._create(self._site("Direction Supplier", supplier_rank=1))
        buyer = self._create(self._site("Direction Buyer", customer_rank=1))
        both = self._create(self._site("Direction Both", supplier_rank=1, customer_rank=1))
        self.assertEqual(supplier.direction, "out")
        self.assertEqual(buyer.direction, "in")
        self.assertFalse(both.direction)
        if "erp_address_label" in self.env["res.partner"]._fields:
            override = self._create(self._site("Direction Pickup Buyer", customer_rank=1, label="PICK UP"))
            self.assertEqual(override.direction, "out")
        explicit = self._create(self._site("Direction Explicit", supplier_rank=1), direction="in")
        self.assertEqual(explicit.direction, "in")

    def test_in_and_out_of_the_same_material_both_save_and_a_repeat_is_reported(self):
        partner = self._site("Direction Pair", supplier_rank=1, customer_rank=1)
        outgoing = self._create(partner, direction="out")
        incoming = self._create(partner, direction="in")
        self.assertEqual(outgoing.direction, "out")
        self.assertEqual(incoming.direction, "in")
        with self.assertRaises(ValidationError):
            self._create(partner, direction="out")
