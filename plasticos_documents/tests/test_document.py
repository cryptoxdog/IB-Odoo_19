from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestPlasticosDocument(TransactionCase):
    """Test suite for plasticos.document"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({"name": "Doc Test Partner"})
        cls.attachment = cls.env["ir.attachment"].create(
            {"name": "test_doc.pdf", "type": "binary", "datas": "dGVzdA=="}
        )
        cls.tag = cls.env["plasticos.document.tag"].create({"name": "Doc Test Tag", "code": "DOC_TEST_TAG"})
        cls._doc_counter = 0

    def _create_document(self, **kwargs):
        """Helper to create plasticos.document with defaults"""
        self.__class__._doc_counter += 1
        vals = {
            "name": kwargs.pop("name", f"Test Doc {self.__class__._doc_counter}"),
            "res_model": "res.partner",
            "res_id": self.partner.id,
            "attachment_id": self.attachment.id,
            "tag_id": self.tag.id,
        }
        vals.update(kwargs)
        return self.env["plasticos.document"].create(vals)

    # ========================================================================
    # CREATION TESTS
    # ========================================================================

    def test_create_basic(self):
        """Test basic record creation"""
        record = self._create_document()
        self.assertTrue(record.exists())
        self.assertEqual(record.res_model, "res.partner")
        self.assertEqual(record.res_id, self.partner.id)

    def test_action_verify_executes_successfully(self):
        """Test action_verify sets verified=True and records user/time"""
        record = self._create_document()
        self.assertFalse(record.verified)

        record.action_verify()

        self.assertTrue(record.verified)
        self.assertEqual(record.verified_by, self.env.user)
        self.assertTrue(record.verified_at)

    def test_action_override_executes_successfully(self):
        """Test action_override sets override=True"""
        record = self._create_document()
        self.assertFalse(record.override)

        # Grant manager group for override
        manager_group = self.env.ref("plasticos_documents.group_documents_manager")
        self.env.user.groups_id |= manager_group

        record.action_override(reason="Test override reason")

        self.assertTrue(record.override)
        self.assertEqual(record.override_reason, "Test override reason")

    def test_action_supersede_executes_successfully(self):
        """Test action_supersede sets is_current=False and superseded_by"""
        record = self._create_document()
        new_doc = self._create_document(name="New Version", version=2)

        self.assertTrue(record.is_current)

        record.action_supersede(new_doc.id)

        self.assertFalse(record.is_current)
        self.assertEqual(record.superseded_by, new_doc)

    def test_constraint_name_required(self):
        """Test name is required"""
        with self.assertRaises(ValidationError):
            self.env["plasticos.document"].create(
                {
                    "res_model": "res.partner",
                    "res_id": self.partner.id,
                    "attachment_id": self.attachment.id,
                    "tag_id": self.tag.id,
                }
            )

    def test_constraint_res_model_required(self):
        """Test res_model is required"""
        with self.assertRaises(ValidationError):
            self.env["plasticos.document"].create(
                {
                    "name": "Test Doc",
                    "res_id": self.partner.id,
                    "attachment_id": self.attachment.id,
                    "tag_id": self.tag.id,
                }
            )

    def test_constraint_res_id_required(self):
        """Test res_id is required"""
        with self.assertRaises(ValidationError):
            self.env["plasticos.document"].create(
                {
                    "name": "Test Doc",
                    "res_model": "res.partner",
                    "attachment_id": self.attachment.id,
                    "tag_id": self.tag.id,
                }
            )

    def test_constraint_attachment_id_required(self):
        """Test attachment_id is required"""
        with self.assertRaises(ValidationError):
            self.env["plasticos.document"].create(
                {
                    "name": "Test Doc",
                    "res_model": "res.partner",
                    "res_id": self.partner.id,
                    "tag_id": self.tag.id,
                }
            )

    def test_constraint_tag_id_required(self):
        """Test tag_id is required"""
        with self.assertRaises(ValidationError):
            self.env["plasticos.document"].create(
                {
                    "name": "Test Doc",
                    "res_model": "res.partner",
                    "res_id": self.partner.id,
                    "attachment_id": self.attachment.id,
                }
            )
