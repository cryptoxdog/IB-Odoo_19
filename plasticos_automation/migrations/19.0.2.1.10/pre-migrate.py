"""Replace the ON DELETE CASCADE foreign keys on account.move (F-05).

``account_move.transaction_id`` and ``account_move.penalty_rule_id`` were
declared ``ondelete="cascade"``: deleting a transaction or a penalty rule made
PostgreSQL delete the invoices that named it, below the ORM and its unlink
guards. Both fields are now ``ondelete="restrict"``.

The ORM would re-create the constraints while loading the module; this
migration does it first and fails the upgrade when a cascading key is still
present afterwards, so the outcome never depends on that reconciliation.
No row is changed: an existing valid foreign key stays valid under RESTRICT.
"""

import logging

from psycopg2 import sql

_logger = logging.getLogger(__name__)

TABLE = "account_move"
# column -> referenced table
FOREIGN_KEYS = {
    "transaction_id": "plasticos_transaction",
    "penalty_rule_id": "plasticos_penalty_rule",
}

_FIND = """
    SELECT con.conname, con.confdeltype
      FROM pg_constraint con
      JOIN pg_class rel ON rel.oid = con.conrelid
      JOIN pg_namespace ns ON ns.oid = rel.relnamespace
      JOIN pg_attribute att ON att.attrelid = con.conrelid AND att.attnum = ANY(con.conkey)
     WHERE con.contype = 'f'
       AND ns.nspname = current_schema()
       AND rel.relname = %s
       AND att.attname = %s
       AND array_length(con.conkey, 1) = 1
"""


def _foreign_keys(cr, column):
    cr.execute(_FIND, [TABLE, column])
    return cr.fetchall()


def _column_exists(cr, column):
    cr.execute(
        """
        SELECT 1 FROM information_schema.columns
         WHERE table_schema = current_schema() AND table_name = %s AND column_name = %s
        """,
        [TABLE, column],
    )
    return bool(cr.fetchone())


def migrate(cr, version):
    for column, target in FOREIGN_KEYS.items():
        if not _column_exists(cr, column):
            _logger.info("plasticos_automation 19.0.2.1.10: %s.%s absent; the ORM creates it", TABLE, column)
            continue
        replaced = 0
        for name, delete_rule in _foreign_keys(cr, column):
            if delete_rule != "c":
                continue
            cr.execute(
                sql.SQL(
                    "ALTER TABLE {table} DROP CONSTRAINT {name}, "
                    "ADD CONSTRAINT {name} FOREIGN KEY ({column}) REFERENCES {target}(id) ON DELETE RESTRICT"
                ).format(
                    table=sql.Identifier(TABLE),
                    name=sql.Identifier(name),
                    column=sql.Identifier(column),
                    target=sql.Identifier(target),
                )
            )
            replaced += 1
        remaining = [name for name, delete_rule in _foreign_keys(cr, column) if delete_rule == "c"]
        if remaining:
            raise RuntimeError(f"{TABLE}.{column} still cascades through {remaining}; refusing to continue the upgrade")
        _logger.info(
            "plasticos_automation 19.0.2.1.10: %s.%s cascading foreign keys replaced by RESTRICT: %s",
            TABLE,
            column,
            replaced,
        )
