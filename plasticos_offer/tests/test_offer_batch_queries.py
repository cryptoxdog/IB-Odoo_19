"""Offer image counts and price autofill are one query per recordset or create batch."""

import base64
from unittest.mock import patch

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.tests.common import tagged

_PNG_DATAS = base64.b64encode(b"png")
_PDF_DATAS = base64.b64encode(b"pdf")


def _counting_search(model_cls, calls):
    real = model_cls.search

    def search(self, *args, **kwargs):
        calls.append(args[0] if args else kwargs.get("domain"))
        return real(self, *args, **kwargs)

    return patch.object(model_cls, "search", search)


@tagged("post_install", "-at_install", "offer")
class TestOfferBatchQueries(PlasticosTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.supplier = cls.env["res.partner"].create({"name": "Batch Offer Supplier", "is_company": True})
        cls.buyer_a = cls.env["res.partner"].create({"name": "Batch Offer Buyer A", "is_company": True})
        cls.buyer_b = cls.env["res.partner"].create({"name": "Batch Offer Buyer B", "is_company": True})
        cls.intake = cls._create_intake(partner=cls.supplier)

    def _offer_vals(self, buyer, **kw):
        vals = {"intake_id": self.intake.id, "supplier_id": self.supplier.id, "buyer_id": buyer.id}
        vals.update(kw)
        return vals

    def _image_query_cost(self, offers):
        offers.invalidate_recordset(["image_count"])
        before = self.env.cr.sql_log_count
        offers.mapped("image_count")
        return self.env.cr.sql_log_count - before

    def test_image_count_is_grouped_across_offers_and_keeps_its_domain(self):
        offers = self.env["plasticos.offer"].create(
            [self._offer_vals(self.buyer_a, price_per_lb=0.4), self._offer_vals(self.buyer_b, price_per_lb=0.4)]
        )
        first = offers[0]
        self.env["ir.attachment"].create(
            [
                {
                    "name": "a.png",
                    "res_model": "plasticos.offer",
                    "res_id": first.id,
                    "mimetype": "image/png",
                    "datas": _PNG_DATAS,
                },
                {
                    "name": "b.png",
                    "res_model": "plasticos.offer",
                    "res_id": first.id,
                    "mimetype": "image/png",
                    "datas": _PNG_DATAS,
                },
                {
                    "name": "a.pdf",
                    "res_model": "plasticos.offer",
                    "res_id": first.id,
                    "mimetype": "application/pdf",
                    "datas": _PDF_DATAS,
                },
                {
                    "name": "o.png",
                    "res_model": "res.partner",
                    "res_id": first.id,
                    "mimetype": "image/png",
                    "datas": _PNG_DATAS,
                },
            ]
        )
        offers.invalidate_recordset(["image_count"])
        self.assertEqual(offers.mapped("image_count"), [2, 0])
        fresh = self.env["plasticos.offer"].new({})
        self.assertEqual((fresh | offers).mapped("image_count"), [0, 2, 0])
        one_cost = self._image_query_cost(first)
        two_cost = self._image_query_cost(offers)
        self.assertGreaterEqual(one_cost, 1)
        self.assertLess(two_cost, one_cost * 2)

    def test_price_autofill_is_one_match_lookup_per_create_batch(self):
        match_model = self.env["plasticos.intake.match"]
        match_model.create(
            [
                {"intake_id": self.intake.id, "buyer_id": self.buyer_a.id, "typical_price": 0.5},
                {"intake_id": self.intake.id, "buyer_id": self.buyer_a.id, "typical_price": 0.7},
                {"intake_id": self.intake.id, "buyer_id": self.buyer_b.id, "typical_price": 0.3},
            ]
        )
        calls = []
        with _counting_search(type(match_model), calls):
            offers = self.env["plasticos.offer"].create(
                [
                    self._offer_vals(self.buyer_a),
                    self._offer_vals(self.buyer_b),
                    self._offer_vals(self.buyer_a, price_per_lb=0.9),
                ]
            )
        self.assertEqual(offers.mapped("price_per_lb"), [0.7, 0.3, 0.9])
        self.assertEqual(len(calls), 1, calls)

    def test_price_autofill_leaves_an_unmatched_buyer_at_zero(self):
        offer = self.env["plasticos.offer"].create(self._offer_vals(self.buyer_b))
        self.assertEqual(offer.price_per_lb, 0.0)
