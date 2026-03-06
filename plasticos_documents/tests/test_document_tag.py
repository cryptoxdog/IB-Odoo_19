from odoo.addons.plasticos_base.tests.common import PlasticosTestCase
from odoo.exceptions import ValidationError
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestPlasticosDocumentTag(PlasticosTestCase):
    """Test suite for plasticos.document.tag"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._tag_counter = 0

    def _create_tag(self, **kwargs):
        """Helper to create plasticos.document.tag with defaults"""
        self.__class__._tag_counter += 1
        vals = {
            "name": kwargs.pop("name", f"Test Tag {self.__class__._tag_counter}"),
            "code": kwargs.pop("code", f"TEST_TAG_{self.__class__._tag_counter}"),
        }
        vals.update(kwargs)
        return self.env["plasticos.document.tag"].create(vals)

    # ========================================================================
    # CREATION TESTS
    # ========================================================================

    def test_create_basic(self):
        """Test basic record creation"""
        record = self._create_tag()
        self.assertTrue(record.exists())
        self.assertTrue(record.active)

    def test_constraint_name_required(self):
        """Test name is required"""
        with self.assertRaises(ValidationError):
            self.env["plasticos.document.tag"].create(
                {
                    "code": "NO_NAME_TAG",
                }
            )

    def test_constraint_code_required(self):
        """Test code is required"""
        with self.assertRaises(ValidationError):
            self.env["plasticos.document.tag"].create(
                {
                    "name": "No Code Tag",
                }
            )
