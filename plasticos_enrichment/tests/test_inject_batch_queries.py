"""Injection writes provenance in one batch and looks the partner's profiles up once."""

from unittest.mock import patch

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.tests.common import tagged

PROVENANCE = "plasticos.enrichment.provenance"


def _counting(model_cls, method_name, calls):
    real = getattr(model_cls, method_name)

    def wrapped(self, *args, **kwargs):
        calls.append(args[0] if args else kwargs)
        return real(self, *args, **kwargs)

    return patch.object(model_cls, method_name, wrapped)


@tagged("post_install", "-at_install", "plasticos", "enrichment")
class TestInjectBatchQueries(PlasticosTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._skip_if_model_missing("plasticos.enrichment.run")
        cls.run_model = cls.env["plasticos.enrichment.run"]

    def _partner(self, name):
        return self.env["res.partner"].create({"name": name, "is_company": True, "supplier_rank": 1})

    def test_gate_review_inject_writes_every_provenance_row_in_one_create(self):
        partner = self._partner("Inject Batch Gate Co")
        proposed = {"website": "https://batch.example", "city": "Batchville"}
        run = self.run_model.create({"partner_id": partner.id})
        run.write(
            {
                "engine_used": "gate",
                "state": "review",
                "gate_proposal": {"final_fields": proposed, "proposed_partner_fields": proposed},
                "gate_packet_id": "pkt-batch-1",
            }
        )
        creates = []
        with _counting(type(self.env[PROVENANCE]), "create", creates):
            run.action_inject()
        self.assertEqual(run.state, "injected")
        self.assertEqual(run.fields_written, 2)
        self.assertEqual(partner.website, "https://batch.example")
        self.assertEqual(partner.city, "Batchville")
        self.assertEqual(len(creates), 1, creates)
        rows = self.env[PROVENANCE].search([("run_id", "=", run.id)])
        self.assertEqual(sorted(rows.mapped("target_field")), ["city", "website"])
        self.assertTrue(all(row.status == "written" for row in rows))

    def test_material_inject_looks_profiles_up_once_and_merges_a_repeated_identity(self):
        partner = self._partner("Inject Batch Material Co")
        polymer = self.env.ref("plasticos_material_profile.polymer_pp")
        form = self.env.ref("plasticos_material_profile.form_bale")
        run = self.run_model.create({"partner_id": partner.id})
        source = self.env["plasticos.enrichment.source"].create(
            {"partner_id": partner.id, "source_type": "website", "url": "https://batch.example/materials"}
        )
        self.env["plasticos.enrichment.extraction"].create(
            {
                "run_id": run.id,
                "source_id": source.id,
                "material_json": [{"polymer": "PP"}, {"polymer": "PP"}, {"polymer": "PP"}],
                "confidence": 0.95,
                "governance_passed": True,
            }
        )
        run.write({"state": "validated"})
        self.assertTrue(run.extraction_ids.filtered("is_injectable"))
        service_cls = type(self.env["plasticos.enrichment.service"])
        profile_cls = type(self.env["plasticos.material.profile"])
        profile_searches = []

        def normalize_material(_service, _raw):
            return {"polymer": "PP", "form": "BALES", "freeform_notes": "batch inject"}, [], []

        with (
            patch.object(service_cls, "normalize_material", normalize_material),
            _counting(profile_cls, "search", profile_searches),
        ):
            run.action_inject()
        self.assertEqual(run.state, "injected")
        profiles = self.env["plasticos.material.profile"].search(
            [("partner_id", "=", partner.id), ("polymer_id", "=", polymer.id), ("form_id", "=", form.id)]
        )
        self.assertEqual(len(profiles), 1)
        self.assertEqual(profiles.freeform_notes, "batch inject")
        self.assertEqual(run.profiles_created, 1)
        partner_lookups = [
            domain
            for domain in profile_searches
            if any(term[0] == "partner_id" for term in domain if isinstance(term, tuple))
        ]
        self.assertEqual(len(partner_lookups), 1, profile_searches)
