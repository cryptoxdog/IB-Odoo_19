import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)


class ResPartnerPrivate(models.Model):
    """Extend res.partner with a private-contact flag.

    When ``x_private`` is ``True`` the record is hidden from all users
    except the record owner (``create_uid``) and System Administrators.
    Enforcement is handled via ``ir.rule`` in ``security/record_rules.xml``.
    """

    _inherit = "res.partner"

    x_private = fields.Boolean(
        string="Private Contact",
        default=False,
        help=("When enabled, this contact is only visible to the user who " "created it and to System Administrators."),
    )
