"""Adopt existing PO / CARRIER_CERT legacy tags before the DEC-014 seed loads (TASK-069).

``plasticos.document.tag`` codes are unique. A database that already holds one of
these codes would refuse the new seed record; this binds the existing row to the
new xmlid instead. A bound xmlid is left alone, so a rerun changes nothing
(POS-INV-19).
"""

import logging

_logger = logging.getLogger(__name__)

MODULE = "plasticos_documents"
SEED = (("tag_purchase_order", "PO"), ("tag_carrier_certification", "CARRIER_CERT"))


def migrate(cr, version):
    if not version:
        return
    adopted = 0
    for xmlid, code in SEED:
        cr.execute("SELECT 1 FROM ir_model_data WHERE module = %s AND name = %s", (MODULE, xmlid))
        if cr.fetchone():
            continue
        cr.execute("SELECT id FROM plasticos_document_tag WHERE code = %s ORDER BY id LIMIT 1", (code,))
        row = cr.fetchone()
        if not row:
            continue
        cr.execute(
            """
            INSERT INTO ir_model_data (module, name, model, res_id, noupdate)
            VALUES (%s, %s, 'plasticos.document.tag', %s, false)
            """,
            (MODULE, xmlid, row[0]),
        )
        adopted += 1
    _logger.info("plasticos_documents 19.0.2.1.25: adopted %d existing legacy tag(s) for the DEC-014 seed", adopted)
