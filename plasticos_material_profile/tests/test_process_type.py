import uuid

try:
    from psycopg.errors import IntegrityError
except ImportError:
    from psycopg2 import IntegrityError

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.exceptions import ValidationError
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestPlasticosProcessType(PlasticosTestCase):
    """Test suite for plasticos.process.type"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.ProcessType = cls.env["plasticos.process.type"]

    def _create_type(self, **kwargs):
        """Helper to create plasticos.process.type with unique defaults"""
        unique = uuid.uuid4().hex[:6].upper()
        code = kwargs.pop("code", f"PROC-{unique}")
        vals = {
            "name": f"Test Process {unique}",
            "code": code,
        }
        vals.update(kwargs)
        return self.ProcessType.create(vals)

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
                self.ProcessType.create({"code": "NO-NAME"})

    def test_constraint_code_required(self):
        """Test code is required"""
        with self.assertRaises((ValidationError, IntegrityError)):
            with self.env.cr.savepoint():
                self.ProcessType.create({"name": "No Code Process"})

    def test_constraint_code_unique(self):
        """Test code must be unique"""
        self._create_type(code="UNIQUE-PROC")
        with self.assertRaises((ValidationError, IntegrityError)):
            with self.env.cr.savepoint():
                self._create_type(code="UNIQUE-PROC")
