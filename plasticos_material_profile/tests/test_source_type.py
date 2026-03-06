import uuid

from psycopg2 import IntegrityError

from odoo.addons.plasticos_base.tests.common import PlasticosTestCase
from odoo.exceptions import ValidationError
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestPlasticosSourceType(PlasticosTestCase):
    """Test suite for plasticos.source.type"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.SourceType = cls.env["plasticos.source.type"]

    def _create_type(self, **kwargs):
        """Helper to create plasticos.source.type with unique defaults"""
        unique = uuid.uuid4().hex[:6].upper()
        code = kwargs.pop("code", f"SRC-{unique}")
        vals = {
            "name": f"Test Source {unique}",
            "code": code,
        }
        vals.update(kwargs)
        return self.SourceType.create(vals)

    # ========================================================================
    # CREATION TESTS
    # ========================================================================

    def test_create_basic(self):
        """Test basic record creation"""
        record = self._create_type()
        self.assertTrue(record.exists())
        self.assertTrue(record.name)
        self.assertTrue(record.code)

    def test_constraint_name_required(self):
        """Test name is required"""
        raised = False
        try:
            self.SourceType.create({"code": "NO-NAME"})
        except (ValidationError, IntegrityError):
            raised = True
        self.assertTrue(raised, "Expected exception was not raised")

    def test_constraint_code_required(self):
        """Test code is required"""
        raised = False
        try:
            self.SourceType.create({"name": "No Code Source"})
        except (ValidationError, IntegrityError):
            raised = True
        self.assertTrue(raised, "Expected exception was not raised")

    def test_constraint_code_unique(self):
        """Test code must be unique"""
        self._create_type(code="UNIQUE-SRC")
        raised = False
        try:
            self._create_type(code="UNIQUE-SRC")
        except (ValidationError, IntegrityError):
            raised = True
        self.assertTrue(raised, "Expected exception was not raised")
