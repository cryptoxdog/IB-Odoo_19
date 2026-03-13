"""
Test document tags.

Tests unique code constraint.
"""

try:
    from psycopg.errors import IntegrityError
except ImportError:
    from psycopg2 import IntegrityError

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestDocumentTags(PlasticosTestCase):
    """Test plasticos.document.tag model."""

    def test_create_tag(self):
        """Document tag can be created."""
        tag = self.env["plasticos.document.tag"].create(
            {
                "name": "Certificate of Insurance",
                "code": "COI",
            }
        )
        self.assertTrue(tag.id)

    def test_unique_code_constraint(self):
        """Tag code must be unique."""
        self.env["plasticos.document.tag"].create(
            {
                "name": "Certificate of Insurance",
                "code": "COI",
            }
        )

        with self.assertRaises(IntegrityError):
            self.env.cr.execute(
                """
                INSERT INTO plasticos_document_tag (name, code)
                VALUES (%s, %s)
            """,
                ("Another COI", "COI"),
            )

    def test_different_codes_allowed(self):
        """Different codes should be allowed."""
        tag1 = self.env["plasticos.document.tag"].create(
            {
                "name": "Certificate of Insurance",
                "code": "COI",
            }
        )
        tag2 = self.env["plasticos.document.tag"].create(
            {
                "name": "Bill of Lading",
                "code": "BOL",
            }
        )
        self.assertNotEqual(tag1.id, tag2.id)
