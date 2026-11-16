from odoo.exceptions import AccessError, UserError
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "broker_intelligence")
class TestMackSecurity(TransactionCase):
    def test_forged_receipt_create_blocked(self):
        with self.assertRaises(AccessError):
            self.env["plasticos.broker.consultation"].create(
                [
                    {
                        "source_model": "plasticos.intake",
                        "source_id": 1,
                        "source_revision": "fake",
                        "question": "fake",
                        "response_snapshot": {},
                        "actor_id": self.env.user.id,
                        "company_id": self.env.company.id,
                        "request_key": "fake",
                    }
                ]
            )

    def test_wrong_source_model_not_a_broker_chat(self):
        with self.assertRaises(UserError):
            self.env["plasticos.broker.consultation"].action_consult("res.partner", 1, "what?")
