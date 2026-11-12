"""account.move is never SQL-deleted through its transaction or penalty-rule link (F-05)."""

import importlib.util

from psycopg2 import IntegrityError

from odoo.modules.module import get_module_path
from odoo.tests import TransactionCase, tagged
from odoo.tools import mute_logger

ACCOUNT_MOVE = "account.move"
LINKS = {"transaction_id": "plasticos_transaction", "penalty_rule_id": "plasticos_penalty_rule"}


def _migration():
    path = get_module_path("plasticos_automation") + "/migrations/19.0.2.1.10/pre-migrate.py"
    spec = importlib.util.spec_from_file_location("plasticos_automation_fk_1902110", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@tagged("post_install", "-at_install", "plasticos", "automation")
class TestAccountMoveFkOndelete(TransactionCase):
    def _delete_rules(self, column):
        self.env.cr.execute(
            """
            SELECT con.confdeltype
              FROM pg_constraint con
              JOIN pg_class rel ON rel.oid = con.conrelid
              JOIN pg_attribute att ON att.attrelid = con.conrelid AND att.attnum = ANY(con.conkey)
             WHERE con.contype = 'f' AND rel.relname = 'account_move' AND att.attname = %s
            """,
            [column],
        )
        return [row[0] for row in self.env.cr.fetchall()]

    def _force_cascade(self, column):
        """Rebuild the pre-fix schema: the same key, cascading."""
        self.env.cr.execute(
            f"ALTER TABLE account_move DROP CONSTRAINT IF EXISTS account_move_{column}_fkey, "  # noqa: S608
            f"ADD CONSTRAINT account_move_{column}_fkey FOREIGN KEY ({column}) "
            f"REFERENCES {LINKS[column]}(id) ON DELETE CASCADE"
        )

    def test_fields_and_live_foreign_keys_do_not_cascade(self):
        for column in LINKS:
            self.assertEqual(self.env[ACCOUNT_MOVE]._fields[column].ondelete, "restrict", column)
            rules = self._delete_rules(column)
            self.assertTrue(rules, f"account_move.{column} has no foreign key")
            self.assertNotIn("c", rules, f"account_move.{column} still cascades")

    def test_deleting_an_applied_penalty_rule_is_refused_and_keeps_the_invoice(self):
        rule = self.env["plasticos.penalty.rule"].create({"name": "FK ondelete rule"})
        partner = self.env["res.partner"].create({"name": "FK Restrict Buyer", "is_company": True})
        move = self.env[ACCOUNT_MOVE].create(
            {"move_type": "out_invoice", "partner_id": partner.id, "penalty_rule_id": rule.id}
        )
        self.env.flush_all()
        with self.assertRaises(IntegrityError), mute_logger("odoo.sql_db"), self.env.cr.savepoint():
            self.env.cr.execute("DELETE FROM plasticos_penalty_rule WHERE id = %s", [rule.id])
        self.assertTrue(move.exists(), "the invoice must survive a refused rule delete")
        self.assertTrue(rule.exists())

    def test_cascade_schema_deletes_the_invoice_and_migration_stops_it(self):
        """Falsifying: under the old key the invoice vanishes; after the migration it cannot."""
        rule = self.env["plasticos.penalty.rule"].create({"name": "FK ondelete rule"})
        partner = self.env["res.partner"].create({"name": "FK Cascade Buyer", "is_company": True})
        move = self.env[ACCOUNT_MOVE].create(
            {"move_type": "out_invoice", "partner_id": partner.id, "penalty_rule_id": rule.id}
        )
        self.env.flush_all()
        for column in LINKS:
            self._force_cascade(column)
        self.assertEqual(self._delete_rules("penalty_rule_id"), ["c"])
        with self.env.cr.savepoint() as savepoint:
            self.env.cr.execute("DELETE FROM plasticos_penalty_rule WHERE id = %s", [rule.id])
            self.env.cr.execute("SELECT 1 FROM account_move WHERE id = %s", [move.id])
            self.assertFalse(self.env.cr.fetchone(), "the old cascading key deleted the invoice")
            savepoint.rollback()

        _migration().migrate(self.env.cr, "19.0.2.1.9")

        for column in LINKS:
            self.assertEqual(self._delete_rules(column), ["r"], column)
        with self.assertRaises(IntegrityError), mute_logger("odoo.sql_db"), self.env.cr.savepoint():
            self.env.cr.execute("DELETE FROM plasticos_penalty_rule WHERE id = %s", [rule.id])
        self.env.cr.execute("SELECT 1 FROM account_move WHERE id = %s", [move.id])
        self.assertTrue(self.env.cr.fetchone())

    def test_migration_is_idempotent(self):
        migration = _migration()
        migration.migrate(self.env.cr, "19.0.2.1.9")
        migration.migrate(self.env.cr, "19.0.2.1.9")
        for column in LINKS:
            self.assertEqual(self._delete_rules(column), ["r"], column)
