"""Claim reference uniqueness is one query per create or write batch and keeps its messages."""

import uuid
from unittest.mock import patch

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.exceptions import ValidationError
from odoo.tests import tagged


def _counting_search(model_cls, calls):
    real = model_cls.search

    def search(self, *args, **kwargs):
        calls.append(args[0] if args else kwargs.get("domain"))
        return real(self, *args, **kwargs)

    return patch.object(model_cls, "search", search)


@tagged("post_install", "-at_install")
class TestClaimReferenceUniquenessBatch(PlasticosTestCase):
    def _reference(self, label):
        return f"CLM-UNIQ-{label}-{uuid.uuid4().hex[:8].upper()}"

    def _vals(self, name):
        transaction = self._create_transaction(name=self._reference("TX"))
        return {
            "name": name,
            "transaction_id": transaction.id,
            "case_type": "buyer_claim",
            "severity": "medium",
            "state": "pending",
        }

    def test_batch_create_rejects_an_existing_reference_before_insert(self):
        claim_model = self.env["plasticos.claim"]
        held = self._reference("held")
        fresh = self._reference("fresh")
        claim_model.create(self._vals(held))
        with self.assertRaises(ValidationError) as caught:
            claim_model.create([self._vals(fresh), self._vals(held)])
        self.assertIn(f"Claim reference '{held}' already exists.", str(caught.exception))
        self.assertEqual(claim_model.search_count([("name", "=", fresh)]), 0)

    def test_batch_create_runs_one_uniqueness_search(self):
        claim_model = self.env["plasticos.claim"]
        vals_list = [self._vals(self._reference(str(index))) for index in range(3)]
        calls = []
        with _counting_search(type(claim_model), calls):
            claims = claim_model.create(vals_list)
        self.assertEqual(len(claims), 3)
        self.assertEqual(len(calls), 1, calls)

    def test_sequence_assignment_still_names_a_new_claim(self):
        claim_model = self.env["plasticos.claim"]
        claim = claim_model.create(self._vals("New"))
        self.assertTrue(claim.name)
        self.assertNotEqual(claim.name, "New")

    def test_single_write_of_a_held_reference_raises_and_a_free_one_is_one_search(self):
        claim_model = self.env["plasticos.claim"]
        held = self._reference("held")
        claim_model.create(self._vals(held))
        claim = claim_model.create(self._vals(self._reference("other")))
        with self.assertRaises(ValidationError) as caught:
            claim.write({"name": held})
        self.assertIn(f"Claim reference '{held}' already exists.", str(caught.exception))
        calls = []
        free = self._reference("free")
        with _counting_search(type(claim_model), calls):
            claim.write({"name": free})
        self.assertEqual(claim.name, free)
        self.assertEqual(len(calls), 1, calls)

    def test_multi_claim_write_of_one_reference_raises_without_a_per_record_search(self):
        claim_model = self.env["plasticos.claim"]
        first = claim_model.create(self._vals(self._reference("first")))
        second = claim_model.create(self._vals(self._reference("second")))
        shared = self._reference("shared")
        calls = []
        with _counting_search(type(claim_model), calls), self.assertRaises(ValidationError) as caught:
            (first | second).write({"name": shared})
        self.assertIn(f"Claim reference '{shared}' already exists.", str(caught.exception))
        self.assertLessEqual(len(calls), 1, calls)
