from odoo.tests.common import TransactionCase, tagged

from ..services.shadow import can_inject, context_from_advice


@tagged("post_install", "-at_install", "broker_intelligence")
class TestBrokerShadowSafety(TransactionCase):
    def test_disabled_does_not_inject(self):
        self.assertFalse(can_inject("off", "shadow"))
        self.assertFalse(can_inject("off", "live"))

    def test_shadow_does_not_activate_in_live(self):
        self.assertTrue(can_inject("shadow_only", "shadow"))
        self.assertFalse(can_inject("shadow_only", "live"))

    def test_advice_is_not_fabricated_seller_evidence(self):
        self.assertEqual(context_from_advice({})["seller_evidence_refs"], [])
