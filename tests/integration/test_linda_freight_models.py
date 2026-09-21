"""Odoo-runtime regression coverage for Linda's local freight persistence boundary."""

from odoo import fields
from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests.common import tagged

RATE_MEMORY_RECONCILIATION = "plasticos.rate.memory.reconciliation"


@tagged("post_install", "-at_install", "plasticos", "integration", "logistics", "linda")
class TestLindaFreightModels(PlasticosTestCase):
    """Exercise model/ACL/state contracts that pure-Python service tests cannot load."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # These models are the contract under test. A runtime that lacks one has
        # not installed plasticos_logistics correctly, so fail instead of skipping:
        # a skipped suite would let a broken install or upgrade look green.
        for model in (
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
        ):
            assert model in cls.env, f"{model} is not in the registry; plasticos_logistics install/upgrade is broken"
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

    def _user_with_groups(self, login, *group_xml_ids):
        groups = self.env["res.groups"]
        for xml_id in group_xml_ids:
            group = self.env.ref(xml_id, raise_if_not_found=False)
            self.assertTrue(group, f"{xml_id} must exist")
            groups |= group
        # Odoo 19: the user/group relation is ``group_ids`` (``groups_id`` was removed).
        return self.env["res.users"].create({"name": login, "login": login, "group_ids": [(6, 0, groups.ids)]})

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

    def _quote_values(self, request, recipient, **overrides):
        values = {
            "company_id": request.company_id.id,
            "request_id": request.id,
            "recipient_id": recipient.id,
            "carrier_id": recipient.carrier_id.id,
            "response_kind": "quote",
            "quoted_amount": 1200.0,
            "currency_id": self.currency.id,
            "source_channel": "manual",
            "source_message_id": f"message-{request.id}-{recipient.id}",
        }
        values.update(overrides)
        return values

    def test_manual_response_records_provenance_without_fabricating_send_evidence(self):
        """F4: an inbound/manual carrier response must not claim an outbound send occurred."""
        _load, _context, request, recipient = self._new_request()
        self.assertEqual(recipient.state, "pending")
        self.assertEqual(recipient.attempt_count, 0)
        quote = self.env["plasticos.freight.quote"].create(self._quote_values(request, recipient))
        recipient.invalidate_recordset()
        self.assertEqual(recipient.state, "responded")
        self.assertEqual(recipient.response_at, quote.responded_at)
        self.assertEqual(recipient.attempt_count, 0)
        self.assertFalse(recipient.sent_at)
        self.assertFalse(recipient.last_attempt_at)
        self.assertFalse(recipient.outbound_message_ref)
        self.assertFalse(request.sent_at)

    def test_recipient_send_evidence_stays_internally_consistent(self):
        """F4: send facts require a recorded outbound attempt, and vice versa."""
        _load, _context, _request, recipient = self._new_request()
        internal = recipient.with_context(plasticos_logistics_internal_rfq_write=True)
        # Even the workflow capability cannot record a send time without an attempt.
        with self.assertRaises(ValidationError):
            recipient._rfq_write({"sent_at": fields.Datetime.now()})
        with self.assertRaises(UserError):
            # A forged context value is not the in-process capability token.
            internal.write({"attempt_count": 1})

    def test_request_and_recipient_evidence_reject_direct_writes(self):
        """F5: readonly=True is UI-only; lifecycle and delivery evidence is server-guarded."""
        _load, _context, request, recipient = self._new_request()
        quote = self.env["plasticos.freight.quote"].create(self._quote_values(request, recipient))
        now = fields.Datetime.now()
        for values in (
            {"selected_quote_id": quote.id},
            {"sent_at": now},
            {"resolved_at": now},
            {"cancelled_at": now},
            {"cancellation_reason": "forged"},
            {"failure_code": "forged"},
        ):
            with self.assertRaises(UserError, msg=f"request write must be rejected: {values}"):
                request.write(values)
        for values in (
            {"attempt_count": 3},
            {"last_attempt_at": now},
            {"sent_at": now},
            {"response_at": now},
            {"delivery_error_class": "forged"},
            {"outbound_message_ref": "forged"},
            {"state": "sent"},
        ):
            with self.assertRaises(UserError, msg=f"recipient write must be rejected: {values}"):
                recipient.write(values)
        with self.assertRaises(UserError):
            quote.write({"timeliness": "late"})
        # The canonical workflow still resolves the request with its own selected quote.
        quote.action_select()
        request.action_select_quote()
        self.assertEqual(request.state, "resolved")
        self.assertEqual(request.selected_quote_id, quote)
        self.assertTrue(request.resolved_at)

    def test_supersession_enforces_same_request_carrier_company_lineage(self):
        """F5: a superseding response must share request, carrier, and company with its predecessor."""
        _load, _context, request, recipient = self._new_request()
        quote_model = self.env["plasticos.freight.quote"]
        first = quote_model.create(self._quote_values(request, recipient))
        other_carrier = self.env["res.partner"].create({"name": "Linda Other Carrier", "is_company": True})
        other_recipient = self.env["plasticos.freight.quote.recipient"].create(
            {
                "company_id": request.company_id.id,
                "request_id": request.id,
                "carrier_id": other_carrier.id,
                "channel": "manual",
                "destination_snapshot": "operator-entered",
                "idempotency_key": f"recipient-other-{request.id}",
            }
        )
        with self.assertRaises(ValidationError):
            quote_model.create(
                self._quote_values(
                    request, other_recipient, supersedes_quote_id=first.id, source_message_id="other-carrier"
                )
            )
        _load2, _context2, other_request, other_request_recipient = self._new_request()
        with self.assertRaises(ValidationError):
            quote_model.create(
                self._quote_values(
                    other_request,
                    other_request_recipient,
                    supersedes_quote_id=first.id,
                    source_message_id="other-request",
                )
            )
        second = quote_model.create(
            self._quote_values(request, recipient, supersedes_quote_id=first.id, source_message_id="revised")
        )
        self.assertEqual(second.supersedes_quote_id, first)
        self.assertEqual(first.lifecycle_state, "superseded")
        self.assertEqual(second.lifecycle_state, "active")
        with self.assertRaises(ValidationError):
            quote_model.create(
                self._quote_values(request, recipient, supersedes_quote_id=first.id, source_message_id="revised-again")
            )

    def test_logistics_user_can_create_reconciliation_evidence_but_cannot_mutate_it(self):
        """F2: Logistics holds create on reconciliation evidence; write and unlink stay denied."""
        load, context = self._new_load()
        logistics_user = self._user_with_groups("linda.logistics.only", "plasticos_security_base.group_logistics")
        load._confirm_freight_rate(
            rate=1000.0,
            carrier=self.carrier,
            currency=self.currency,
            resolution_method="manual",
            context_fingerprint=context.fingerprint,
        )
        self.assertEqual(load.state, "rate_confirmed")
        sale = load.sale_order_id
        # sudo() justification: legacy rate memory is frozen for every role (no ACL grants
        # create); the fixture row stands in for a pre-existing cache row seeded before the freeze.
        legacy_row = (
            self.env["plasticos.rate.memory"]
            .sudo()
            .with_context(plasticos_logistics_legacy_rate_memory_migration=True)
            .create(
                {
                    "carrier_id": self.carrier.id,
                    "lane_key": f"{sale.partner_shipping_id.id}-{sale.partner_invoice_id.id}",
                    "rate_amount": 1000.0,
                    "rate_date": fields.Date.to_date(load.rate_confirmed_at),
                }
            )
        )
        access = self.env["ir.model.access"].with_user(logistics_user)
        self.assertTrue(access.check(RATE_MEMORY_RECONCILIATION, "create", raise_exception=False))
        self.assertFalse(access.check(RATE_MEMORY_RECONCILIATION, "write", raise_exception=False))
        self.assertFalse(access.check(RATE_MEMORY_RECONCILIATION, "unlink", raise_exception=False))
        legacy_row.with_user(logistics_user).action_reconcile_to_canonical_history()
        evidence = self.env[RATE_MEMORY_RECONCILIATION].search([("legacy_rate_memory_id", "=", legacy_row.id)])
        self.assertEqual(len(evidence), 1)
        self.assertEqual(evidence.disposition, "exact_single_match")
        self.assertEqual(evidence.canonical_load_id, load)
        self.assertEqual(evidence.company_id, load.company_id)
        as_logistics = evidence.with_user(logistics_user)
        self.assertFalse(as_logistics.has_access("write"))
        self.assertFalse(as_logistics.has_access("unlink"))
        with self.assertRaises(UserError):
            as_logistics.write({"disposition": "no_candidate_match"})
        with self.assertRaises(UserError):
            as_logistics.unlink()

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
        sales_user = self._user_with_groups("linda.sales.only", "plasticos_security_base.group_sales_rep")
        with self.assertRaises(AccessError):
            load.with_user(sales_user).action_request_freight_estimate()

    def test_sal_provenance_fields_exist_with_safe_defaults(self):
        load, _context = self._new_load()
        self.assertIn("sal_decision", load._fields)
        self.assertIn("sal_source_load_id", load._fields)
        self.assertIn("freight_context_fingerprint", load._fields)
        self.assertIn("rate_resolution_method", load._fields)
        self.assertFalse(load.rate_confirmed_at)
        self.assertFalse(load.sal_source_load_id)

    def test_confirmed_sal_booking_terms_reject_direct_edits(self):
        load, context = self._new_load()
        load._freight_write(
            {
                "carrier_id": self.carrier.id,
                "rate_amount": 1500.0,
                "rate_currency_id": self.currency.id,
                "rate_confirmed_at": fields.Datetime.now(),
                "rate_resolution_method": "sal",
                "freight_context_fingerprint": context.fingerprint,
                "sal_decision": "hit",
            }
        )
        with self.assertRaises(UserError):
            load.write({"rate_amount": 1.0})
        with self.assertRaises(UserError):
            load.write({"carrier_id": False})

    def test_direct_load_create_cannot_bypass_state_or_provenance(self):
        """R3: create() is guarded like write(); a caller cannot start past Draft or with provenance."""
        sale = self.env["sale.order"].create({"partner_id": self.destination.id})
        base = {
            "sale_order_id": sale.id,
            "pickup_partner_id": self.origin.id,
            "delivery_partner_id": self.destination.id,
            "reference_weight": 40000,
            "rate_currency_id": self.currency.id,
        }
        load_model = self.env["plasticos.load"]
        for forged in (
            {"state": "rate_confirmed"},
            {"state": "delivered"},
            {"rate_confirmed_at": fields.Datetime.now()},
            {"rate_resolution_method": "manual"},
            {"sal_decision": "hit"},
        ):
            with self.assertRaises(UserError, msg=f"load create must be rejected: {forged}"):
                load_model.create({**base, **forged})
        load = load_model.create(base)
        self.assertEqual(load.state, "draft")
        self.assertFalse(load.rate_confirmed_at)

    def test_duplicated_load_starts_in_draft_without_provenance(self):
        """Odoo's Duplicate action must not inherit workflow-owned state or provenance."""
        load, context = self._new_load()
        load._freight_write(
            {
                "carrier_id": self.carrier.id,
                "rate_amount": 1500.0,
                "rate_currency_id": self.currency.id,
                "rate_confirmed_at": fields.Datetime.now(),
                "rate_resolution_method": "manual",
                "freight_context_fingerprint": context.fingerprint,
                "sal_decision": "miss",
            }
        )
        duplicate = load.copy()
        self.assertEqual(duplicate.state, "draft")
        self.assertFalse(duplicate.rate_confirmed_at)
        self.assertFalse(duplicate.rate_resolution_method)
        self.assertFalse(duplicate.sal_decision)
        self.assertFalse(duplicate.freight_context_fingerprint)

    def test_rate_confirmation_cancels_orphaned_rfq_episodes_durably(self):
        """Confirming a rate through any path cancels other active episodes in the same transaction."""
        load, context, request, _recipient = self._new_request()
        load._confirm_freight_rate(
            rate=1000.0,
            carrier=self.carrier,
            currency=self.currency,
            resolution_method="manual",
            context_fingerprint=context.fingerprint,
        )
        request.invalidate_recordset()
        self.assertEqual(request.state, "cancelled")
        self.assertEqual(request.cancellation_reason, "load_rate_confirmed")
        event = self.env["plasticos.freight.event"].search(
            [("load_id", "=", load.id), ("event_type", "=", "rfq_request_cancelled_rate_confirmed")],
            limit=1,
        )
        self.assertTrue(event)
        self.assertEqual(event.outcome_code, "load_rate_confirmed")

    def test_recipient_idempotency_key_is_derived_when_absent(self):
        """R4: operators add recipients through the request form without supplying a key."""
        from odoo.addons.plasticos_logistics.models.freight_quote import recipient_idempotency_key

        load, _context = self._new_load()
        request = self.env["plasticos.freight.quote.request"].create({"load_id": load.id})
        recipient = self.env["plasticos.freight.quote.recipient"].create(
            {
                "company_id": load.company_id.id,
                "request_id": request.id,
                "carrier_id": self.carrier.id,
                "channel": "manual",
                "destination_snapshot": "operator-entered",
            }
        )
        self.assertEqual(recipient.idempotency_key, recipient_idempotency_key(request.id, self.carrier.id, "manual"))

    def test_stale_context_guard_never_writes_and_resolution_cancels_durably(self):
        """R5: the request guard raises without writing; load resolution persists the cancellation."""
        load, _context, request, _recipient = self._new_request()
        load.write({"reference_weight": 41000})
        # A plain try/except (no savepoint) so a write by the guard would remain visible.
        try:
            request.action_rank_quotes()
        except UserError:
            pass
        else:
            self.fail("a stale freight quote request must be refused")
        request.invalidate_recordset()
        self.assertEqual(request.state, "draft")
        self.assertFalse(request.cancelled_at)
        load.action_resolve_freight()
        request.invalidate_recordset()
        self.assertEqual(request.state, "cancelled")
        self.assertEqual(request.cancellation_reason, "context_changed")
        self.assertTrue(request.cancelled_at)
        event = self.env["plasticos.freight.event"].search(
            [("load_id", "=", load.id), ("event_type", "=", "rfq_request_cancelled_context_change")],
            limit=1,
        )
        self.assertTrue(event)
        self.assertEqual(event.facts.get("request_id"), request.id)
