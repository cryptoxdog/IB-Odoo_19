import uuid

from psycopg2 import IntegrityError

from odoo.addons.plasticos_base.tests.common import PlasticosTestCase
from odoo.exceptions import ValidationError
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestPlasticosMaterialForm(PlasticosTestCase):
    """Test suite for plasticos.material.form"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.MaterialForm = cls.env["plasticos.material.form"]

    def _create_form(self, **kwargs):
        """Helper to create plasticos.material.form with unique defaults"""
        unique = uuid.uuid4().hex[:6].upper()
        code = kwargs.pop("code", f"FORM-{unique}")
        vals = {
            "name": f"Test Form {unique}",
            "code": code,
        }
        vals.update(kwargs)
        return self.MaterialForm.create(vals)

    # ========================================================================
    # CREATION TESTS
    # ========================================================================

    def test_create_basic(self):
        """Test basic record creation"""
        record = self._create_form()
        self.assertTrue(record.exists())
        self.assertTrue(record.name)
        self.assertTrue(record.code)

    def test_constraint_name_required(self):
        """Test name is required"""
        raised = False
        try:
            self.MaterialForm.create({"code": "NO-NAME"})
        except (ValidationError, IntegrityError):
            raised = True
        self.assertTrue(raised, "Expected exception was not raised")

    def test_constraint_code_required(self):
        """Test code is required"""
        raised = False
        try:
            self.MaterialForm.create({"name": "No Code Form"})
        except (ValidationError, IntegrityError):
            raised = True
        self.assertTrue(raised, "Expected exception was not raised")

    def test_constraint_code_unique(self):
        """Test code must be unique"""
        self._create_form(code="UNIQUE-FORM")
        raised = False
        try:
            self._create_form(code="UNIQUE-FORM")
        except (ValidationError, IntegrityError):
            raised = True
        self.assertTrue(raised, "Expected exception was not raised")
