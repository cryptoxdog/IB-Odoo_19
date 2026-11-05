"""PR #322 final gate: trusted clock, read-only compliance, midnight projection.

G20-G28 stay on the existing association, verification, native-search, and
invoice tests. This module closes the clock, read-purity, and cron seams.
"""

import base64
from datetime import timedelta
from unittest.mock import patch

from odoo import fields
from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.exceptions import UserError
from odoo.tests.common import tagged

_FORGED_PAST = "2000-01-01"
_FORGED_FUTURE = "2999-12-31"


@tagged("post_install", "-at_install", "documents", "pr322", "expiry_final")
class TestExpiryFinalGate(PlasticosTestCase):
    """Server date, pure reads, and the existing 00:05 midnight projection."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create(
            {"name": "Expiry Gate Partner", "is_company": True, "customer_rank": 1, "supplier_rank": 1}
        )
        internal = cls.env.ref("base.group_user")
        verifier = cls.env.ref("plasticos_documents.group_documents_user")
        manager = cls.env.ref("plasticos_documents.group_documents_manager")
        purchase = cls.env.ref("purchase.group_purchase_user")
        cls.verifier = cls.env["res.users"].create(
            {
                "name": "Expiry Gate Verifier",
                "login": "pr322_expiry_gate_verifier",
                "group_ids": [(6, 0, [internal.id, verifier.id, purchase.id])],
            }
        )
        cls.manager = cls.env["res.users"].create(
            {
                "name": "Expiry Gate Manager",
                "login": "pr322_expiry_gate_manager",
                "group_ids": [(6, 0, [internal.id, manager.id, purchase.id])],
            }
        )
        cls.bol = cls.env["plasticos.document.tag"].search([("code", "=", "BOL")], limit=1)
        cls.receiving = cls.env["plasticos.document.tag"].search([("code", "=", "RECEIVING")], limit=1)
        if not cls.bol or not cls.receiving:
            raise AssertionError("BLOCKED: BOL or RECEIVING tag is not installed")

    def _clock(self, day):
        return patch.object(type(self.env["plasticos.document"]), "_evidence_today", return_value=day)

    def _attachment(self):
        return self.env["ir.attachment"].create(
            {
                "name": "expiry-gate.txt",
                "datas": base64.b64encode(b"expiry-gate"),
                "res_model": "plasticos.document",
                "res_id": 0,
            }
        )

    def _transaction(self, quantity=10):
        return self.env["plasticos.transaction"].create(
            {"supplier_id": self.partner.id, "buyer_id": self.partner.id, "quantity": quantity}
        )

    def _only_rule(self, tag):
        self.env["plasticos.document.rule"].search([("res_model", "=", "plasticos.transaction")]).write(
            {"active": False}
        )
        return self.env["plasticos.document.rule"].create(
            {
                "name": f"expiry gate {tag.code}",
                "tag_id": tag.id,
                "res_model": "plasticos.transaction",
                "required_for_invoice": True,
                "required_for_close": True,
            }
        )

    def _accepted(self, tag, transaction, quantity, expiry):
        shell = self.env["plasticos.document"].create(
            {
                "name": tag.code,
                "tag_id": tag.id,
                "res_model": "documents.document",
                "res_id": 0,
                "attachment_id": self._attachment().id,
                "expiry_date": expiry,
            }
        )
        return shell.with_user(self.verifier).action_associate(
            "plasticos.transaction",
            transaction.id,
            source_reference=f"expiry-{tag.code}-{quantity}",
            covered_quantity=quantity,
        )

    def _invoice(self, transaction):
        sale = self.env["sale.order"].create({"partner_id": self.partner.id, "transaction_id": transaction.id})
        return self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner.id,
                "invoice_origin": sale.name,
                "invoice_date": "2026-10-28",
                "invoice_line_ids": [(0, 0, {"name": "Buyer", "quantity": 1, "price_unit": 10.0})],
            }
        )

    def _status(self, transaction):
        self.env.flush_all()
        self.env.cr.execute(
            "SELECT compliance_status FROM plasticos_transaction WHERE id = %s",
            (transaction.id,),
        )
        return self.env.cr.fetchone()[0]

    def _forged(self, record):
        return record.with_context(
            plasticos_documents_today=_FORGED_PAST,
            tz="Pacific/Honolulu",
            allowed_company_ids=[self.env.company.id],
        )

    def test_forged_context_cannot_move_the_evidence_clock(self):
        """G01, G02, G05, G07. Context past, future, and timezone do not decide expiry."""
        tx = self._transaction()
        self._only_rule(self.bol)
        today = fields.Date.today()
        row = self._accepted(self.bol, tx, 0, today)
        row.with_user(self.verifier).action_verify()
        actor = row.verified_by
        stamp = row.verified_at
        service = self.env["plasticos.compliance.service"]
        forged_past = self._forged(row)
        forged_future = row.with_context(plasticos_documents_today=_FORGED_FUTURE, tz="Pacific/Kiritimati")
        self.assertEqual(forged_past._evidence_today(), today)
        self.assertEqual(forged_future._evidence_today(), fields.Date.today())
        self.assertTrue(forged_past._currently_eligible())
        self.assertTrue(forged_future._currently_eligible())
        self.assertTrue(self._forged(service).is_compliant("plasticos.transaction", tx.id, purpose="invoice"))
        next_day = today + timedelta(days=1)
        with self._clock(next_day):
            self.assertFalse(self._forged(row)._currently_eligible())
            self.assertFalse(service.is_compliant("plasticos.transaction", tx.id, purpose="close"))
            self.assertEqual(row.verified_by, actor)
            self.assertEqual(row.verified_at, stamp)
            self.assertTrue(row.verified)

    def test_action_post_rejects_expired_receiving_when_context_names_an_earlier_day(self):
        """G03, G06, G18. Live post uses the server date and leaves the draft and the decision."""
        tx = self._transaction(quantity=10)
        self._only_rule(self.receiving)
        today = fields.Date.today()
        row = self._accepted(self.receiving, tx, 10, today)
        row.with_user(self.verifier).action_verify()
        actor = row.verified_by
        stamp = row.verified_at
        digest = row.evidence_digest
        invoice = self._invoice(tx)
        self.assertEqual(self._status(tx), "compliant")
        later = today + timedelta(days=1)
        with self._clock(later):
            self.assertEqual(self._status(tx), "compliant")
            with self.assertRaisesRegex(UserError, "Missing required documents"):
                self._forged(invoice).action_post()
            self.assertEqual(invoice.state, "draft")
            self.assertEqual(row.verified_by, actor)
            self.assertEqual(row.verified_at, stamp)
            self.assertEqual(row.evidence_digest, digest)
            self.assertTrue(row.verified)
            self.assertFalse(row.override)

    def test_verify_and_override_ignore_a_forged_earlier_date(self):
        """G04. An expired original cannot be accepted by sending yesterday in context."""
        tx = self._transaction()
        self._only_rule(self.bol)
        today = fields.Date.today()
        row = self._accepted(self.bol, tx, 0, today)
        with self._clock(today + timedelta(days=1)):
            forged = self._forged(row)
            with self.assertRaisesRegex(UserError, "UNRESOLVED"):
                forged.with_user(self.verifier).action_verify()
            with self.assertRaisesRegex(UserError, "UNRESOLVED"):
                forged.with_user(self.manager).action_override(reason="forged earlier day")
        self.assertFalse(row.verified)
        self.assertFalse(row.override)
        self.assertFalse(row.override_reason)

    def test_compliance_reads_do_not_store_or_post(self):
        """G08, G09, G10, G11, G19. Queries after a flush do not recompute or update."""
        tx = self._transaction()
        self._only_rule(self.bol)
        row = self._accepted(self.bol, tx, 0, fields.Date.today() + timedelta(days=5))
        row.with_user(self.verifier).action_verify()
        invoice = self._invoice(tx)
        service = self.env["plasticos.compliance.service"]
        self.env.flush_all()
        updates = []
        cursor = self.env.cr
        real_execute = cursor.execute

        def watching(query, params=None, log_exceptions=True):
            text = query.code if hasattr(query, "code") else str(query)
            folded = text.upper()
            if "UPDATE" in folded and "PLASTICOS_" in folded:
                updates.append(text)
            return real_execute(query, params, log_exceptions=log_exceptions)

        mail_before = self.env["mail.mail"].search_count([])
        transaction_model = type(tx)
        with (
            patch.object(cursor, "execute", watching),
            patch.object(transaction_model, "_compute_compliance") as compliance_compute,
            patch.object(type(invoice), "action_post", side_effect=AssertionError("post")),
            patch.object(
                type(self.env["plasticos.midnight.recompute"]),
                "_cron_midnight_recompute",
                side_effect=AssertionError("cron"),
            ),
        ):
            service.get_missing_documents("plasticos.transaction", tx.id, purpose="invoice")
            self.assertTrue(service.is_compliant("plasticos.transaction", tx.id, purpose="invoice"))
            found = self.env["plasticos.transaction"].search(
                [("id", "=", tx.id), ("compliance_status", "=", "compliant")]
            )
            counted = self.env["plasticos.transaction"].search_count([("compliance_status", "=", "compliant")])
            tx.read(["compliance_status"])
            self.env["plasticos.transaction"].read_group(
                [("id", "=", tx.id)],
                ["compliance_status"],
                ["compliance_status"],
            )
        self.assertEqual(found, tx)
        self.assertGreaterEqual(counted, 1)
        compliance_compute.assert_not_called()
        self.assertFalse(updates)
        self.assertEqual(self.env["mail.mail"].search_count([]), mail_before)

    def test_exact_day_rows_do_not_starve_past_expiry_or_inactive_rows(self):
        """G13, G14. Today stays current. More than one batch of real expiries still finishes."""
        horizon = fields.Date.today() + timedelta(days=30)
        attachment = self.env["ir.attachment"].create({"name": "batch.txt", "raw": b"batch"})
        today_rows = self.env["plasticos.document"].create(
            [
                {
                    "name": f"exact-day-{index}",
                    "tag_id": self.bol.id,
                    "res_model": "res.partner",
                    "res_id": self.partner.id,
                    "attachment_id": attachment.id,
                    "expiry_date": horizon,
                }
                for index in range(1000)
            ]
        )
        expired_rows = self.env["plasticos.document"].create(
            [
                {
                    "name": f"past-expiry-{index}",
                    "tag_id": self.bol.id,
                    "res_model": "res.partner",
                    "res_id": self.partner.id,
                    "attachment_id": attachment.id,
                    "expiry_date": horizon - timedelta(days=1),
                }
                for index in range(1001)
            ]
        )
        inactive = self.env["plasticos.document"].create(
            {
                "name": "inactive-past",
                "tag_id": self.bol.id,
                "res_model": "res.partner",
                "res_id": self.partner.id,
                "attachment_id": attachment.id,
                "expiry_date": horizon - timedelta(days=2),
                "active": False,
            }
        )
        self.assertFalse(expired_rows[0].is_expired)
        self.assertFalse(inactive.is_expired)
        document_model = type(expired_rows)
        real_compute = document_model._compute_is_expired
        batches = []

        def _compute_is_expired(records):
            batches.append(list(records.ids))
            return real_compute(records)

        with self._clock(horizon), patch.object(document_model, "_compute_is_expired", _compute_is_expired):
            self.env["plasticos.midnight.recompute"]._recompute_document_expiry()
        recomputed = {row_id for batch in batches for row_id in batch}
        self.assertFalse(set(today_rows.ids) & recomputed)
        self.assertTrue(set(expired_rows.ids) <= recomputed)
        self.assertIn(inactive.id, recomputed)
        self.assertTrue(all(len(batch) <= 1000 for batch in batches))
        self.assertGreater(len(batches), 1)
        self.assertTrue(all(row.is_expired for row in expired_rows))
        self.assertTrue(inactive.is_expired)
        self.assertFalse(any(row.is_expired for row in today_rows))

    def test_cron_projects_only_the_affected_transaction_and_is_idempotent(self):
        """G12, G15, G16, G17, G26. The 00:05 job stores the new day and does not post."""
        today = fields.Date.today()
        self._only_rule(self.bol)
        shared = self._transaction()
        other = self._transaction()
        sole_only = self._transaction()
        shared_expired = self._accepted(self.bol, shared, 0, today + timedelta(days=1))
        shared_current = self._accepted(self.bol, shared, 0, today + timedelta(days=10))
        untouched = self._accepted(self.bol, other, 0, today + timedelta(days=10))
        only = self._accepted(self.bol, sole_only, 0, today + timedelta(days=1))
        for row in (shared_expired, shared_current, untouched, only):
            row.with_user(self.verifier).action_verify()
        invoice = self._invoice(shared)
        service = self.env["plasticos.midnight.recompute"]
        compliance = self.env["plasticos.compliance.service"]
        mail_before = self.env["mail.mail"].search_count([])
        later = today + timedelta(days=2)
        real_claims = type(service)._recompute_claim_time_fields
        claims_called = []

        def _recompute_claim_time_fields(records):
            claims_called.append(True)
            return real_claims(records)

        with (
            self._clock(later),
            patch.object(type(service), "_recompute_claim_time_fields", _recompute_claim_time_fields),
            patch.object(type(invoice), "action_post", side_effect=AssertionError("post")),
        ):
            self.assertTrue(compliance.is_compliant("plasticos.transaction", shared.id))
            self.assertFalse(compliance.is_compliant("plasticos.transaction", sole_only.id))
            self.assertEqual(self._status(sole_only), "compliant")
            stamp = only.verified_at
            service._cron_midnight_recompute()
            self.assertEqual(self._status(shared), "compliant")
            self.assertEqual(self._status(sole_only), "missing")
            self.assertEqual(self._status(other), "compliant")
            self.assertFalse(shared_expired._currently_eligible())
            self.assertTrue(shared_current._currently_eligible())
            self.assertEqual(only.verified_by, self.verifier)
            service._recompute_document_expiry()
            self.assertEqual(self._status(sole_only), "missing")
            self.assertEqual(only.verified_at, stamp)
        self.assertTrue(claims_called)
        self.assertEqual(invoice.state, "draft")
        self.assertEqual(self.env["mail.mail"].search_count([]), mail_before)
        self.assertEqual(untouched.verified_by, self.verifier)
