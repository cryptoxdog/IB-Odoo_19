"""The 19.0.5.11.1 post-migrate retires a Sheet material grade left by 19.0.5.11.0."""

import importlib.util
import uuid

from odoo.modules.module import get_module_path
from odoo.tests import TransactionCase, tagged


def _migration():
    path = get_module_path("plasticos_material_profile") + "/migrations/19.0.5.11.1/post-migrate.py"
    spec = importlib.util.spec_from_file_location("sheet_grade_post_migrate", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@tagged("post_install", "-at_install")
class TestSheetGradeRetirement(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({"name": "Sheet Grade Facility", "is_company": True})
        cls.Profile = cls.env["plasticos.material.profile"]

    def _polymer(self):
        code = f"SG-{uuid.uuid4().hex[:8].upper()}"
        return self.env["plasticos.polymer"].create({"name": f"Sheet Grade {code}", "code": code})

    def _sheet_grade(self):
        grade = self.env["plasticos.material.grade"].create({"name": "Sheet", "code": "SHEET"})
        self.env["ir.model.data"].create(
            {
                "module": "plasticos_material_profile",
                "name": "material_grade_sheet",
                "model": "plasticos.material.grade",
                "res_id": grade.id,
                "noupdate": True,
            }
        )
        return grade

    def _migrate(self):
        _migration().migrate(self.env.cr, "19.0.5.11.0")
        self.env.invalidate_all()

    def test_absent_sheet_grade_is_a_no_op(self):
        self._migrate()
        self.assertFalse(self.env["plasticos.material.grade"].search([("code", "=", "SHEET")]))

    def test_unreferenced_sheet_grade_is_removed(self):
        self._sheet_grade()
        self._migrate()
        self.assertFalse(self.env["plasticos.material.grade"].search([("code", "=", "SHEET")]))
        self.assertFalse(self.env.ref("plasticos_material_profile.material_grade_sheet", raise_if_not_found=False))

    def test_referenced_sheet_grade_is_archived(self):
        grade = self._sheet_grade()
        profile = self.Profile.create(
            {
                "partner_id": self.partner.id,
                "polymer_id": self._polymer().id,
                "material_grade_id": grade.id,
            }
        )
        self._migrate()
        grade.invalidate_recordset()
        self.assertFalse(grade.active)
        self.assertEqual(profile.material_grade_id, grade)

    def test_rerun_changes_nothing(self):
        grade = self._sheet_grade()
        self.Profile.create(
            {
                "partner_id": self.partner.id,
                "polymer_id": self._polymer().id,
                "material_grade_id": grade.id,
            }
        )
        self._migrate()
        self._migrate()
        grade.invalidate_recordset()
        self.assertFalse(grade.active)
