from psycopg2 import IntegrityError

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.exceptions import ValidationError
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestPlasticosPolymer(PlasticosTestCase):
    """Test suite for plasticos.polymer"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Polymer = cls.env["plasticos.polymer"]

    def _create_polymer(self, **kwargs):
        """Helper to create plasticos.polymer with defaults"""
        import uuid

        code = kwargs.pop("code", f"TEST-{uuid.uuid4().hex[:6].upper()}")
        vals = {
            "name": code,
            "code": code,
        }
        vals.update(kwargs)
        return self.Polymer.create(vals)

    # ========================================================================
    # CREATION TESTS
    # ========================================================================

    def test_create_basic(self):
        """Test basic record creation"""
        record = self._create_polymer()
        self.assertTrue(record.exists())
        self.assertTrue(record.name)
        self.assertTrue(record.code)

    def test_create_with_all_fields(self):
        """Test creation with all optional fields"""
        record = self._create_polymer(
            full_name="High-Density Polyethylene",
            resin_id_code="2",
            category="commodity",
            description="Test description",
        )
        self.assertEqual(record.full_name, "High-Density Polyethylene")
        self.assertEqual(record.resin_id_code, "2")
        self.assertEqual(record.category, "commodity")
        self.assertEqual(record.description, "Test description")

    # ========================================================================
    # CONSTRAINT TESTS
    # ========================================================================

    def test_constraint_name_required(self):
        """Test name is required"""
        raised = False
        try:
            self.Polymer.create({"code": "NONAME"})
        except (ValidationError, IntegrityError):
            raised = True
        self.assertTrue(raised, "Expected exception was not raised")

    def test_constraint_code_required(self):
        """Test code is required"""
        raised = False
        try:
            self.Polymer.create({"name": "No Code Polymer"})
        except (ValidationError, IntegrityError):
            raised = True
        self.assertTrue(raised, "Expected exception was not raised")

    def test_constraint_code_unique(self):
        """Test code must be unique"""
        self._create_polymer(code="UNIQUE-TEST")
        raised = False
        try:
            self._create_polymer(code="UNIQUE-TEST")
        except (ValidationError, IntegrityError):
            raised = True
        self.assertTrue(raised, "Expected exception was not raised")

    # ========================================================================
    # CATEGORY TESTS
    # ========================================================================

    def test_category_default(self):
        """Test default category is commodity"""
        record = self._create_polymer()
        self.assertEqual(record.category, "commodity")

    def test_category_engineering(self):
        """Test engineering category"""
        record = self._create_polymer(category="engineering")
        self.assertEqual(record.category, "engineering")

    def test_category_specialty(self):
        """Test specialty category"""
        record = self._create_polymer(category="specialty")
        self.assertEqual(record.category, "specialty")
