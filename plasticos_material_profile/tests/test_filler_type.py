import uuid

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestPlasticosFillerType(PlasticosTestCase):
    """Test suite for plasticos.filler.type"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.FillerType = cls.env["plasticos.filler.type"]

    def _create_type(self, **kwargs):
        """Helper to create plasticos.filler.type with unique defaults"""
        unique = uuid.uuid4().hex[:6].upper()
        code = kwargs.pop("code", f"FILLER-{unique}")
        vals = {
            "name": f"Test Filler {unique}",
            "code": code,
        }
        vals.update(kwargs)
        return self.FillerType.create(vals)

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
        with self.assertRaises(Exception):
            with self.env.cr.savepoint():
                self.FillerType.create({"code": "NO-NAME"})

    def test_constraint_code_required(self):
        """Test code is required"""
        with self.assertRaises(Exception):
            with self.env.cr.savepoint():
                self.FillerType.create({"name": "No Code Filler"})

    def test_constraint_code_unique(self):
        """Test code must be unique"""
        self._create_type(code="UNIQUE-FILLER")
        with self.assertRaises(Exception):
            with self.env.cr.savepoint():
                self._create_type(code="UNIQUE-FILLER")
