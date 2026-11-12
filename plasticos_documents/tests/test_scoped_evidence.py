"""Export campaign S3: operation-scoped evidence on the one plasticos.document owner.

V08 operation evidence isolation and V09 legacy consumers. Each case names the
BRS rule it witnesses. Operation obligations are declared by a downstream owner
(Export); core Documents declares none, so these tests declare two for the case.
"""

import base64
import importlib.util
import itertools
import json
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from odoo import fields
from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.exceptions import AccessError, UserError
from odoo.modules.module import get_module_path
from odoo.tests.common import tagged

GATE = "export_gate_receipt"
PHOTOS = "export_loading_photos"
DECLARED = frozenset({GATE, PHOTOS})
_BYTES = itertools.count()


def _migration(name):
    path = Path(get_module_path("plasticos_documents")) / "migrations" / "19.0.2.1.18" / name
    spec = importlib.util.spec_from_file_location(f"plasticos_documents_s3_{name.replace('-', '_')}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@tagged("post_install", "-at_install", "documents", "scoped_evidence")
class TestScopedEvidence(PlasticosTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True, mail_notrack=True))
        parent = cls.env["res.partner"].create({"name": "Scoped Parent", "is_company": True})
        cls.supplier = cls.env["res.partner"].create(
            {"name": "Scoped Supplier", "is_company": True, "parent_id": parent.id, "supplier_rank": 1}
        )
        cls.buyer = cls.env["res.partner"].create(
            {"name": "Scoped Buyer", "is_company": True, "parent_id": parent.id, "customer_rank": 1}
        )
        cls.company_b = cls.env["res.company"].create({"name": "Scoped Company B"})
        internal = cls.env.ref("base.group_user")
        verifier = cls.env.ref("plasticos_documents.group_documents_user")
        manager = cls.env.ref("plasticos_documents.group_documents_manager")
        purchase = cls.env.ref("purchase.group_purchase_user")
        Users = cls.env["res.users"].with_context(no_reset_password=True)
        cls.verifier = Users.create(
            {
                "name": "Scoped Verifier",
                "login": "s3_scoped_verifier",
                "group_ids": [(6, 0, [internal.id, verifier.id, purchase.id])],
            }
        )
        cls.manager = Users.create(
            {
                "name": "Scoped Manager",
                "login": "s3_scoped_manager",
                "group_ids": [(6, 0, [internal.id, manager.id, purchase.id])],
            }
        )
        cls.internal = Users.create(
            {"name": "Scoped Internal", "login": "s3_scoped_internal", "group_ids": [(6, 0, [internal.id])]}
        )
        cls.foreign = Users.create(
            {
                "name": "Scoped Foreign",
                "login": "s3_scoped_foreign",
                "company_id": cls.company_b.id,
                "company_ids": [(6, 0, [cls.company_b.id])],
                "group_ids": [(6, 0, [internal.id])],
            }
        )
        Tag = cls.env["plasticos.document.tag"]
        cls.bol = Tag.search([("code", "=", "BOL")], limit=1)
        cls.scale = Tag.search([("code", "=", "SCALE")], limit=1)
        cls.photo = Tag.search([("code", "=", "PHOTO")], limit=1)
        if not (cls.bol and cls.scale and cls.photo):
            raise AssertionError("BLOCKED: BOL, SCALE or PHOTO tag is not installed")
        cls.uom = cls.env["uom.uom"].search([], limit=1)

    def setUp(self):
        super().setUp()
        self.patch(type(self.env["plasticos.document"]), "_scoped_obligation_kinds", lambda model: DECLARED)

    # ── fixtures ─────────────────────────────────────────────────────

    def _trade(self, name):
        order = self.env["sale.order"].create({"partner_id": self.buyer.id})
        tx = self.env["plasticos.transaction"].create(
            {
                "name": name,
                "supplier_id": self.supplier.id,
                "buyer_id": self.buyer.id,
                "sale_order_id": order.id,
                "quantity": 10,
            }
        )
        load = self.env["plasticos.load"].create({"sale_order_id": order.id})
        self.assertEqual(load.transaction_id, tx)
        self.assertEqual(load.company_id, order.company_id)
        return order, tx, load

    def _attachment(self, res_model="plasticos.document", res_id=0):
        return self.env["ir.attachment"].create(
            {
                "name": "scoped-original.pdf",
                "datas": base64.b64encode(f"scoped-original-{next(_BYTES)}".encode()),
                "res_model": res_model,
                "res_id": res_id,
            }
        )

    def _shell(self, tag, attachment=None):
        return self.env["plasticos.document"].create(
            {
                "name": tag.code,
                "tag_id": tag.id,
                "res_model": "documents.document",
                "res_id": 0,
                "attachment_id": (attachment or self._attachment()).id,
            }
        )

    def _scope(self, shell, subject, kind=GATE, revision="BKG-1/r1", coverage="container-1", **extra):
        return shell.with_user(self.verifier)._associate_scope(
            subject._name,
            subject.id,
            f"booking mail {revision}",
            obligation_kind=kind,
            operation_revision_key=revision,
            coverage_key=coverage,
            **extra,
        )

    def _verdict(self, subject, kind=GATE, revision="BKG-1/r1", company=None):
        return self.env["plasticos.document"].get_scoped_evidence_verdict(
            (company or self.env.company).id, subject._name, subject.id, kind, revision
        )

    def _only_rule(self, tag, invoice=True, close=True):
        self.env["plasticos.document.rule"].search([("res_model", "=", "plasticos.transaction")]).write(
            {"active": False}
        )
        return self.env["plasticos.document.rule"].create(
            {
                "name": f"scoped {tag.code}",
                "tag_id": tag.id,
                "res_model": "plasticos.transaction",
                "required_for_invoice": invoice,
                "required_for_close": close,
            }
        )

    # ── V08: isolation of independent obligations and revisions ─────

    def test_two_operation_revisions_on_one_original_stay_independent(self):
        """BRS-EXP-09-R008, BRS-EXP-03-R001: one original, two revisions, two decisions."""
        _order, _tx, load = self._trade("TX-S3-REV")
        attachment = self._attachment()
        first = self._scope(self._shell(self.bol, attachment), load, revision="BKG-1/r1")
        second = self._scope(self._shell(self.bol, attachment), load, revision="BKG-1/r2")
        self.assertNotEqual(first, second)
        self.assertEqual(first.attachment_id, second.attachment_id)
        self.assertEqual(first.source_revision, second.source_revision)
        self.assertNotEqual(first.operation_revision_key, second.operation_revision_key)
        first.with_user(self.verifier).action_verify()
        self.assertTrue(first.verified)
        self.assertFalse(second.verified)
        self.assertEqual(self._verdict(load, revision="BKG-1/r1"), {"status": "applied", "record_id": first.id})
        verdict = self._verdict(load, revision="BKG-1/r2")
        self.assertEqual(verdict["status"], "blocked")
        self.assertEqual(verdict["record_id"], second.id)
        self.assertEqual(self._verdict(load, kind=PHOTOS)["status"], "blocked")
        self.assertEqual(self._verdict(load, revision="BKG-1/r9")["status"], "stale")

    def test_replay_is_idempotent_and_a_contradictory_payload_is_refused(self):
        """BRS-EXP-11-R003, BRS-EXP-11-R001: no duplicate original, no silent collapse."""
        _order, _tx, load = self._trade("TX-S3-REPLAY")
        attachment = self._attachment()
        row = self._scope(self._shell(self.bol, attachment), load)
        again = self._scope(self._shell(self.bol, attachment), load)
        self.assertEqual(row, again)
        accepted = self.env["plasticos.document"].search(
            [("attachment_id", "=", attachment.id), ("association_state", "=", "accepted")]
        )
        self.assertEqual(accepted, row)
        with self.assertRaisesRegex(UserError, "different quantity"):
            self._scope(
                self._shell(self.bol, attachment),
                load,
                quantity_known=True,
                covered_quantity=5.0,
                evidence_uom_id=self.uom.id,
            )
        other_container = self._scope(self._shell(self.bol, attachment), load, coverage="Container-2 ")
        self.assertEqual(other_container.coverage_key, "container-2")
        self.assertNotEqual(other_container, row)

    def test_quantity_is_known_only_with_its_unit_and_never_inferred(self):
        """BRS-EXP-11-R008: physical weights are evidence candidates; unknown stays unknown."""
        _order, _tx, load = self._trade("TX-S3-QTY")
        with self.assertRaisesRegex(UserError, "unknown quantity"):
            self._scope(self._shell(self.scale), load, covered_quantity=40200.0)
        with self.assertRaisesRegex(UserError, "needs its unit"):
            self._scope(self._shell(self.scale), load, quantity_known=True, covered_quantity=40200.0)
        unknown = self._scope(self._shell(self.scale), load, coverage="ticket-1728952")
        self.assertFalse(unknown.quantity_known)
        self.assertEqual(unknown.covered_quantity, 0.0)
        self.assertFalse(unknown.evidence_uom_id)
        known = self._scope(
            self._shell(self.scale),
            load,
            coverage="ticket-1728953",
            quantity_known=True,
            covered_quantity=40200.0,
            evidence_uom_id=self.uom.id,
        )
        self.assertTrue(known.quantity_known)
        self.assertEqual(known.evidence_uom_id, self.uom)

    def test_undeclared_obligation_and_subject_fail_closed(self):
        """BRS-EXP-13-R008: an exact authoritative target, or nothing."""
        _order, tx, load = self._trade("TX-S3-UNKNOWN")
        with self.assertRaisesRegex(UserError, "not a declared evidence obligation"):
            self._scope(self._shell(self.bol), load, kind="export_vessel_departure")
        with self.assertRaisesRegex(UserError, "operation revision"):
            self._scope(self._shell(self.bol), load, revision="  ")
        with self.assertRaisesRegex(UserError, "not an exact evidence subject"):
            self._shell(self.bol).with_user(self.verifier)._associate_scope(
                "res.partner", self.buyer.id, "ref", obligation_kind=GATE, operation_revision_key="r1"
            )
        self.assertEqual(self._verdict(load, kind="export_vessel_departure")["status"], "not_available")
        self.assertEqual(self._verdict(load, kind="legacy")["status"], "not_available")
        self.assertEqual(self._verdict(load, revision="")["status"], "not_available")
        missing = self.env["plasticos.document"].get_scoped_evidence_verdict(
            self.env.company.id, "plasticos.load", 0, GATE, "r1"
        )
        self.assertEqual(missing["status"], "not_available")
        self.assertEqual(self._verdict(tx)["status"], "blocked")
        with patch.object(type(self.env["plasticos.document"]), "_scoped_obligation_kinds", lambda model: frozenset()):
            self.assertEqual(self._verdict(load)["status"], "not_available")

    def test_accepted_scope_is_immutable_whatever_the_grant(self):
        """BRS-EXP-09-R004: correction is a new reviewed row, never a rewrite."""
        _order, _tx, load = self._trade("TX-S3-IMMUTABLE")
        row = self._scope(self._shell(self.bol), load)
        for vals in (
            {"operation_revision_key": "BKG-1/r2"},
            {"coverage_key": "container-9"},
            {"obligation_kind": "legacy"},
            {"quantity_known": True, "evidence_uom_id": self.uom.id},
        ):
            with self.assertRaises(AccessError), self.env.cr.savepoint():
                row.with_user(self.manager)._association_write(vals)
            with self.assertRaises(AccessError), self.env.cr.savepoint():
                row.with_user(self.verifier).write(vals)
        with self.assertRaises(AccessError), self.env.cr.savepoint():
            self.env["plasticos.document"].with_user(self.verifier).create(
                {
                    "name": "forged",
                    "tag_id": self.bol.id,
                    "res_model": "plasticos.load",
                    "res_id": load.id,
                    "attachment_id": self._attachment().id,
                    "obligation_kind": GATE,
                }
            )
        self.assertEqual(row.operation_revision_key, "BKG-1/r1")
        self.assertEqual(row.obligation_kind, GATE)

    def test_currentness_expiry_supersession_and_replacement_clear_the_verdict(self):
        """V08 currentness; BRS-EXP-09-R008: only current verified evidence proves the obligation."""
        _order, _tx, load = self._trade("TX-S3-CURRENT")
        row = self._scope(self._shell(self.bol), load)
        row.write({"expiry_date": fields.Date.today() + timedelta(days=10)})
        row.with_user(self.verifier).action_verify()
        self.assertEqual(self._verdict(load)["status"], "applied")
        later = fields.Date.today() + timedelta(days=11)
        with patch.object(type(self.env["plasticos.document"]), "_evidence_today", return_value=later):
            self.assertEqual(self._verdict(load)["status"], "stale")
        self.assertEqual(self._verdict(load)["status"], "applied")
        actor, stamp = row.verified_by, row.verified_at
        replacement = self._scope(self._shell(self.bol), load, coverage="container-1-v2")
        row.with_user(self.verifier).action_supersede(replacement.id)
        # The superseded decision is history, not current proof; the replacement awaits verification.
        self.assertEqual(self._verdict(load)["status"], "stale")
        replacement.with_user(self.verifier).action_verify()
        self.assertEqual(self._verdict(load), {"status": "applied", "record_id": replacement.id})
        self.assertEqual((row.verified_by, row.verified_at), (actor, stamp))

        fresh = self._scope(self._shell(self.bol), load, revision="BKG-2/r1")
        fresh.with_user(self.verifier).action_verify()
        self.assertEqual(self._verdict(load, revision="BKG-2/r1")["status"], "applied")
        self.env["ir.attachment"].browse(fresh.attachment_id.id).write(
            {"datas": base64.b64encode(b"replaced-original-bytes")}
        )
        self.assertEqual(self._verdict(load, revision="BKG-2/r1")["status"], "stale")
        self.assertTrue(fresh.association_review_required)

    def test_conflicting_originals_for_one_coverage_are_ambiguous(self):
        """BRS-EXP-09-R004: two originals for the same exact scope abstain."""
        _order, _tx, load = self._trade("TX-S3-AMBIG")
        one = self._scope(self._shell(self.bol), load)
        two = self._scope(self._shell(self.bol), load)
        (one | two).with_user(self.verifier).action_verify()
        verdict = self._verdict(load)
        self.assertEqual(verdict["status"], "ambiguous")
        self.assertIn("container-1", verdict["reason"])
        pictures = self._scope(self._shell(self.photo), load, kind=PHOTOS, coverage="photo-1")
        others = self._scope(self._shell(self.photo), load, kind=PHOTOS, coverage="photo-2")
        (pictures | others).with_user(self.verifier).action_verify()
        self.assertEqual(self._verdict(load, kind=PHOTOS)["status"], "applied")

    def test_pending_photo_evidence_is_not_complete(self):
        """BRS-EXP-11-R009, BRS-EXP-11-R002: an accepted but unverified photo set stays pending."""
        _order, _tx, load = self._trade("TX-S3-PHOTO")
        row = self._scope(self._shell(self.photo), load, kind=PHOTOS, coverage="photo-link")
        verdict = self._verdict(load, kind=PHOTOS)
        self.assertEqual(verdict, {"status": "blocked", "record_id": row.id, "reason": "evidence awaits verification"})
        self.assertEqual(self._verdict(load, kind=GATE), {"status": "blocked", "reason": "evidence is missing"})

    def test_cross_company_isolation(self):
        """BRS-EXP-09-R003: exact company and subject, never another company's evidence."""
        _order, _tx, load = self._trade("TX-S3-COMPANY")
        row = self._scope(self._shell(self.bol), load)
        row.with_user(self.verifier).action_verify()
        self.assertEqual(row.subject_company_id, load.company_id)
        self.assertEqual(self._verdict(load, company=self.company_b)["status"], "blocked")
        Document = self.env["plasticos.document"]
        self.assertFalse(Document.with_user(self.foreign).search([("id", "=", row.id)]))
        self.assertEqual(Document.with_user(self.internal).search([("id", "=", row.id)]), row)
        legacy = self._shell(self.bol)
        self.assertEqual(Document.with_user(self.foreign).search([("id", "=", legacy.id)]), legacy)
        with self.assertRaises(AccessError), self.env.cr.savepoint():
            row.with_user(self.foreign).read(["name"])

    def test_one_business_verifier_decides_each_row(self):
        """BRS-EXP-03-R003: the scope row is decided only through the Documents commands."""
        _order, _tx, load = self._trade("TX-S3-VERIFIER")
        row = self._scope(self._shell(self.bol), load)
        with self.assertRaises(AccessError), self.env.cr.savepoint():
            row.with_user(self.internal).action_verify()
        with self.assertRaises(AccessError), self.env.cr.savepoint():
            row.with_user(self.verifier).write({"verified": True})
        with self.assertRaises(AccessError), self.env.cr.savepoint():
            row.with_user(self.verifier).action_override("no")
        row.with_user(self.manager).action_override("export desk accepted the gate receipt")
        self.assertEqual(row.override_by, self.manager)
        self.assertEqual(self._verdict(load)["status"], "applied")

    def test_form_command_associates_the_draft_scope(self):
        """RP-05-E012: the owner form submits the scope through the same helper."""
        _order, _tx, load = self._trade("TX-S3-FORM")
        shell = self._shell(self.bol)
        shell.write(
            {
                "association_subject_model": "plasticos.load",
                "association_subject_id": load.id,
                "association_source_reference": "form booking mail",
                "association_obligation_kind": GATE,
                "association_operation_revision_key": "BKG-7/r1",
                "association_coverage_key": "container-7",
            }
        )
        row = shell.with_user(self.verifier).action_associate_from_form()
        self.assertEqual(row.obligation_kind, GATE)
        self.assertEqual(row.operation_revision_key, "BKG-7/r1")
        self.assertEqual(row.association_state, "accepted")

    def test_scoped_changes_reach_the_native_invalidation_hook(self):
        """B11: scoped rows invalidate the native projection through the base hook."""
        _order, _tx, load = self._trade("TX-S3-HOOK")
        calls = []
        original = type(self.env["plasticos.document"])._invalidate_native_projection

        def record(model):
            calls.append(set(model.ids))
            return original(model)

        with patch.object(type(self.env["plasticos.document"]), "_invalidate_native_projection", record):
            row = self._scope(self._shell(self.bol), load)
            self.assertTrue(any(row.id in ids for ids in calls))
            calls.clear()
            row.with_user(self.verifier).action_verify()
            self.assertTrue(any(row.id in ids for ids in calls))

    # ── V09: legacy consumers and merged protections ─────────────────

    def test_operation_row_never_reaches_legacy_compliance(self):
        """V09, BRS-EXP-09-R002: an operation BOL does not satisfy or alter transaction compliance."""
        _order, tx, _load = self._trade("TX-S3-LEGACY")
        self._only_rule(self.bol)
        service = self.env["plasticos.compliance.service"]
        operation = self._scope(self._shell(self.bol), tx)
        operation.with_user(self.verifier).action_verify()
        self.assertFalse(service.is_compliant("plasticos.transaction", tx.id, purpose="invoice"))
        self.assertFalse(service.is_compliant("plasticos.transaction", tx.id))
        tx.invalidate_recordset()
        self.assertEqual(tx.compliance_status, "missing")
        legacy = (
            self._shell(self.bol)
            .with_user(self.verifier)
            .action_associate("plasticos.transaction", tx.id, "legacy bol")
        )
        self.assertEqual(legacy.obligation_kind, "legacy")
        legacy.with_user(self.verifier).action_verify()
        self.assertTrue(service.is_compliant("plasticos.transaction", tx.id, purpose="invoice"))
        tx.invalidate_recordset()
        self.assertEqual(tx.compliance_status, "compliant")
        self.assertEqual(self._verdict(tx)["status"], "applied")

    def test_invoice_posting_gate_blocks_on_missing_legacy_not_on_operation_row(self):
        """B13: account.move.action_post through _missing_invoice_documents stays legacy-only."""
        order, tx, _load = self._trade("TX-S3-INVOICE")
        order.write({"transaction_id": tx.id})
        self._only_rule(self.bol, invoice=True, close=False)

        def invoice():
            return self.env["account.move"].create(
                {
                    "move_type": "out_invoice",
                    "partner_id": self.buyer.id,
                    "invoice_origin": order.name,
                    "invoice_line_ids": [(0, 0, {"name": "Line", "quantity": 1, "price_unit": 50.0})],
                }
            )

        blocked = invoice()
        with self.assertRaisesRegex(UserError, "Missing required documents for invoice posting"):
            blocked.action_post()
        operation = self._scope(self._shell(self.bol), tx)
        operation.with_user(self.verifier).action_verify()
        with self.assertRaisesRegex(UserError, "Missing required documents for invoice posting"):
            blocked.action_post()
        self.assertEqual(blocked.state, "draft")
        legacy = (
            self._shell(self.bol)
            .with_user(self.verifier)
            .action_associate("plasticos.transaction", tx.id, "legacy bol")
        )
        legacy.with_user(self.verifier).action_verify()
        posted = invoice()
        posted.action_post()
        self.assertEqual(posted.state, "posted")
        # The operation row on the same transaction does not block the legacy-proven gate.
        self.assertTrue(operation._currently_eligible())

    def test_scale_ticket_clock_reads_actual_events_and_legacy_rows(self):
        """RP-05-E004/B3/B14: actual clocks, legacy scale ticket, thresholds unchanged."""
        from odoo.addons.plasticos_logistics.models.load import (
            _ACTUAL_EVENT_INTERNAL_WRITE,
            _ACTUAL_EVENT_INTERNAL_WRITE_TOKEN,
            _FREIGHT_INTERNAL_WRITE,
            _FREIGHT_INTERNAL_WRITE_TOKEN,
        )

        rule = self.env.ref("plasticos_documents.rule_scale_ticket_carrier")
        self.assertEqual((rule.overdue_business_days, rule.escalation_business_days), (2, 7))
        _order, tx, load = self._trade("TX-S3-SCALE")
        tx.with_context(bypass_state_guard=True).write({"state": "delivered"})
        long_ago = fields.Datetime.now() - timedelta(days=30)
        load.with_context(**{_FREIGHT_INTERNAL_WRITE: _FREIGHT_INTERNAL_WRITE_TOKEN}).write(
            {"state": "delivered", "delivered_at": long_ago, "dispatched_at": long_ago}
        )
        params = self.env["ir.config_parameter"]
        model = self.env["plasticos.transaction"].with_context(scale_ticket_batch_size=10)

        def run():
            params.set_param("plasticos_documents.scale_ticket_retry_ids", "")
            params.set_param("plasticos_documents.scale_ticket_scan_cursor", str(load.id - 1))
            with patch.object(type(model), "_get_logistics_manager", lambda self, group: self.env.user):
                model.cron_check_scale_tickets()

        run()
        self.assertFalse(load.scale_ticket_reminder_sent, "a workflow timestamp is not an actual delivery")
        self.assertFalse(load.scale_ticket_escalated)
        operation = self._scope(self._shell(self.scale), load, coverage="ticket-1")
        operation.with_user(self.verifier).action_verify()
        load.with_context(**{_ACTUAL_EVENT_INTERNAL_WRITE: _ACTUAL_EVENT_INTERNAL_WRITE_TOKEN}).write(
            {"actual_pickup_at": long_ago, "actual_delivery_at": long_ago}
        )
        run()
        self.assertTrue(load.scale_ticket_reminder_sent, "an operation row is not the legacy scale ticket")
        self.assertTrue(load.scale_ticket_escalated)
        summary = f"ESCALATION: Missing scale ticket on {load.name}"
        count = self.env["mail.activity"].search_count(
            [("res_model", "=", "plasticos.load"), ("res_id", "=", load.id), ("summary", "=", summary)]
        )
        run()
        self.assertEqual(
            self.env["mail.activity"].search_count(
                [("res_model", "=", "plasticos.load"), ("res_id", "=", load.id), ("summary", "=", summary)]
            ),
            count,
        )

    def test_load_without_actual_time_leaves_the_clock_unknown(self):
        """C02-REAUTH-2 / BRS-07-R051: no actual event means no clock, no reminder, no escalation."""
        from odoo.addons.plasticos_logistics.models.load import (
            _FREIGHT_INTERNAL_WRITE,
            _FREIGHT_INTERNAL_WRITE_TOKEN,
        )

        _order, tx, load = self._trade("TX-S3-UNKNOWN-CLOCK")
        tx.with_context(bypass_state_guard=True).write({"state": "delivered"})
        long_ago = fields.Datetime.now() - timedelta(days=30)
        load.with_context(**{_FREIGHT_INTERNAL_WRITE: _FREIGHT_INTERNAL_WRITE_TOKEN}).write(
            {"state": "delivered", "delivered_at": long_ago, "dispatched_at": long_ago}
        )
        self.assertFalse(load.actual_pickup_at)
        self.assertFalse(load.actual_delivery_at)
        model = self.env["plasticos.transaction"]
        self.assertEqual(model._scale_ticket_clock_dates(load), (None, None))
        notes = len(load.message_ids)
        params = self.env["ir.config_parameter"]
        params.set_param("plasticos_documents.scale_ticket_retry_ids", "")
        params.set_param("plasticos_documents.scale_ticket_scan_cursor", str(load.id - 1))
        with patch.object(type(model), "_get_logistics_manager", lambda self, group: self.env.user):
            model.with_context(scale_ticket_batch_size=10).cron_check_scale_tickets()
        self.assertFalse(load.scale_ticket_reminder_sent)
        self.assertFalse(load.scale_ticket_escalated)
        self.assertEqual(len(load.message_ids), notes)
        self.assertFalse(
            self.env["mail.activity"].search_count([("res_model", "=", "plasticos.load"), ("res_id", "=", load.id)])
        )

    def test_release_guard_withholds_new_instruction_but_records_actual_events(self):
        """RP-05-E029, BRS-EXP-03-R006: stale scoped evidence withholds release, not the record of what happened."""
        _order, _tx, load = self._trade("TX-S3-RELEASE")
        Load = self.env["plasticos.load"]
        self.assertEqual(Load.assert_can_release_physical_operation(load.id, "dispatch")["status"], "applied")
        pending = self._scope(self._shell(self.bol), load)
        self.assertEqual(Load.assert_can_release_physical_operation(load.id, "dispatch")["status"], "applied")
        pending.write({"expiry_date": fields.Date.today() + timedelta(days=1)})
        pending.with_user(self.verifier).action_verify()
        self.assertEqual(Load.assert_can_release_physical_operation(load.id, "dispatch")["status"], "applied")
        later = fields.Date.today() + timedelta(days=5)
        with patch.object(type(self.env["plasticos.document"]), "_evidence_today", return_value=later):
            verdict = Load.assert_can_release_physical_operation(load.id, "dispatch")
            self.assertEqual(verdict["status"], "blocked")
            self.assertIn("no longer current", verdict["reason"])
            evidence = self._attachment("plasticos.load", load.id)
            picked = fields.Datetime.now() - timedelta(hours=2)
            result = load.action_record_actual_event("pickup", picked, evidence)
        self.assertEqual(result["status"], "applied")
        self.assertEqual(load.actual_pickup_at, picked.replace(microsecond=0))

    def test_ordinary_user_cannot_unlink_evidence(self):
        """RP-05-E010: unlink needs the Documents manager."""
        row = self._shell(self.bol)
        with self.assertRaises(AccessError), self.env.cr.savepoint():
            row.with_user(self.internal).unlink()
        with self.assertRaises(AccessError), self.env.cr.savepoint():
            row.with_user(self.verifier).unlink()
        self.assertTrue(row.exists())
        row.with_user(self.manager).unlink()
        self.assertFalse(row.exists())

    # ── Migration 19.0.2.1.18 ────────────────────────────────────────

    def test_migration_refuses_an_unsupported_baseline(self):
        """RP-07-E094: only the reconciled 19.0.2.1.17 baseline upgrades."""
        pre = _migration("pre-migrate.py")
        with self.assertRaisesRegex(RuntimeError, "upgrades only from 19.0.2.1.17"):
            pre.migrate(self.env.cr, "19.0.2.1.16")
        pre.migrate(self.env.cr, "19.0.2.1.17")
        pre.migrate(self.env.cr, False)

    def test_migration_classifies_legacy_without_changing_provenance(self):
        """RP-07-E095: same accepted actor, time and digest; idempotent rerun."""
        _order, tx, _load = self._trade("TX-S3-MIGRATE")
        row = self._shell(self.bol).with_user(self.verifier).action_associate("plasticos.transaction", tx.id, "m")
        row.with_user(self.verifier).action_verify()
        self.env.flush_all()
        pre = _migration("pre-migrate.py")
        post = _migration("post-migrate.py")
        cr = self.env.cr
        cr.execute(pre.CENSUS_SQL)
        total, accepted, decided, digest = cr.fetchone()
        self.env["ir.config_parameter"].set_param(
            pre.CENSUS_KEY,
            json.dumps([total, accepted, decided, digest]),
        )
        self.env.flush_all()
        post.migrate(cr, "19.0.2.1.17")
        cr.execute("SELECT 1 FROM ir_config_parameter WHERE key = %s", (pre.CENSUS_KEY,))
        self.assertFalse(cr.fetchone())
        post.migrate(cr, "19.0.2.1.17")
        cr.execute(pre.CENSUS_SQL)
        self.assertEqual(cr.fetchone(), (total, accepted, decided, digest))
        row.invalidate_recordset()
        self.assertEqual(row.obligation_kind, "legacy")
        self.assertFalse(row.operation_revision_key)
        self.assertFalse(row.quantity_known)
