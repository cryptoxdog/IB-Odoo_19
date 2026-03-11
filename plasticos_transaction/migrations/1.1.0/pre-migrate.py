def migrate(cr, _version):
    # Backfill missing sequence names
    cr.execute("""
        SELECT id FROM plasticos_transaction
        WHERE name = 'New';
    """)
    ids = [row[0] for row in cr.fetchall()]

    from odoo import SUPERUSER_ID, api

    env = api.Environment(cr, SUPERUSER_ID, {})

    for tx_id in ids:
        seq = env["ir.sequence"].next_by_code("plasticos.transaction")
        env["plasticos.transaction"].browse(tx_id).write({"name": seq})

    cr.execute("""
        UPDATE plasticos_transaction
        SET commission_locked = FALSE
        WHERE commission_locked IS NULL;
    """)

    cr.execute("""
        UPDATE plasticos_transaction
        SET commission_locked_amount = commission_amount
        WHERE commission_locked = TRUE
        AND (commission_locked_amount IS NULL OR commission_locked_amount = 0);
    """)
