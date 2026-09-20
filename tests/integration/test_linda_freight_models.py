"""Odoo-runtime regression coverage for Linda's local freight persistence boundary."""

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.exceptions import AccessError, UserError
from odoo.tests.common import tagged


@tagged("post_install", "-at_install", "plasticos", "integration", "logistics", "linda")
class TestLindaFreightModels(PlasticosTestCase):
    """Exercise model/ACL/state contracts that pure-Python service tests cannot load."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._skip_if_model_missing(
            "plasticos.intake",
            "plasticos.transaction",
            "plasticos.load",
            "plasticos.freight.quote.request",
            "plasticos.freight.quote.recipient",
            "plasticos.freight.quote",
            "plasticos.freight.estimate",
            "plasticos.freight.event",
            "plasticos.freight.calibration.observation",
            "plasticos.rate.memory",
            "plasticos.rate.memory.reconciliation",
        )
        cls.origin = cls.env["res.partner"].create(
            {
                "name": "Linda Origin",
                "is_company": True,
                "supplier_rank": 1,
                "partner_latitude": 40.7128,
                "partner_longitude": -74.006,
            }
        )
        cls.destination = cls.env["res.partner"].create(
            {
                "name": "Linda Destination",
                "is_company": True,
                "customer_rank": 1,
                "partner_latitude": 41.8781,
                "partner_longitude": -87.6298,
            }
        )
        cls.carrier = cls.env["res.partner"].create({"name": "Linda Carrier", "is_company": True, "supplier_rank": 1})
        cls.currency = cls.env.company.currency_id

    def _new_load(self):
        intake = self.env["plasticos.intake"].create({"partner_id": self.origin.id})
        sale = self.env["sale.order"].create({"partner_id": self.destination.id})
        load = self.env["plasticos.load"].create(
            {
                "sale_order_id": sale.id,
                "pickup_partner_id": self.origin.id,
                "delivery_partner_id": self.destination.id,
                "reference_weight": 40000,
                "rate_currency_id": self.currency.id,
            }
        )
        transaction = self.env["plasticos.transaction"].create(
            {
                "sale_order_id": sale.id,
                "supplier_id": self.origin.id,
                "buyer_id": self.destination.id,
                "intake_id": intake.id,
                "load_id": load.id,
            }
        )
        load.invalidate_recordset()
        self.assertEqual(load.transaction_id, transaction)
        load._transition("awaiting_ready")
        load.action_confirm_ready()
        from odoo.addons.plasticos_logistics.services.freight_context import build_freight_context

        context = build_freight_context(load)
        self.assertTrue(context)
        load._freight_write(
            {
                "freight_context_fingerprint": context.fingerprint,
                "freight_context_version": "freight_context_v3",
                "sal_decision": "miss",
                "sal_miss_reason": "no_prior_movement",
            }
        )
        return load, context

    def _new_request(self):
        load, context = self._new_load()
        request = self.env["plasticos.freight.quote.request"].create({"load_id": load.id})
        self.assertEqual(request.context_fingerprint, context.fingerprint)
        recipient = self.env["plasticos.freight.quote.recipient"].create(
            {
                "company_id": load.company_id.id,
                "request_id": request.id,
                "carrier_id": self.carrier.id,
                "channel": "manual",
                "destination_snapshot": "operator-entered",
                "idempotency_key": f"recipient-{request.id}",
            }
        )
        return load, context, request, recipient

    def test_load_provenance_and_state_bypass_is_rejected(self):
        load, _context = self._new_load()
        with self.assertRaises(UserError):
            load.write({"state": "rate_confirmed"})
        with self.assertRaises(UserError):
            load.write({"freight_context_fingerprint": "bypass"})

    def test_quote_selection_requires_locked_canonical_workflow(self):
        _load, _context, request, recipient = self._new_request()
        quote_model = self.env["plasticos.freight.quote"]
        quote_values = {
            "company_id": request.company_id.id,
            "request_id": request.id,
            "recipient_id": recipient.id,
            "carrier_id": self.carrier.id,
            "response_kind": "quote",
            "quoted_amount": 1200.0,
            "currency_id": self.currency.id,
            "source_channel": "manual",
            "source_message_id": f"message-{request.id}",
        }
        with self.assertRaises(UserError):
            quote_model.create({**quote_values, "selected": True})
        quote = quote_model.create(quote_values)
        with self.assertRaises(UserError):
            quote.write({"selected": True})
        quote.action_select()
        self.assertTrue(quote.selected)
        self.assertEqual(request.quote_ids.filtered("selected"), quote)
        request._rfq_write({"state": "cancelled"})
        with self.assertRaises(UserError):
            quote_model.create({**quote_values, "source_message_id": f"late-{request.id}"})

    def test_calibration_is_append_only_and_corrections_are_attributed(self):
        load, context = self._new_load()
        calibration_model = self.env["plasticos.freight.calibration.observation"]
        calibration_model.create(
            {
                "company_id": load.company_id.id,
                "load_id": load.id,
                "currency_id": self.currency.id,
                "actual_cost_amount": 900.0,
                "context_fingerprint": context.fingerprint,
            }
        )
        load._freight_write(
            {
                "actual_freight_cost": 900.0,
                "actual_freight_currency_id": self.currency.id,
                "actual_freight_recorded_at": "2026-09-20 00:00:00",
            }
        )
        with self.assertRaises(UserError):
            load.write({"actual_freight_cost": 950.0})
        load.action_correct_actual_freight_cost(950.0, self.currency, "Carrier invoice corrected")
        observations = calibration_model.search([("load_id", "=", load.id)], order="observed_at, id")
        self.assertEqual(len(observations), 2)
        self.assertEqual(observations[-1].supersedes_observation_id, observations[0])
        self.assertEqual(observations[-1].recorded_by_id, self.env.user)

    def test_event_correlation_and_legacy_cache_retirement_are_enforced(self):
        load, _context = self._new_load()
        event = self.env["plasticos.freight.event"].search(
            [("load_id", "=", load.id), ("event_type", "=", "freight_state_transition")],
            order="id desc",
            limit=1,
        )
        self.assertTrue(event.correlation_id)
        with self.assertRaises(UserError):
            event.write({"outcome_code": "bypass"})
        with self.assertRaises(UserError):
            self.env["plasticos.rate.memory"].create(
                {"carrier_id": self.carrier.id, "lane_key": "1-2", "rate_amount": 10.0}
            )

    def test_non_logistics_user_cannot_execute_freight_command(self):
        load, _context = self._new_load()
        sales_group = self.env.ref("plasticos_security_base.group_sales_rep", raise_if_not_found=False)
        self.assertTrue(sales_group)
        sales_user = self.env["res.users"].create(
            {
                "name": "Linda Sales Only",
                "login": "linda.sales.only@example.invalid",
                "groups_id": [(6, 0, [sales_group.id])],
            }
        )
        with self.assertRaises(AccessError):
            load.with_user(sales_user).action_request_freight_estimate()
