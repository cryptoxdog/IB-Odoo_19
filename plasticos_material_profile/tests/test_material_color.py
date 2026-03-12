import uuid

# Odoo 19 may use psycopg3; handle both
try:
    from psycopg2 import IntegrityError
except ImportError:
    from psycopg.errors import IntegrityError

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.exceptions import ValidationError
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestPlasticosMaterialColor(PlasticosTestCase):
    """Test suite for plasticos.material.color"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.MaterialColor = cls.env["plasticos.material.color"]

    def _create_color(self, **kwargs):
        """Helper to create plasticos.material.color with unique defaults"""
        unique = uuid.uuid4().hex[:6].upper()
        code = kwargs.pop("code", f"COLOR-{unique}")
        vals = {
            "name": f"Test Color {unique}",
            "code": code,
        }
        vals.update(kwargs)
        return self.MaterialColor.create(vals)

    # ========================================================================
    # CREATION TESTS
    # ========================================================================

    def test_create_basic(self):
        """Test basic record creation"""
        record = self._create_color()
        self.assertTrue(record.exists())
        self.assertTrue(record.name)
        self.assertTrue(record.code)

    def test_constraint_name_required(self):
        """Test name is required"""
        with self.assertRaises((ValidationError, IntegrityError)):
            with self.env.cr.savepoint():
                self.MaterialColor.create({"code": "NO-NAME"})

    def test_constraint_code_required(self):
        """Test code is required"""
        with self.assertRaises((ValidationError, IntegrityError)):
            with self.env.cr.savepoint():
                self.MaterialColor.create({"name": "No Code Color"})

    def test_constraint_code_unique(self):
        """Test code must be unique"""
        self._create_color(code="UNIQUE-COLOR")
        with self.assertRaises((ValidationError, IntegrityError)):
            with self.env.cr.savepoint():
                self._create_color(code="UNIQUE-COLOR")
