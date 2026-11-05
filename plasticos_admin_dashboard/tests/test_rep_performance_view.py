"""The rep-performance SQL view is created by the model's init()."""

from odoo.tests import TransactionCase, tagged

_RELATION = "plasticos_rep_performance"
_COLUMNS = (
    "rep_name",
    "deals_closed",
    "revenue_closed",
    "gm_pct",
    "commission",
    "period_sort",
)


@tagged("post_install", "-at_install")
class TestRepPerformanceView(TransactionCase):
    def test_init_creates_view_with_report_columns(self):
        self.env["plasticos.rep.performance"].init()
        self.env.cr.execute(
            """
            SELECT c.relkind
              FROM pg_class c
              JOIN pg_namespace n ON n.oid = c.relnamespace
             WHERE n.nspname = 'public'
               AND c.relname = %s
            """,
            (_RELATION,),
        )
        row = self.env.cr.fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row[0], "v")

        self.env.cr.execute(
            """
            SELECT column_name
              FROM information_schema.columns
             WHERE table_schema = 'public'
               AND table_name = %s
            """,
            (_RELATION,),
        )
        names = {record[0] for record in self.env.cr.fetchall()}
        for column in _COLUMNS:
            self.assertIn(column, names)

        self.env["plasticos.rep.performance"].search([], limit=1)
