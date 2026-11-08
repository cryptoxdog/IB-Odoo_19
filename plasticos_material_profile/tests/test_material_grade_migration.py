"""The 19.0.5.11.0 post-migrate moves the six former forms onto material grades."""

import importlib.util
import uuid

from odoo.addons.plasticos_material_profile.grade_codes import FORMER_FORM_CODES
from odoo.addons.plasticos_material_profile.grade_migration import (
    GradeMigrationError,
    move_former_forms,
    origin_note,
)
from odoo.modules.module import get_module_path
from odoo.tests import TransactionCase, tagged


def _migration():
    path = get_module_path("plasticos_material_profile") + "/migrations/19.0.5.11.0/post-migrate.py"
    spec = importlib.util.spec_from_file_location("material_grade_post_migrate", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@tagged("post_install", "-at_install")
class TestMaterialGradeMigration(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.cr.execute("ALTER TABLE plasticos_material_profile ADD COLUMN IF NOT EXISTS origin_form_id integer")
        Form = cls.env["plasticos.material.form"]
        cls.former = {code: Form.create({"name": f"Former {code.title()}", "code": code}) for code in FORMER_FORM_CODES}
        cls.regrind = Form.search([("code", "=", "REGRIND")], limit=1)
        cls.grades = {grade.code: grade for grade in cls.env["plasticos.material.grade"].search([])}
        cls.partner = cls.env["res.partner"].create({"name": "Grade Migration Facility", "is_company": True})
        cls.Profile = cls.env["plasticos.material.profile"]

    def _polymer(self):
        code = f"GM-{uuid.uuid4().hex[:8].upper()}"
        return self.env["plasticos.polymer"].create({"name": f"Grade Migration {code}", "code": code})

    def _profile(self, form=None, origin=None, **vals):
        profile = self.Profile.create(
            {
                "partner_id": self.partner.id,
                "polymer_id": self._polymer().id,
                "form_id": form.id if form else False,
                **vals,
            }
        )
        if origin:
            self.env.flush_all()
            self.env.cr.execute(
                "UPDATE plasticos_material_profile SET origin_form_id = %s WHERE id = %s", (origin.id, profile.id)
            )
        return profile

    def test_former_forms_and_origin_forms_become_grades(self):
        drums_form = self._profile(form=self.former["DRUMS"])
        drums_origin = self._profile(origin=self.former["DRUMS"])
        disagreeing = self._profile(form=self.former["PALLETS"], origin=self.former["CRATES"])
        unmapped = self._profile(origin=self.regrind, freeform_notes="kept")

        _migration().migrate(self.env.cr, "19.0.5.10.0")
        self.env.invalidate_all()

        self.assertEqual(drums_form.material_grade_id, self.grades["DRUMS"])
        self.assertFalse(drums_form.form_id)
        self.assertEqual(drums_origin.material_grade_id, self.grades["DRUMS"])
        self.assertFalse(drums_origin.freeform_notes)
        self.assertEqual(disagreeing.material_grade_id, self.grades["PALLETS"])
        self.assertFalse(disagreeing.form_id)
        self.assertIn(origin_note(self.former["CRATES"]), disagreeing.freeform_notes.splitlines())
        self.assertFalse(unmapped.material_grade_id)
        self.assertEqual(unmapped.freeform_notes, f"kept\n{origin_note(self.regrind)}")
        self.assertFalse(self.Profile.search_count([("form_id", "in", [f.id for f in self.former.values()])]))
        for code in ("PALLETS", "CRATES", "DRUMS", "IBC_TOTES"):
            self.assertTrue(
                self.env["plasticos.grade.template"].search_count([("material_grade_id.code", "=", code)]),
                code,
            )

    def test_rerun_changes_nothing(self):
        disagreeing = self._profile(form=self.former["BUCKETS"], origin=self.former["TOTES"])
        first = move_former_forms(self.env, "plasticos.material.profile", notes_field="freeform_notes")
        notes = disagreeing.freeform_notes
        second = move_former_forms(self.env, "plasticos.material.profile", notes_field="freeform_notes")
        self.assertEqual(first[0], 1)
        self.assertEqual(second, (0, first[1], first[2]))
        self.assertEqual(disagreeing.freeform_notes, notes)
        self.assertEqual(disagreeing.material_grade_id, self.grades["BUCKETS"])

    def test_origin_row_neither_copied_nor_noted_raises(self):
        self._profile(origin=self.former["DRUMS"], material_grade_id=self.grades["BUCKETS"].id)
        with self.assertRaises(GradeMigrationError):
            move_former_forms(self.env, "plasticos.material.profile", notes_field="freeform_notes")
