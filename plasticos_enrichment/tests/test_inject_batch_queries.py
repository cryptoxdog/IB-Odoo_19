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
        # S6 (C06-SCOPE-3 c): Bales was retired as a form on 2026-11-10 (c1bd4e93; bales are
        # packaging), so this fixture uses an active form. The test is about one profile lookup.
        form = self.env.ref("plasticos_material_profile.form_pellets")
        run = self.run_model.create({"partner_id": partner.id})
        source = self.env["plasticos.enrichment.source"].create(
            {"partner_id": partner.id, "source_type": "website", "url": "https://batch.example/materials"}
        )
        self.env["plasticos.enrichment.extraction"].create(
            {
                "run_id": run.id,
                "source_id": source.id,
                "material_json": [
                    {"polymer": "PP"},
                    {"polymer": "PP"},
                    {"polymer": "PP"},
                    {"polymer": "PP"},
                ],
                "confidence": 0.95,
                "governance_passed": True,
            }
        )
        run.write({"state": "validated"})
        self.assertTrue(run.extraction_ids.filtered("is_injectable"))
        service_cls = type(self.env["plasticos.enrichment.service"])
        profile_cls = type(self.env["plasticos.material.profile"])
        profile_searches = []
        profile_creates = []
        seen = {"n": 0}

        def normalize_material(_service, _raw):
            seen["n"] += 1
            vals = {"polymer": "PP", "form": "PELLETS", "freeform_notes": "batch inject"}
            if seen["n"] == 4:
                vals["certification_notes"] = "merged note"
            return vals, [], []

        with (
            patch.object(service_cls, "normalize_material", normalize_material),
            _counting(profile_cls, "search", profile_searches),
            _counting(profile_cls, "create", profile_creates),
        ):
            run.action_inject()
        self.assertEqual(run.state, "injected")
        profiles = self.env["plasticos.material.profile"].search(
            [("partner_id", "=", partner.id), ("polymer_id", "=", polymer.id), ("form_id", "=", form.id)]
        )
        self.assertEqual(len(profiles), 1)
        self.assertEqual(profiles.freeform_notes, "batch inject")
        self.assertEqual(profiles.certification_notes, "merged note")
        self.assertEqual(run.profiles_created, 1)
        self.assertEqual(run.profiles_updated, 1)
        self.assertEqual(len(profile_creates), 1, profile_creates)
        self.assertIsInstance(profile_creates[0], list)
        self.assertEqual(len(profile_creates[0]), 1)
        # The inject preloads every profile for the partner in one search. Creating
        # that profile also runs the material-profile uniqueness pre-check, which
        # searches partner + polymer + form + grade once per created row.
        preload_lookups = [
            domain
            for domain in profile_searches
            if [term[0] for term in domain if isinstance(term, tuple)] == ["partner_id"]
        ]
        uniqueness_lookups = [
            domain
            for domain in profile_searches
            if any(isinstance(term, tuple) and term[0] == "material_grade_id" for term in domain)
        ]
        self.assertEqual(len(preload_lookups), 1, profile_searches)
        self.assertEqual(len(uniqueness_lookups), 1, profile_searches)
