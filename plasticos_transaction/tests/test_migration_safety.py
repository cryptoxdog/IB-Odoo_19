from odoo.addons.plasticos_base.tests.common import PlasticosTestCase


class TestMigrationSafety(PlasticosTestCase):
    def test_no_duplicate_invoice_links(self):
        self.env.cr.execute("""
            SELECT customer_invoice_id
            FROM plasticos_transaction
            WHERE customer_invoice_id IS NOT NULL
            GROUP BY customer_invoice_id
            HAVING COUNT(*) > 1;
        """)
        duplicates = self.env.cr.fetchall()
        self.assertFalse(duplicates, "Duplicate customer_invoice_id links must not exist.")
