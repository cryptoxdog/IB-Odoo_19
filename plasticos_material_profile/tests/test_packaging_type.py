import uuid

from psycopg.errors import IntegrityError

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.exceptions import ValidationError
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestPlasticosPackagingType(PlasticosTestCase):
    """Test suite for plasticos.packaging.type"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.PackagingType = cls.env["plasticos.packaging.type"]

    def _create_type(self, **kwargs):
        """Helper to create plasticos.packaging.type with unique defaults"""
        unique = uuid.uuid4().hex[:6].upper()
        code = kwargs.pop("code", f"PKG-{unique}")
        vals = {
            "name": f"Test Packaging {unique}",
            "code": code,
        }
        vals.update(kwargs)
        return self.PackagingType.create(vals)

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
        with self.assertRaises((ValidationError, IntegrityError)):
            with self.env.cr.savepoint():
                self.PackagingType.create({"code": "NO-NAME"})

    def test_constraint_code_required(self):
        """Test code is required"""
        with self.assertRaises((ValidationError, IntegrityError)):
            with self.env.cr.savepoint():
                self.PackagingType.create({"name": "No Code Packaging"})

    def test_constraint_code_unique(self):
        """Test code must be unique"""
        self._create_type(code="UNIQUE-PKG")
        with self.assertRaises((ValidationError, IntegrityError)):
            with self.env.cr.savepoint():
                self._create_type(code="UNIQUE-PKG")
