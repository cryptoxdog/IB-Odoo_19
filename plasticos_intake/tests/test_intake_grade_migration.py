"""The 19.0.5.4.0 post-migrate moves former forms on intakes to grades and sets the form to OTHER."""

import importlib.util

from odoo.addons.plasticos_material_profile.grade_migration import origin_note
from odoo.modules.module import get_module_path
from odoo.tests import TransactionCase, tagged


def _migration():
    path = get_module_path("plasticos_intake") + "/migrations/19.0.5.4.0/post-migrate.py"
    spec = importlib.util.spec_from_file_location("intake_grade_post_migrate", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@tagged("post_install", "-at_install")
class TestIntakeGradeMigration(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.cr.execute("ALTER TABLE plasticos_intake ADD COLUMN IF NOT EXISTS origin_form_id integer")
        Form = cls.env["plasticos.material.form"]
        cls.drums_form = Form.create({"name": "Former Drums", "code": "DRUMS"})
        cls.crates_form = Form.create({"name": "Former Crates", "code": "CRATES"})
        cls.other = Form.search([("code", "=", "OTHER")], limit=1)
        cls.polymer = cls.env["plasticos.polymer"].search([("code", "=", "HDPE")], limit=1)
        cls.grades = {grade.code: grade for grade in cls.env["plasticos.material.grade"].search([])}

    def _intake(self, form, origin=None):
        intake = self.env["plasticos.intake"].create(
            {"pending_company_name": "Grade Migration Supplier", "polymer_id": self.polymer.id, "form_id": form.id}
        )
        if origin:
            self.env.flush_all()
            self.env.cr.execute("UPDATE plasticos_intake SET origin_form_id = %s WHERE id = %s", (origin.id, intake.id))
        return intake

    def test_former_form_becomes_grade_and_other(self):
        drums = self._intake(self.drums_form)
        disagreeing = self._intake(self.drums_form, origin=self.crates_form)
        origin_only = self._intake(self.other, origin=self.crates_form)

        migration = _migration()
        migration.migrate(self.env.cr, "19.0.5.3.0")
        self.env.invalidate_all()
        notes = disagreeing.intake_notes
        migration.migrate(self.env.cr, "19.0.5.3.0")
        self.env.invalidate_all()

        self.assertEqual(drums.form_id, self.other)
        self.assertEqual(drums.material_grade_id, self.grades["DRUMS"])
        self.assertEqual(disagreeing.form_id, self.other)
        self.assertEqual(disagreeing.material_grade_id, self.grades["DRUMS"])
        self.assertIn(origin_note(self.crates_form), notes.splitlines())
        self.assertEqual(disagreeing.intake_notes, notes)
        self.assertEqual(origin_only.material_grade_id, self.grades["CRATES"])
        self.assertEqual(origin_only.form_id, self.other)
