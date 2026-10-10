"""Refuse the active-rule index when a representative already has two active rules."""


def migrate(cr, version):
    """Census active plasticos.commission.rule rows before the partial unique index.

    A fresh install has no prior rows. An upgrade with duplicates must stop.
    This script does not deactivate or delete a rule.
    """
    if not version:
        return
    cr.execute("SELECT to_regclass('plasticos_commission_rule')")
    if cr.fetchone()[0] is None:
        return
    cr.execute(
        """
        SELECT sales_rep_id, array_agg(id ORDER BY id)
          FROM plasticos_commission_rule
         WHERE active IS TRUE
         GROUP BY sales_rep_id
        HAVING count(*) > 1
        """
    )
    conflicts = cr.fetchall()
    if conflicts:
        raise RuntimeError(
            "More than one active commission rule exists for a sales representative. "
            f"Resolve these (sales_rep_id, rule ids) before upgrading: {conflicts}"
        )
