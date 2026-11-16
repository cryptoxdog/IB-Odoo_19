"""Set an empty intake contact from the location's reached person.

Intakes that already have a contact are skipped. The existing preferred-contact
sync may store that same person on the facility.
"""

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {"mail_notrack": True, "tracking_disable": True})
    intakes = env["plasticos.intake"].search(
        [
            ("contact_id", "=", False),
            "|",
            ("facility_id", "!=", False),
            ("partner_id", "!=", False),
        ]
    )
    filled = 0
    for intake in intakes:
        source = intake.facility_id or intake.partner_id
        person = source._plasticos_reach_person()
        if not person:
            continue
        intake.write({"contact_id": person.id})
        filled += 1
    _logger.info("Set the reached contact on %s intake(s).", filled)
