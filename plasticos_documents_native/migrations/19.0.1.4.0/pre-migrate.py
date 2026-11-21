"""Adopt existing same-name tags before the DEC-014 seed loads (TASK-069).

``documents.tag`` names are unique. A database where someone already created, for
example, a "Packing List" tag by hand would refuse the new seed record and stop the
upgrade. This binds each such tag to its new xmlid instead, so the seed updates it
in place and no tag, document link or name is duplicated. A tag that already has
the xmlid is left alone, so a second run changes nothing (POS-INV-19).
"""

import logging

_logger = logging.getLogger(__name__)

MODULE = "plasticos_documents_native"
SEED = (
    ("tag_purchase_order", "Purchase Order"),
    ("tag_packing_list", "Packing List"),
    ("tag_receiving_report", "Receiving Report"),
    ("tag_certified_scale_ticket", "Certified Scale Ticket (CST)"),
    ("tag_delivery_order_confirmation", "Delivery Order Confirmation"),
    ("tag_carrier_certification", "Carrier Certification"),
    ("tag_customer_invoice", "Customer Invoice"),
    ("tag_financial_document", "Financial Document"),
    ("tag_carrier_invoice", "Carrier Invoice"),
    ("tag_credit_note", "Credit Note"),
    ("tag_debit_note", "Debit Note"),
    ("tag_statement", "Statement"),
    ("tag_payment_confirmation", "Payment Confirmation"),
    ("tag_delivery_receipt", "Delivery Receipt"),
    ("tag_order_confirmation", "Order Confirmation"),
    ("tag_material_certification", "Material Certification"),
    ("tag_technical_specification", "Technical Specification"),
    ("tag_unloading_pic", "Unloading Pic"),
    ("tag_delivery_photo", "Delivery Photo"),
    ("tag_damage_photo", "Damage Photo"),
    ("tag_evidence_gap", "Evidence Gap"),
    ("tag_duplicate_candidate", "Duplicate Candidate"),
    ("tag_includes_supporting_evidence", "Includes Supporting Evidence"),
)


def migrate(cr, version):
    if not version:
        return
    cr.execute("SELECT to_regclass('documents_tag')")
    if not cr.fetchone()[0]:
        return
    adopted = 0
    for xmlid, name in SEED:
        cr.execute(
            "SELECT 1 FROM ir_model_data WHERE module = %s AND name = %s",
            (MODULE, xmlid),
        )
        if cr.fetchone():
            continue
        cr.execute("SELECT id FROM documents_tag WHERE name->>'en_US' = %s ORDER BY id LIMIT 1", (name,))
        row = cr.fetchone()
        if not row:
            continue
        cr.execute(
            """
            INSERT INTO ir_model_data (module, name, model, res_id, noupdate)
            VALUES (%s, %s, 'documents.tag', %s, false)
            """,
            (MODULE, xmlid, row[0]),
        )
        adopted += 1
    _logger.info("plasticos_documents_native 19.0.1.4.0: adopted %d existing tag(s) for the DEC-014 seed", adopted)
