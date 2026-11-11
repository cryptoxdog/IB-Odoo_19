"""V5 — nullability and partial uniqueness keep historical rows visible and invent no lineage.

* a historical match run / result / offer with an intake and no opportunity
  stays readable and unchanged;
* a lot result with no intake is allowed;
* one native opportunity per source intake, while manual lots on one partner
  and profile are never collapsed;
* one unsent offer per reviewed result, while historical offers without a
  result are unaffected.
"""

from __future__ import annotations

import uuid

from psycopg2.errors import UniqueViolation

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.addons.plasticos_matching.models.match_run import RECEIPT_WRITE_CONTEXT
from odoo.addons.plasticos_offer.tests.test_manual_send import send_offer_email
from odoo.tests.common import tagged
from odoo.tools import mute_logger


@tagged("post_install", "-at_install", "plasticos", "crm_bridge", "opportunity", "migration")
class TestOpportunityMigration(PlasticosTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._skip_if_model_missing("plasticos.opportunity.approval", "plasticos.match.run", "plasticos.offer")
        cls.Lead = cls.env["crm.lead"]
        cls.Run = cls.env["plasticos.match.run"].with_context(**{RECEIPT_WRITE_CONTEXT: True})
        cls.Result = cls.env["plasticos.match.result"]
        cls.Offer = cls.env["plasticos.offer"]
        cls.supplier = cls._create_partner("Historical Supplier", supplier_rank=1)
        cls.buyer = cls._create_partner("Historical Buyer", customer_rank=1)
        cls.polymer = cls._get_or_create_polymer()
        cls.form = cls._get_or_create_form()
        cls.profile = cls.env["plasticos.material.profile"].create(
            {"partner_id": cls.supplier.id, "polymer_id": cls.polymer.id, "form_id": cls.form.id}
        )
        cls.intake = cls._create_intake(partner=cls.supplier, polymer=cls.polymer, form=cls.form)

    def _historical_run(self, **extra):
        vals = {
            "intake_id": self.intake.id,
            "supplier_partner_id": self.supplier.id,
            "state": "ok",
            "operation_id": f"odoo:matching:test:plasticos.match.run:hist-{uuid.uuid4().hex[:12]}",
            "gate_response_digest": "digest-hist",
        }
        vals.update(extra)
        return self.Run.create(vals)

    def test_historical_intake_run_result_and_offer_stay_readable_without_lineage(self):
        run = self._historical_run()
        result = self.Result.sudo().create(
            {
                "intake_id": self.intake.id,
                "buyer_partner_id": self.buyer.id,
                "score": 70.0,
                "run_id": run.operation_id,
                "match_run_id": run.id,
            }
        )
        offer = self.Offer.create(
            {"intake_id": self.intake.id, "supplier_id": self.supplier.id, "buyer_id": self.buyer.id}
        )
        self.env.invalidate_all()
        self.assertFalse(run.opportunity_id)
        self.assertFalse(run.approval_id)
        self.assertEqual(run.intake_id, self.intake)
        self.assertIn(self.intake.name or "", result.display_name)
        self.assertFalse(offer.match_result_id)
        self.assertEqual(self.Run.search([("opportunity_id", "=", False), ("id", "=", run.id)]), run)

    def test_lot_result_without_intake_is_allowed(self):
        run = self._historical_run(intake_id=False)
        result = self.Result.sudo().create(
            {
                "buyer_partner_id": self.buyer.id,
                "score": 80.0,
                "run_id": run.operation_id,
                "match_run_id": run.id,
            }
        )
        self.assertFalse(result.intake_id)
        self.assertFalse(result.intake_polymer)
        self.assertIn(self.supplier.name, result.display_name)

    def test_one_result_per_buyer_per_gate_operation(self):
        run = self._historical_run(intake_id=False)
        self.Result.sudo().create(
            {"buyer_partner_id": self.buyer.id, "score": 80.0, "run_id": run.operation_id, "match_run_id": run.id}
        )
        with mute_logger("odoo.sql_db"), self.assertRaises(UniqueViolation):
            self.Result.sudo().create(
                {"buyer_partner_id": self.buyer.id, "score": 81.0, "run_id": run.operation_id, "match_run_id": run.id}
            )

    def test_one_opportunity_per_source_intake_but_manual_lots_are_not_collapsed(self):
        self.Lead.create({"name": "First", "type": "opportunity", "source_intake_id": self.intake.id})
        with mute_logger("odoo.sql_db"), self.assertRaises(UniqueViolation):
            self.Lead.create({"name": "Second", "type": "opportunity", "source_intake_id": self.intake.id})
        manual_one = self.Lead.create(
            {
                "name": "Manual 1",
                "type": "opportunity",
                "partner_id": self.supplier.id,
                "material_profile_id": self.profile.id,
            }
        )
        manual_two = self.Lead.create(
            {
                "name": "Manual 2",
                "type": "opportunity",
                "partner_id": self.supplier.id,
                "material_profile_id": self.profile.id,
            }
        )
        lot_one = manual_one.action_approve_lot()
        lot_two = manual_two.action_approve_lot()
        lot_three = manual_two.action_approve_lot()
        self.assertEqual(len(lot_one | lot_two | lot_three), 3)
        self.assertEqual(lot_two.snapshot_digest, lot_three.snapshot_digest, "same frozen material, distinct lots")

    def test_one_accepted_offer_per_opportunity_is_a_database_invariant(self):
        opportunity = self.Lead.create(
            {
                "name": "Winner Opp",
                "type": "opportunity",
                "partner_id": self.supplier.id,
                "material_profile_id": self.profile.id,
            }
        )
        lot = opportunity.action_approve_lot()
        run = self._historical_run(intake_id=False, opportunity_id=opportunity.id, approval_id=lot.id)
        other_buyer = self._create_partner("Historical Buyer Two", customer_rank=1)
        results = self.Result.sudo().create(
            [
                {"buyer_partner_id": buyer.id, "score": 80.0, "run_id": run.operation_id, "match_run_id": run.id}
                for buyer in (self.buyer, other_buyer)
            ]
        )
        offers = self.Offer.create(
            [
                {
                    "supplier_id": self.supplier.id,
                    "buyer_id": result.buyer_partner_id.id,
                    "match_result_id": result.id,
                    "price_per_lb": 0.12,
                    "quantity_lbs": 40000,
                }
                for result in results
            ]
        )
        self.assertEqual(set(offers.mapped("opportunity_id").ids), {opportunity.id})
        # Both offers are really sent first: Accepted is reachable only from Sent.
        send_offer_email(offers)
        # Bypass the readable pre-check on purpose: the index must hold on its own.
        offers[0].write({"state": "accepted"})
        with mute_logger("odoo.sql_db"), self.assertRaises(UniqueViolation):
            offers[1].write({"state": "accepted"})
            offers.flush_recordset()

    def test_one_offer_per_reviewed_result_but_historical_offers_unaffected(self):
        run = self._historical_run(intake_id=False)
        result = self.Result.sudo().create(
            {"buyer_partner_id": self.buyer.id, "score": 80.0, "run_id": run.operation_id, "match_run_id": run.id}
        )
        base = {"supplier_id": self.supplier.id, "buyer_id": self.buyer.id}
        self.Offer.create({**base, "match_result_id": result.id})
        with mute_logger("odoo.sql_db"), self.assertRaises(UniqueViolation):
            self.Offer.create({**base, "match_result_id": result.id})
        legacy = self.Offer.create({**base, "intake_id": self.intake.id}) | self.Offer.create(
            {**base, "intake_id": self.intake.id}
        )
        self.assertEqual(len(legacy), 2)
