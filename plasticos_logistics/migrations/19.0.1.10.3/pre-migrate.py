"""Refuse the load uniqueness constraint when current data already violates it."""


def migrate(cr, version):
    """Census non-null plasticos.transaction.load_id before UNIQUE(load_id).

    A fresh install has no prior rows. An upgrade with duplicate assignments
    must stop so a human can reconcile them. This script does not pick a winner.
    """
    if not version:
        return
    cr.execute("SELECT to_regclass('plasticos_transaction')")
    if cr.fetchone()[0] is None:
        return
    cr.execute(
        """
        SELECT 1
          FROM information_schema.columns
         WHERE table_name = 'plasticos_transaction'
           AND column_name = 'load_id'
        """
    )
    if cr.fetchone() is None:
        return
    cr.execute(
        """
        SELECT load_id, array_agg(id ORDER BY id)
          FROM plasticos_transaction
         WHERE load_id IS NOT NULL
         GROUP BY load_id
        HAVING count(*) > 1
        """
    )
    conflicts = cr.fetchall()
    if conflicts:
        raise RuntimeError(
            "plasticos.transaction.load_id is not unique. "
            f"Resolve these (load_id, transaction ids) before upgrading: {conflicts}"
        )
