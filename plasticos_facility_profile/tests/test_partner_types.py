"""
Test partner types.

Tests unique code and lead source mapping.
"""

from psycopg.errors import IntegrityError

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestPartnerTypes(PlasticosTestCase):
    """Test plasticos.partner.type model."""

    def test_create_partner_type(self):
        """Partner type can be created."""
        ptype = self.env["plasticos.partner.type"].create(
            {
                "name": "Recycler",
                "code": "REC",
            }
        )
        self.assertTrue(ptype.id)

    def test_unique_code_constraint(self):
        """Partner type code must be unique."""
        self.env["plasticos.partner.type"].create(
            {
                "name": "Recycler",
                "code": "REC",
            }
        )

        with self.assertRaises(IntegrityError):
            self.env.cr.execute(
                """
                INSERT INTO plasticos_partner_type (name, code)
                VALUES (%s, %s)
            """,
                ("Another Recycler", "REC"),
            )

    def test_different_codes_allowed(self):
        """Different codes should be allowed."""
        pt1 = self.env["plasticos.partner.type"].create(
            {
                "name": "Recycler",
                "code": "REC",
            }
        )
        pt2 = self.env["plasticos.partner.type"].create(
            {
                "name": "Processor",
                "code": "PROC",
            }
        )
        self.assertNotEqual(pt1.id, pt2.id)

    def test_lead_source_mapping(self):
        """Partner type can have lead source mapping."""
        if "utm.source" not in self.env:
            self.skipTest("utm.source not installed")

        utm_source = self.env["utm.source"].create(
            {
                "name": "Recycler Network",
            }
        )

        ptype = self.env["plasticos.partner.type"].create(
            {
                "name": "Recycler",
                "code": "REC",
                "lead_source_id": utm_source.id,
            }
        )

        self.assertEqual(ptype.lead_source_id, utm_source)
