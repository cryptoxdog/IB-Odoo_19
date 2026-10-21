"""Attach already-imported call history to the ERP person that owns it.

Rows written before partner_id existed are still keyed by the VanillaSoft
contact id. The external ref already maps that id to one res.partner. This
fills partner_id from that ref. It does not create partners, leads, or copies
of the calls.
"""


def migrate(cr, version):
    if not version:
        return
    cr.execute(
        """
        UPDATE plasticos_crm_call_event AS call
           SET partner_id = ref.res_id
          FROM plasticos_crm_external_ref AS ref
         WHERE call.partner_id IS NULL
           AND ref.res_model = %s
           AND ref.provider = call.provider
           AND ref.external_id = call.contact_external_id
           AND ref.res_id IS NOT NULL
        """,
        ("res.partner",),
    )
    cr.execute(
        """
        UPDATE plasticos_crm_external_table_row AS row
           SET partner_id = ref.res_id
          FROM plasticos_crm_external_ref AS ref
         WHERE row.partner_id IS NULL
           AND ref.res_model = %s
           AND ref.provider = row.provider
           AND ref.external_id = row.contact_external_id
           AND ref.res_id IS NOT NULL
        """,
        ("res.partner",),
    )
