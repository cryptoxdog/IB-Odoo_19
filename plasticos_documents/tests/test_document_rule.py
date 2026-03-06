from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestPlasticosDocumentRule(TransactionCase):
    """Test suite for plasticos.document.rule"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tag = cls.env["plasticos.document.tag"].create({"name": "Rule Test Tag", "code": "RULE_TEST_TAG"})
        cls._rule_counter = 0

    def _create_rule(self, **kwargs):
        """Helper to create plasticos.document.rule with defaults"""
        self.__class__._rule_counter += 1
        vals = {
            "name": kwargs.pop("name", f"Test Rule {self.__class__._rule_counter}"),
            "tag_id": self.tag.id,
            "res_model": "plasticos.transaction",
        }
        vals.update(kwargs)
        return self.env["plasticos.document.rule"].create(vals)

    # ========================================================================
    # CREATION TESTS
    # ========================================================================

    def test_create_basic(self):
        """Test basic record creation"""
        record = self._create_rule()

        self.assertTrue(record.exists())
        # TODO: Add specific assertions

    def test_constraint_name_required(self):
        """Test name is required"""
        with self.assertRaises(ValidationError):
            self.env["plasticos.document.rule"].create(
                {
                    "tag_id": self.tag.id,
                    "res_model": "plasticos.transaction",
                }
            )

    def test_constraint_tag_id_required(self):
        """Test tag_id is required"""
        with self.assertRaises(ValidationError):
            self.env["plasticos.document.rule"].create(
                {
                    "name": "Test Rule No Tag",
                    "res_model": "plasticos.transaction",
                }
            )

    def test_constraint_res_model_required(self):
        """Test res_model is required"""
        with self.assertRaises(ValidationError):
            self.env["plasticos.document.rule"].create(
                {
                    "name": "Test Rule No Model",
                    "tag_id": self.tag.id,
                }
            )
