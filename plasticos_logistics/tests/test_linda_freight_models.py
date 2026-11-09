"""Odoo-runtime regression coverage for Linda's local freight persistence boundary."""

from datetime import timedelta
from unittest.mock import patch

from psycopg2.errors import UniqueViolation

from odoo import fields
from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests.common import tagged
from odoo.tools import mute_logger

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

    def _new_load(self, buyer=None):
        # polymer_id / form_id are required=True (plasticos_intake/models/intake.py:181-196).
        buyer = buyer or self.destination
        intake = self.env["plasticos.intake"].create(
            {
                "partner_id": self.origin.id,
                "polymer_id": self.default_polymer.id,
                "form_id": self.default_form.id,
            }
        )
        sale = self.env["sale.order"].create({"partner_id": buyer.id})
        load = self.env["plasticos.load"].create(
            {
                "sale_order_id": sale.id,
                "pickup_partner_id": self.origin.id,
                "delivery_partner_id": buyer.id,
                "reference_weight": 40000,
                "rate_currency_id": self.currency.id,
            }
        )
        transaction = self.env["plasticos.transaction"].create(
            {
                "sale_order_id": sale.id,
                "supplier_id": self.origin.id,
                "buyer_id": buyer.id,
                "intake_id": intake.id,
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

    def test_supersession_check_counts_superseders_once_per_batch(self):
        """A batch create superseding one prior twice is rejected; two priors superseded once each pass with one grouped count."""
        _load, _context, request, recipient = self._new_request()
        quote_model = self.env["plasticos.freight.quote"]
        first = quote_model.create(self._quote_values(request, recipient))
        with self.assertRaises(ValidationError):
            quote_model.create(
                [
                    self._quote_values(request, recipient, supersedes_quote_id=first.id, source_message_id="batch-a"),
                    self._quote_values(request, recipient, supersedes_quote_id=first.id, source_message_id="batch-b"),
                ]
            )
        _load2, _context2, other_request, other_recipient = self._new_request()
        other_first = quote_model.create(self._quote_values(other_request, other_recipient))
        quote_cls = type(quote_model)
        real_read_group = quote_cls._read_group
        grouped = []

        def counting_read_group(model, domain, *args, **kwargs):
            grouped.append(domain)
            return real_read_group(model, domain, *args, **kwargs)

        with patch.object(quote_cls, "_read_group", counting_read_group):
            pair = quote_model.create(
                [
                    self._quote_values(request, recipient, supersedes_quote_id=first.id, source_message_id="batch-c"),
                    self._quote_values(
                        other_request, other_recipient, supersedes_quote_id=other_first.id, source_message_id="batch-d"
                    ),
                ]
            )
        self.assertEqual(pair.mapped("supersedes_quote_id"), first | other_first)
        lineage_counts = [
            domain for domain in grouped if any(isinstance(t, tuple) and t[0] == "supersedes_quote_id" for t in domain)
        ]
        self.assertEqual(len(lineage_counts), 1, grouped)

    def test_reconciliation_of_two_legacy_rows_creates_evidence_in_one_batch(self):
        load, context = self._new_load()
        load._confirm_freight_rate(
            rate=1000.0,
            carrier=self.carrier,
            currency=self.currency,
            resolution_method="manual",
            context_fingerprint=context.fingerprint,
        )
        other_buyer = self.env["res.partner"].create(
            {"name": "Linda Other Buyer", "is_company": True, "customer_rank": 1}
        )
        other_load, other_context = self._new_load(buyer=other_buyer)
        other_load._confirm_freight_rate(
            rate=1100.0,
            carrier=self.carrier,
            currency=self.currency,
            resolution_method="manual",
            context_fingerprint=other_context.fingerprint,
        )

        def legacy_vals(confirmed_load, amount):
            sale = confirmed_load.sale_order_id
            return {
                "carrier_id": self.carrier.id,
                "lane_key": f"{sale.partner_shipping_id.id}-{sale.partner_invoice_id.id}",
                "rate_amount": amount,
                "rate_date": fields.Date.to_date(confirmed_load.rate_confirmed_at),
            }

        # sudo() justification: legacy rate memory is frozen for every role (no ACL grants
        # create); the fixture rows stand in for pre-existing cache rows seeded before the freeze.
        legacy_rows = (
            self.env["plasticos.rate.memory"]
            .sudo()
            .with_context(plasticos_logistics_legacy_rate_memory_migration=True)
            .create([legacy_vals(load, 1000.0), legacy_vals(other_load, 1100.0)])
        )
        evidence_cls = type(self.env[RATE_MEMORY_RECONCILIATION])
        real_create = evidence_cls.create
        creates = []

        def counting_create(model, vals_list):
            creates.append(vals_list)
            return real_create(model, vals_list)

        with patch.object(evidence_cls, "create", counting_create):
            legacy_rows.action_reconcile_to_canonical_history()
        self.assertEqual(len(creates), 1, creates)
        evidence = self.env[RATE_MEMORY_RECONCILIATION].search([("legacy_rate_memory_id", "in", legacy_rows.ids)])
        self.assertEqual(len(evidence), 2)
        self.assertEqual(set(evidence.mapped("disposition")), {"exact_single_match"})
        self.assertEqual(set(evidence.mapped("canonical_load_id").ids), {load.id, other_load.id})
        # A second reconciliation of the same rows adds nothing.
        legacy_rows.action_reconcile_to_canonical_history()
        self.assertEqual(
            self.env[RATE_MEMORY_RECONCILIATION].search_count([("legacy_rate_memory_id", "in", legacy_rows.ids)]), 2
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

    def _legacy_cache_row(self, lane_key, amount, rate_date):
        # sudo() justification: legacy rate memory is frozen for every role (no ACL grants
        # create); the fixture row stands in for a pre-existing cache row seeded before the freeze.
        return (
            self.env["plasticos.rate.memory"]
            .sudo()
            .with_context(plasticos_logistics_legacy_rate_memory_migration=True)
            .create(
                {
                    "carrier_id": self.carrier.id,
                    "lane_key": lane_key,
                    "rate_amount": amount,
                    "rate_date": rate_date,
                }
            )
        )

    def test_non_exact_dispositions_stay_unowned_and_rerun_adds_nothing(self):
        """ADR-129: the four non-exact dispositions persist with an explicit empty company."""
        load, context = self._new_load()
        load._confirm_freight_rate(
            rate=1000.0,
            carrier=self.carrier,
            currency=self.currency,
            resolution_method="manual",
            context_fingerprint=context.fingerprint,
        )
        other_buyer = self.env["res.partner"].create(
            {"name": "Linda Unowned Buyer", "is_company": True, "customer_rank": 1}
        )
        other_load, other_context = self._new_load(buyer=other_buyer)
        other_load._confirm_freight_rate(
            rate=1100.0,
            carrier=self.carrier,
            currency=self.currency,
            resolution_method="manual",
            context_fingerprint=other_context.fingerprint,
        )
        rate_date = fields.Date.to_date(load.rate_confirmed_at)
        rows = {
            "invalid_lane_key": self._legacy_cache_row("nolanekey", 1.0, rate_date),
            "no_candidate_match": self._legacy_cache_row("999999-999998", 2.0, rate_date),
            "multiple_candidate_matches": self._legacy_cache_row("multi-lane", 3.0, rate_date),
            "candidate_scan_truncated": self._legacy_cache_row("trunc-lane", 4.0, rate_date),
        }
        from odoo.addons.plasticos_logistics.services.freight_history import legacy_lane_candidates

        def candidates(env, legacy_row, **kwargs):
            if legacy_row.lane_key == "multi-lane":
                return load | other_load, False, True
            if legacy_row.lane_key == "trunc-lane":
                return load, True, True
            return legacy_lane_candidates(env, legacy_row, **kwargs)

        recordset = self.env["plasticos.rate.memory"].browse([row.id for row in rows.values()])
        with patch(
            "odoo.addons.plasticos_logistics.services.freight_history.legacy_lane_candidates",
            side_effect=candidates,
        ):
            recordset.action_reconcile_to_canonical_history()
            recordset.action_reconcile_to_canonical_history()
        evidence = self.env[RATE_MEMORY_RECONCILIATION].search([("legacy_rate_memory_id", "in", recordset.ids)])
        self.assertEqual(len(evidence), 4)
        by_disposition = {row.disposition: row for row in evidence}
        self.assertEqual(set(by_disposition), set(rows))
        for row in evidence:
            self.assertFalse(row.company_id)
            self.assertFalse(row.canonical_load_id)
            self.assertNotEqual(row.company_id, self.env.company)

    def test_exact_match_in_another_company_is_rejected_and_hidden(self):
        """ADR-129: an exact match keeps its load company and is not visible in another company."""
        load, context = self._new_load()
        load._confirm_freight_rate(
            rate=1000.0,
            carrier=self.carrier,
            currency=self.currency,
            resolution_method="manual",
            context_fingerprint=context.fingerprint,
        )
        sale = load.sale_order_id
        rate_date = fields.Date.to_date(load.rate_confirmed_at)
        lane_key = f"{sale.partner_shipping_id.id}-{sale.partner_invoice_id.id}"
        owned = self._legacy_cache_row(lane_key, 1000.0, rate_date)
        owned.action_reconcile_to_canonical_history()
        exact = self.env[RATE_MEMORY_RECONCILIATION].search([("legacy_rate_memory_id", "=", owned.id)])
        self.assertEqual(exact.company_id, load.company_id)
        self.assertEqual(exact.canonical_load_id, load)
        other_company = self.env["res.company"].create({"name": "Linda Other Company", "currency_id": self.currency.id})
        mismatched = self._legacy_cache_row(lane_key, 1000.0, fields.Date.add(rate_date, days=1))
        with self.assertRaises(ValidationError):
            self.env[RATE_MEMORY_RECONCILIATION].create(
                {
                    "company_id": other_company.id,
                    "legacy_rate_memory_id": mismatched.id,
                    "carrier_id": mismatched.carrier_id.id,
                    "lane_key": mismatched.lane_key,
                    "legacy_rate_amount": mismatched.rate_amount,
                    "legacy_rate_date": mismatched.rate_date,
                    "disposition": "exact_single_match",
                    "canonical_load_id": load.id,
                    "candidate_count": 1,
                }
            )
        reader = self.env["res.users"].create(
            {
                "name": "Linda Other Reader",
                "login": "linda.other.reader",
                "company_id": other_company.id,
                "company_ids": [(6, 0, [other_company.id])],
                "group_ids": [(6, 0, [self.env.ref("base.group_user").id])],
            }
        )
        self.assertFalse(self.env[RATE_MEMORY_RECONCILIATION].with_user(reader).search([("id", "=", exact.id)]))
        unowned = self._legacy_cache_row("nolanekey", 5.0, rate_date)
        unowned.action_reconcile_to_canonical_history()
        unowned_evidence = self.env[RATE_MEMORY_RECONCILIATION].search([("legacy_rate_memory_id", "=", unowned.id)])
        self.assertFalse(unowned_evidence.company_id)
        self.assertEqual(
            self.env[RATE_MEMORY_RECONCILIATION].with_user(reader).search([("id", "=", unowned_evidence.id)]),
            unowned_evidence,
        )

    def test_user_without_reconciliation_read_cannot_see_unowned_rows(self):
        portal = self._user_with_groups("linda.no.reconciliation.read", "base.group_portal")
        with self.assertRaises(AccessError):
            self.env[RATE_MEMORY_RECONCILIATION].with_user(portal).search([])

    # ── Issue #182 / ADR-129: one global classification per legacy row ─────────

    def _company_b(self):
        return self.env["res.company"].create({"name": "Linda Company B", "currency_id": self.currency.id})

    def _logistics_user(self, login, companies):
        groups = self.env.ref("base.group_user") | self.env.ref("plasticos_security_base.group_logistics")
        return self.env["res.users"].create(
            {
                "name": login,
                "login": login,
                "company_id": companies[0].id,
                "company_ids": [(6, 0, companies.ids)],
                "group_ids": [(6, 0, groups.ids)],
            }
        )

    def _company_a_exact_row(self, amount):
        """A legacy row whose only matching canonical load belongs to the main company (A)."""
        load, context = self._new_load()
        load._confirm_freight_rate(
            rate=amount,
            carrier=self.carrier,
            currency=self.currency,
            resolution_method="manual",
            context_fingerprint=context.fingerprint,
        )
        sale = load.sale_order_id
        legacy = self._legacy_cache_row(
            f"{sale.partner_shipping_id.id}-{sale.partner_invoice_id.id}",
            amount,
            fields.Date.to_date(load.rate_confirmed_at),
        )
        return load, legacy

    def _reconciliation_count(self, legacy):
        # sudo() justification: the assertion is about the global row count, which
        # company isolation would hide from the test user.
        return self.env[RATE_MEMORY_RECONCILIATION].sudo().search_count([("legacy_rate_memory_id", "in", legacy.ids)])

    def test_company_b_first_cannot_record_a_false_no_candidate_match(self):
        """Case A: B cannot see A's matching load, so B records nothing; A's later run keeps the true match."""
        from odoo.addons.plasticos_logistics.services.freight_history import legacy_lane_candidates

        company_a = self.env.company
        load, legacy = self._company_a_exact_row(1310.0)
        genuine = self._legacy_cache_row("999991-999992", 1311.0, legacy.rate_date)
        user_b = self._logistics_user("linda.company.b.first", self._company_b())

        candidates, truncated, complete = legacy_lane_candidates(legacy.with_user(user_b).env, legacy)
        self.assertFalse(complete)
        self.assertFalse(truncated)
        self.assertFalse(candidates, "a load outside the actor's access must not leave the candidate scan")

        batch = (legacy | genuine).with_user(user_b)
        with self.assertRaises(AccessError):
            batch.action_reconcile_to_canonical_history()
        # Fail closed for the whole batch: neither the false no-match nor the genuine one is stored.
        self.assertEqual(self._reconciliation_count(legacy | genuine), 0)

        user_a = self._logistics_user("linda.company.a.after", company_a)
        legacy.with_user(user_a).action_reconcile_to_canonical_history()
        evidence = self.env[RATE_MEMORY_RECONCILIATION].search([("legacy_rate_memory_id", "=", legacy.id)])
        self.assertEqual(evidence.disposition, "exact_single_match")
        self.assertEqual(evidence.canonical_load_id, load)
        self.assertEqual(evidence.company_id, company_a)
        self.assertEqual(evidence.candidate_count, 1)

    def test_company_a_first_then_b_replays_without_duplicate_or_disclosure(self):
        """Case B: B's replay of A's exact match adds nothing, raises nothing and shows B nothing."""
        company_a = self.env.company
        load, legacy = self._company_a_exact_row(1320.0)
        user_a = self._logistics_user("linda.company.a.first", company_a)
        legacy.with_user(user_a).action_reconcile_to_canonical_history()
        self.assertEqual(self._reconciliation_count(legacy), 1)

        user_b = self._logistics_user("linda.company.b.replay", self._company_b())
        self.assertTrue(legacy.with_user(user_b).action_reconcile_to_canonical_history())
        self.assertEqual(self._reconciliation_count(legacy), 1)
        self.assertFalse(
            self.env[RATE_MEMORY_RECONCILIATION].with_user(user_b).search([("legacy_rate_memory_id", "=", legacy.id)])
        )
        with self.assertRaises(AccessError):
            load.with_user(user_b).read(["name"])
        evidence = self.env[RATE_MEMORY_RECONCILIATION].search([("legacy_rate_memory_id", "=", legacy.id)])
        self.assertEqual(evidence.company_id, company_a)
        self.assertEqual(evidence.canonical_load_id, load)

    def test_genuine_no_match_is_one_unowned_row_from_any_company(self):
        """Case C: a complete search that finds nothing stores exactly one unowned no-match row."""
        company_b = self._company_b()
        user_b = self._logistics_user("linda.company.b.nomatch", company_b)
        legacy = self._legacy_cache_row("999993-999994", 1330.0, fields.Date.today())
        legacy.with_user(user_b).action_reconcile_to_canonical_history()
        legacy.with_user(user_b).action_reconcile_to_canonical_history()
        self.assertEqual(self._reconciliation_count(legacy), 1)
        evidence = (
            self.env[RATE_MEMORY_RECONCILIATION].with_user(user_b).search([("legacy_rate_memory_id", "=", legacy.id)])
        )
        self.assertEqual(evidence.disposition, "no_candidate_match")
        self.assertFalse(evidence.company_id)
        self.assertFalse(evidence.canonical_load_id)
        self.assertEqual(evidence.candidate_count, 0)
        user_a = self._logistics_user("linda.company.a.nomatch", self.env.company)
        self.assertEqual(
            self.env[RATE_MEMORY_RECONCILIATION].with_user(user_a).search([("legacy_rate_memory_id", "=", legacy.id)]),
            evidence,
        )

    def test_repeat_reconciliation_is_idempotent_across_company_switching_and_fresh_env(self):
        """Case D: the active-company switch never changes the stored answer or duplicates it.

        A real process restart cannot run inside one test transaction; a fresh environment with
        every cache dropped proves the replay reads only database state. The cross-process replay
        is proven separately on the upgraded database.
        """
        company_a = self.env.company
        company_b = self._company_b()
        load, legacy = self._company_a_exact_row(1340.0)
        operator = self._logistics_user("linda.company.ab", company_b | company_a)

        only_b = legacy.with_user(operator).with_context(allowed_company_ids=[company_b.id])
        with self.assertRaises(AccessError):
            only_b.action_reconcile_to_canonical_history()
        self.assertEqual(self._reconciliation_count(legacy), 0)

        both = legacy.with_user(operator).with_context(allowed_company_ids=[company_a.id, company_b.id])
        both.action_reconcile_to_canonical_history()
        both.action_reconcile_to_canonical_history()
        self.assertTrue(only_b.action_reconcile_to_canonical_history())
        # Only database state survives: drop every cache and use a fresh environment.
        self.env.invalidate_all()
        fresh = self.env(user=operator.id, context={"allowed_company_ids": [company_b.id]})
        self.assertTrue(fresh["plasticos.rate.memory"].browse(legacy.id).action_reconcile_to_canonical_history())
        self.assertEqual(self._reconciliation_count(legacy), 1)
        evidence = self.env[RATE_MEMORY_RECONCILIATION].search([("legacy_rate_memory_id", "=", legacy.id)])
        self.assertEqual(evidence.disposition, "exact_single_match")
        self.assertEqual(evidence.canonical_load_id, load)
        self.assertEqual(evidence.company_id, company_a)

    def _confirmed_load_in(self, company, rate, buyer=None):
        """A rate-confirmed load whose sale order (and so company) is ``company``."""
        main_env = self.env
        self.env = self.env(context=dict(self.env.context, allowed_company_ids=[company.id]))
        try:
            load, context = self._new_load(buyer=buyer)
            load._confirm_freight_rate(
                rate=rate,
                carrier=self.carrier,
                currency=self.currency,
                resolution_method="manual",
                context_fingerprint=context.fingerprint,
            )
        finally:
            self.env = main_env
        self.assertEqual(load.company_id, company)
        return load.with_env(main_env)

    def test_real_classifier_records_multiple_candidate_matches_unowned(self):
        """Two readable loads on one lane, carrier, amount and date: no stub, one unowned row."""
        company_a = self.env.company
        first = self._confirmed_load_in(company_a, 1390.0)
        second = self._confirmed_load_in(company_a, 1390.0)
        self.assertEqual(first.rate_confirmed_at.date(), second.rate_confirmed_at.date())
        sale = first.sale_order_id
        legacy = self._legacy_cache_row(
            f"{sale.partner_shipping_id.id}-{sale.partner_invoice_id.id}",
            1390.0,
            fields.Date.to_date(first.rate_confirmed_at),
        )
        user_a = self._logistics_user("linda.real.multiple", company_a)
        legacy.with_user(user_a).action_reconcile_to_canonical_history()
        evidence = self.env[RATE_MEMORY_RECONCILIATION].search([("legacy_rate_memory_id", "=", legacy.id)])
        self.assertEqual(evidence.disposition, "multiple_candidate_matches")
        self.assertEqual(evidence.candidate_count, 2)
        self.assertFalse(evidence.company_id)
        self.assertFalse(evidence.canonical_load_id)

    def test_real_scan_truncation_is_decided_by_every_scanned_load(self):
        """A truncated scan counts unmatched loads too, so one the actor cannot read makes it incomplete."""
        from odoo.addons.plasticos_logistics.services.freight_history import legacy_lane_candidates

        company_a = self.env.company
        company_b = self._company_b()
        matching = self._confirmed_load_in(company_a, 1395.0)
        other_buyer = self.env["res.partner"].create(
            {"name": "Linda Company B Buyer", "is_company": True, "customer_rank": 1}
        )
        unmatched_b = self._confirmed_load_in(company_b, 1395.0, buyer=other_buyer)
        sale = matching.sale_order_id
        legacy = self._legacy_cache_row(
            f"{sale.partner_shipping_id.id}-{sale.partner_invoice_id.id}",
            1395.0,
            fields.Date.to_date(matching.rate_confirmed_at),
        )
        self.assertEqual(fields.Date.to_date(unmatched_b.rate_confirmed_at), legacy.rate_date)
        user_a_env = legacy.with_user(self._logistics_user("linda.real.truncated", company_a)).env

        # Not truncated: only the lane match decides, and the actor can read it.
        candidates, truncated, complete = legacy_lane_candidates(user_a_env, legacy, scan_limit=5)
        self.assertEqual((candidates, truncated, complete), (matching.with_env(user_a_env), False, True))
        # Truncated at one load: both scanned loads decide, and company B's is unreadable.
        candidates, truncated, complete = legacy_lane_candidates(user_a_env, legacy, scan_limit=1)
        self.assertEqual((bool(candidates), truncated, complete), (False, True, False))
        # The same truncated scan is complete for an actor who can read both loads.
        candidates, truncated, complete = legacy_lane_candidates(self.env, legacy, scan_limit=1)
        self.assertTrue(truncated)
        self.assertTrue(complete)

    # ── ADR-129 model boundary: direct ORM creates ─────────────────────────────

    def _reconciliation_vals(self, legacy, **overrides):
        values = {
            "legacy_rate_memory_id": legacy.id,
            "carrier_id": legacy.carrier_id.id,
            "lane_key": legacy.lane_key,
            "legacy_rate_amount": legacy.rate_amount,
            "legacy_rate_date": legacy.rate_date,
            "disposition": "no_candidate_match",
            "company_id": False,
            "canonical_load_id": False,
            "candidate_count": 0,
        }
        values.update(overrides)
        return values

    def test_direct_create_rejects_invalid_exact_match_ownership(self):
        load, legacy = self._company_a_exact_row(1350.0)
        model = self.env[RATE_MEMORY_RECONCILIATION]
        exact = {"disposition": "exact_single_match", "candidate_count": 1}
        companyless_load = self.env["plasticos.load"].create(
            {
                "pickup_partner_id": self.origin.id,
                "delivery_partner_id": self.destination.id,
                "reference_weight": 40000,
                "rate_currency_id": self.currency.id,
            }
        )
        self.assertFalse(companyless_load.company_id)
        cases = {
            "no canonical load": {"company_id": load.company_id.id},
            "no determinable company": {"canonical_load_id": companyless_load.id},
            "no company on the row": {"canonical_load_id": load.id},
            "wrong company": {"company_id": self._company_b().id, "canonical_load_id": load.id},
        }
        for label, overrides in cases.items():
            with self.subTest(label), self.assertRaises(ValidationError):
                model.create(self._reconciliation_vals(legacy, **exact, **overrides))
        self.assertEqual(self._reconciliation_count(legacy), 0)
        accepted = model.create(
            self._reconciliation_vals(legacy, **exact, company_id=load.company_id.id, canonical_load_id=load.id)
        )
        self.assertEqual(accepted.company_id, load.company_id)
        self.assertEqual(accepted.canonical_load_id, load)

    def test_direct_create_rejects_fabricated_ownership_on_non_exact_dispositions(self):
        load, legacy = self._company_a_exact_row(1360.0)
        model = self.env[RATE_MEMORY_RECONCILIATION]
        for disposition in (
            "invalid_lane_key",
            "no_candidate_match",
            "multiple_candidate_matches",
            "candidate_scan_truncated",
        ):
            for label, overrides in (
                ("fabricated company", {"company_id": self.env.company.id}),
                ("canonical load", {"canonical_load_id": load.id}),
                ("both", {"company_id": load.company_id.id, "canonical_load_id": load.id}),
            ):
                with self.subTest(disposition=disposition, case=label), self.assertRaises(ValidationError):
                    model.create(self._reconciliation_vals(legacy, disposition=disposition, **overrides))
        for disposition in ("rate_mismatch", "missing_canonical_rate"):
            for overrides in ({}, {"company_id": load.company_id.id, "canonical_load_id": load.id}):
                with self.subTest(disposition=disposition, linked=bool(overrides)), self.assertRaises(ValidationError):
                    model.create(self._reconciliation_vals(legacy, disposition=disposition, **overrides))
        self.assertEqual(self._reconciliation_count(legacy), 0)

    def test_direct_create_accepts_each_unowned_disposition_and_keeps_the_boundary(self):
        logistics_user = self._logistics_user("linda.direct.unowned", self.env.company)
        model = self.env[RATE_MEMORY_RECONCILIATION].with_user(logistics_user)
        rate_date = fields.Date.today()
        created = model.browse()
        for index, disposition in enumerate(
            ("invalid_lane_key", "no_candidate_match", "multiple_candidate_matches", "candidate_scan_truncated")
        ):
            legacy = self._legacy_cache_row(f"88880{index}-88881{index}", 1370.0 + index, rate_date)
            row = model.create(self._reconciliation_vals(legacy, disposition=disposition))
            self.assertFalse(row.company_id)
            self.assertFalse(row.canonical_load_id)
            created |= row
        self.assertEqual(len(created), 4)

        fresh = self._legacy_cache_row("888890-888891", 1380.0, rate_date)
        with self.assertRaises(ValidationError):
            model.create(self._reconciliation_vals(fresh, legacy_rate_amount=fresh.rate_amount + 1))
        self.assertEqual(self._reconciliation_count(fresh), 0)
        legacy = created[0].legacy_rate_memory_id
        with mute_logger("odoo.sql_db"), self.assertRaises(UniqueViolation):
            model.create(self._reconciliation_vals(legacy, disposition="no_candidate_match"))

        row = created[0]
        with self.assertRaises(UserError):
            row.write({"company_id": self.env.company.id})
        with self.assertRaises(UserError):
            row.unlink()
        portal = self._user_with_groups("linda.direct.portal", "base.group_portal")
        with self.assertRaises(AccessError):
            self.env[RATE_MEMORY_RECONCILIATION].with_user(portal).search([("id", "=", row.id)])

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

    def _estimate(self, load, request_fingerprint, source_model="plasticos.load"):
        from odoo.addons.plasticos_logistics.models.freight_governance import create_freight_evidence

        return create_freight_evidence(
            self.env,
            "plasticos.freight.estimate",
            {
                "context_fingerprint": "ctx-count",
                "request_fingerprint": request_fingerprint,
                "fingerprint_version": "freight_context_v3",
                "source_model": source_model,
                "source_record_id": load.id,
                "origin_partner_id": self.origin.id,
                "destination_partner_id": self.destination.id,
                "geometry_status": "missing_or_invalid",
                "status": "insufficient_evidence",
                "failure_code": "test_count",
            },
            load=load,
        )

    def test_freight_evidence_counts_read_the_recordset_once(self):
        """Quote requests and load-sourced estimates count for the whole recordset."""
        load, _context = self._new_load()
        bare, _bare_context = self._new_load()
        self.env["plasticos.freight.quote.request"].create({"load_id": load.id})
        with self.assertRaises(UserError):
            self.env["plasticos.freight.quote.request"].create({"load_id": load.id})
        self._estimate(load, "fp-count-1")
        self._estimate(load, "fp-count-2")
        self._estimate(bare, "fp-other-model", source_model="res.partner")
        pair = load | bare
        pair.mapped("freight_quote_request_count")
        pair.mapped("freight_estimate_count")
        self.assertEqual(load.freight_quote_request_count, 1)
        self.assertEqual(bare.freight_quote_request_count, 0)
        self.assertEqual(load.freight_estimate_count, 2)
        self.assertEqual(bare.freight_estimate_count, 0)

    def test_cancel_stale_requests_keeps_fingerprint_and_outside_loads(self):
        """One cancel covers the recordset and leaves an excluded or outside request draft."""
        load_a, context_a, request_a, _recipient_a = self._new_request()
        _load_b, _context_b, request_b, _recipient_b = self._new_request()
        outside, _outside_context, outside_request, _outside_recipient = self._new_request()
        with self.assertRaises(KeyError):
            load_a._cancel_stale_freight_quote_requests(context_a.fingerprint, "corr-bad", reason="not-a-reason")
        self.assertEqual(request_a.state, "draft")
        (load_a | request_b.load_id)._cancel_stale_freight_quote_requests(
            context_a.fingerprint,
            "corr-batch",
            reason="context_changed",
        )
        request_a.invalidate_recordset()
        request_b.invalidate_recordset()
        outside_request.invalidate_recordset()
        self.assertEqual(request_a.state, "draft")
        self.assertEqual(request_b.state, "cancelled")
        self.assertEqual(request_b.cancellation_reason, "context_changed")
        self.assertEqual(outside_request.state, "draft")
        kept, _kept_context, kept_request, _kept_recipient = self._new_request()
        kept._cancel_stale_freight_quote_requests(
            None,
            "corr-exclude",
            reason="load_rate_confirmed",
            exclude_request_ids=kept_request.ids,
        )
        kept_request.invalidate_recordset()
        self.assertEqual(kept_request.state, "draft")

    def test_dispatch_ack_cron_escalates_only_the_aged_test_loads(self):
        """The acknowledgment cron looks up today's activities once and skips a fresh sibling."""
        aged, aged_context = self._new_load()
        fresh, fresh_context = self._new_load()
        aged_sent = fields.Datetime.now() - timedelta(hours=5)
        fresh_sent = fields.Datetime.now() - timedelta(hours=1)
        for load, context, sent_at in ((aged, aged_context, aged_sent), (fresh, fresh_context, fresh_sent)):
            load._confirm_freight_rate(
                rate=1000.0,
                carrier=self.carrier,
                currency=self.currency,
                resolution_method="manual",
                context_fingerprint=context.fingerprint,
            )
            pickup = fields.Datetime.now()
            load.action_schedule(pickup, pickup)
            load.action_dispatch()
            load.write({"dispatch_sent": sent_at})
        self.env["plasticos.load"]._cron_check_dispatch_acknowledgments()
        self.env["plasticos.load"]._cron_check_dispatch_acknowledgments()
        activities = self.env["mail.activity"].search(
            [
                ("res_model", "=", "plasticos.load"),
                ("res_id", "in", [aged.id, fresh.id]),
                ("summary", "ilike", "URGENT: No carrier acknowledgment"),
            ]
        )
        self.assertEqual(activities.mapped("res_id"), [aged.id])

    def test_two_loads_create_two_rfq_rows_and_a_repeat_creates_none(self):
        """One RFQ command inserts the missing rows and keeps each load's correlation id."""
        first, _first_context = self._new_load()
        second, _second_context = self._new_load()
        pair = first | second
        pair.action_create_freight_quote_request()
        requests = self.env["plasticos.freight.quote.request"].search([("load_id", "in", pair.ids)])
        events = self.env["plasticos.freight.event"].search(
            [("load_id", "in", pair.ids), ("event_type", "=", "rfq_request_created")]
        )
        self.assertEqual(set(requests.mapped("load_id").ids), set(pair.ids))
        self.assertEqual(len(events), 2)
        self.assertEqual(len(set(events.mapped("correlation_id"))), 2)
        pair.action_create_freight_quote_request()
        self.assertEqual(
            self.env["plasticos.freight.quote.request"].search_count([("load_id", "in", pair.ids)]),
            2,
        )

    def test_second_actual_cost_raises_and_a_correction_supersedes(self):
        """An initial calibration is unique. A correction names the row it supersedes."""
        load, _context = self._new_load()
        load.write({"actual_freight_cost": 100.0, "actual_freight_currency_id": self.currency.id})
        load.action_record_actual_freight_cost()
        with self.assertRaises(UserError):
            load.action_record_actual_freight_cost()
        load.action_correct_actual_freight_cost(80.0, self.currency, "scale ticket corrected the cost")
        rows = self.env["plasticos.freight.calibration.observation"].search(
            [("load_id", "=", load.id)],
            order="observed_at desc, id desc",
        )
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0].supersedes_observation_id, rows[1])
        self.assertFalse(rows[1].supersedes_observation_id)
