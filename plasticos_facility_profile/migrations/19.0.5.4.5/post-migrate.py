"""Recompute salesperson on partners that already have a parent.

The stored compute now copies the parent salesperson. Existing rows keep the
old value until this recompute. The assignment stays inside that compute.
"""

from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    partners = env["res.partner"].with_context(active_test=False).search([("parent_id", "!=", False)])
    if partners:
        partners._compute_user_id()
    env.flush_all()
