from odoo import SUPERUSER_ID, api


def migrate(cr, _version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    duplicates = env["plasticos.transaction"].read_group(
        [("customer_invoice_id", "!=", False)],
        ["customer_invoice_id"],
        ["customer_invoice_id"],
    )
    for group in duplicates:
        if group["customer_invoice_id_count"] > 1:
            raise Exception("Duplicate customer_invoice_id links detected. Resolve manually before upgrade.")
