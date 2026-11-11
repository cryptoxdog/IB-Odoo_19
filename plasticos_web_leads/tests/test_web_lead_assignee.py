"""Queue assignee is empty at admission, copied once onto a new intake, and locked after that."""

from __future__ import annotations

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "plasticos", "web_lead", "assignee")
class TestWebLeadAssignee(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.WebLead = cls.env["plasticos.web.lead"]
        cls.config = cls.env["plasticos.web.lead.config"].sudo().get_config()
        cls.rep = cls.env.ref("base.user_admin")

    def _lead(self, lead_id, **extra):
        values = {
            "lead_id": lead_id,
            "company_name": "Queue Co",
            "decision": "cold",
            "state": "received",
        }
        values.update(extra)
        return self.WebLead.create(values)

    def _intake(self, lead):
        return lead._create_intake({"form": "PALLETS", "polymer": "HDPE", "estimated_lbs": 500}, self.config)

    def test_a_new_lead_and_its_intake_stay_unassigned(self):
        lead = self._lead("ASSIGN-EMPTY")

        self.assertFalse(lead.assigned_user_id)
        self.assertFalse(self._intake(lead).assigned_user_id)

    def test_a_chosen_queue_assignee_is_copied_onto_the_new_intake(self):
        lead = self._lead("ASSIGN-COPY")
        lead.assigned_user_id = self.rep

        self.assertEqual(self._intake(lead).assigned_user_id, self.rep)

    def test_a_processed_lead_rejects_a_queue_assignee_write(self):
        lead = self._lead("ASSIGN-LOCK", state="intake_created")

        with self.assertRaises(UserError):
            lead.write({"assigned_user_id": self.rep.id})
        self.assertFalse(lead.assigned_user_id)
