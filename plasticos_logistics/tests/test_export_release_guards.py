"""Every new-instruction path reads the one Logistics release guard (S4, RP-03-E016).

The owner hold is a test override of ``plasticos.load._physical_release_errors``:
the base addon never imports the downstream Export addon. Real booking rollover
is tested in ``plasticos_export``. Each path that issues a NEW physical
instruction is refused under the hold; recording what already happened is not;
a domestic load with no hold releases on every path (BRS-EXP-10-R004/R008, V04/V06).
"""

from datetime import timedelta
from unittest.mock import patch

from odoo import fields
from odoo.addons.plasticos_logistics.models.load import PlasticosLoad
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged

HOLD = "Export booking rolled: new carrier instructions are withheld."


def _owner_hold(self, operation_kind):
    return [HOLD]


@tagged("post_install", "-at_install")
class TestExportReleaseGuards(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.supplier = cls.env["res.partner"].create(
            {"name": "S4 Guard Mill", "is_company": True, "supplier_rank": 1, "street": "5 Mill Rd"}
        )
        cls.terminal = cls.env["res.partner"].create(
            {"name": "S4 Guard Ramp", "is_company": True, "street": "6 Ramp Way", "city": "Dallas"}
        )
        cls.carrier = cls.env["res.partner"].create(
            {"name": "S4 Guard Carrier", "is_company": True, "email": "guard@s4-carrier.example"}
        )

    def _load(self):
        load = self.env["plasticos.load"].create(
            {
                "company_id": self.company.id,
                "pickup_partner_id": self.supplier.id,
                "delivery_partner_id": self.terminal.id,
                "reference_weight": 42000,
                "carrier_id": self.carrier.id,
                "rate_currency_id": self.company.currency_id.id,
            }
        )
        load._transition("awaiting_ready")
        load.action_confirm_ready()
        load.action_confirm_rate(950.0)
        return load

    def _scheduled(self):
        load = self._load()
        now = fields.Datetime.now()
        load.action_schedule(now, now)
        return load

    def _bulk_wizard(self, load, state):
        return (
            self.env["plasticos.load.bulk.update.wizard"]
            .with_context(active_ids=load.ids)
            .create({"new_state": state, "reason": "S4 guard witness"})
        )

    def _composer(self, action):
        return self.env["mail.compose.message"].with_context(**action["context"]).create({})

    def _carrier_mail_count(self, load):
        return self.env["mail.mail"].search_count([("model", "=", "plasticos.load"), ("res_id", "=", load.id)])

    def test_hold_refuses_every_new_instruction_path(self):
        load = self._scheduled()
        dispatch = self.env["plasticos.dispatch"].create({"load_id": load.id})
        packet = self._composer(load.action_send_dispatch_packet())
        document = self._composer(load.action_send_delivery_order())
        mails_before = self._carrier_mail_count(load)
        with patch.object(PlasticosLoad, "_physical_release_errors", _owner_hold):
            paths = {
                "standalone dispatch": load.action_dispatch,
                "load._transition": lambda: load._transition("dispatched"),
                "dispatch record": lambda: dispatch.action_transition("dispatched"),
                "packet composer open": load.action_send_dispatch_packet,
                "packet composer send": packet.action_send_mail,
                "document composer send": document.action_send_mail,
                "direct packet send": load.action_send_dispatch_direct,
            }
            for label, attempt in paths.items():
                with self.subTest(path=label), self.assertRaises(UserError), self.env.cr.savepoint():
                    attempt()
            verdict = self.env["plasticos.load"].assert_can_release_physical_operation(load.id, "dispatch_packet")
            self.assertEqual(verdict["status"], "blocked")
            self.assertIn(HOLD, verdict["reason"])
            # The bulk wizard reports the refusal per load instead of moving it.
            with self.env.cr.savepoint():
                try:
                    self._bulk_wizard(load, "dispatched").action_update_status()
                except UserError:
                    pass
        self.assertEqual(load.state, "scheduled")
        self.assertEqual(dispatch.state, "quoted")
        self.assertEqual(self._carrier_mail_count(load), mails_before, "no carrier mail left under the hold")

    def test_hold_refuses_scheduling_a_new_instruction(self):
        load = self._load()
        now = fields.Datetime.now()
        with patch.object(PlasticosLoad, "_physical_release_errors", _owner_hold):
            with self.assertRaises(UserError), self.env.cr.savepoint():
                load.action_schedule(now, now)
        self.assertEqual(load.state, "rate_confirmed")

    def test_hold_never_blocks_reporting_an_actual_event(self):
        load = self._scheduled()
        load.action_dispatch()
        evidence = self.env["ir.attachment"].create(
            {"name": "signed-bol.pdf", "raw": b"%PDF-1.4 s4", "res_model": "plasticos.load", "res_id": load.id}
        )
        picked_at = fields.Datetime.now() - timedelta(hours=1)
        with patch.object(PlasticosLoad, "_physical_release_errors", _owner_hold):
            result = load.action_record_actual_event("pickup", picked_at, evidence)
            load._transition("picked_up")
        self.assertEqual(result["status"], "applied")
        self.assertEqual(load.state, "picked_up")

    def test_domestic_control_releases_on_every_path(self):
        load = self._scheduled()
        verdict = self.env["plasticos.load"].assert_can_release_physical_operation(load.id, "dispatch_packet")
        self.assertEqual(verdict, {"status": "applied", "record_id": load.id})
        self._composer(load.action_send_delivery_order()).action_send_mail()
        load.action_dispatch()
        self.assertEqual(load.state, "dispatched")
