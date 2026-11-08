"""Nullable material-profile form identity."""

import uuid

from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


def _unique_code(prefix):
    return f"{prefix}-{uuid.uuid4().hex[:8].upper()}"


@tagged("post_install", "-at_install")
class TestNullableFormUniqueness(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.profile = cls.env["plasticos.material.profile"]
        parent = cls.env["res.partner"].create({"name": "Nullable Form Parent", "is_company": True})
        cls.partner = cls.env["res.partner"].create(
            {"name": "Nullable Form Facility", "parent_id": parent.id, "is_company": True}
        )
        cls.polymer = cls.env["plasticos.polymer"].create(
            {"name": "Nullable Form Polymer", "code": _unique_code("NFP")}
        )
        cls.form = cls.env["plasticos.material.form"].create({"name": "Nullable Form", "code": _unique_code("NFF")})

    def test_repeated_specified_triple_raises(self):
        vals = {
            "partner_id": self.partner.id,
            "polymer_id": self.polymer.id,
            "form_id": self.form.id,
        }
        self.profile.create(vals)
        with self.assertRaises(ValidationError):
            self.profile.create(vals)

    def test_repeated_empty_form_raises_and_replay_returns_the_same_row(self):
        first = self.profile.create(
            {
                "partner_id": self.partner.id,
                "polymer_id": self.polymer.id,
                "form_id": False,
            }
        )
        replayed = self.profile.search(
            [
                ("partner_id", "=", self.partner.id),
                ("polymer_id", "=", self.polymer.id),
                ("form_id", "=", False),
            ]
        )
        self.assertEqual(replayed, first)
        with self.assertRaises(ValidationError):
            self.profile.create(
                {
                    "partner_id": self.partner.id,
                    "polymer_id": self.polymer.id,
                    "form_id": False,
                }
            )
        self.assertEqual(
            self.profile.search(
                [
                    ("partner_id", "=", self.partner.id),
                    ("polymer_id", "=", self.polymer.id),
                    ("form_id", "=", False),
                ]
            ),
            first,
        )

    def test_specified_and_unspecified_forms_both_save(self):
        specified = self.profile.create(
            {
                "partner_id": self.partner.id,
                "polymer_id": self.polymer.id,
                "form_id": self.form.id,
            }
        )
        unspecified = self.profile.create(
            {
                "partner_id": self.partner.id,
                "polymer_id": self.polymer.id,
                "form_id": False,
            }
        )
        self.assertNotEqual(specified.id, unspecified.id)
        self.assertEqual(specified.form_id, self.form)
        self.assertFalse(unspecified.form_id)

    def test_two_grades_without_form_both_save_and_a_repeated_grade_raises(self):
        Grade = self.env["plasticos.material.grade"]
        drums = Grade.search([("code", "=", "DRUMS")], limit=1)
        buckets = Grade.search([("code", "=", "BUCKETS")], limit=1)
        base = {"partner_id": self.partner.id, "polymer_id": self.polymer.id, "form_id": False}
        first = self.profile.create({**base, "material_grade_id": drums.id})
        second = self.profile.create({**base, "material_grade_id": buckets.id})
        ungraded = self.profile.create(base)
        self.assertEqual(len(first | second | ungraded), 3)
        with self.assertRaises(ValidationError):
            self.profile.create({**base, "material_grade_id": drums.id})
