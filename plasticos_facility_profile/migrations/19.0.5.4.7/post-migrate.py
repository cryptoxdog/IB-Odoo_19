"""Recompute vendor payment terms on partners that already have a parent.

The stored compute now copies the parent vendor term, then the grandparent
term when the parent has none. Existing rows keep a blank child term until
this recompute. The assignment stays inside that compute, so an empty
ancestor does not clear a term that is already set.
"""

from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    partners = env["res.partner"].with_context(active_test=False).search([("parent_id", "!=", False)])
    if partners:
        partners._compute_supplier_payment_term_id()
    env.flush_all()
