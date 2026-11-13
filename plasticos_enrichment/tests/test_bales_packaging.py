"""Extracted bales become packaging Bales, never a form (operator decision 2026-11-12).

The Bales form was retired on 2026-11-10 (plasticos_material_profile 19.0.5.11.14
moves those profiles onto packaging Bales and clears the form). Enrichment follows
the same end state: bale, bales and baled set ``packaging_type_id`` to the Bales
packaging type, leave the form empty and never fall back to form OTHER. Inject
keeps merge-never-overwrite and provenance. These tests run the real
``normalize_material`` path; nothing is patched.
"""

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.tests.common import tagged

PROVENANCE = "plasticos.enrichment.provenance"
PROFILE = "plasticos.material.profile"


@tagged("post_install", "-at_install", "plasticos", "enrichment")
class TestBalesPackaging(PlasticosTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._skip_if_model_missing("plasticos.enrichment.run")
        cls.service = cls.env["plasticos.enrichment.service"]
        cls.bales = cls.env.ref("plasticos_material_profile.packaging_bales")
        cls.gaylords = cls.env.ref("plasticos_material_profile.packaging_gaylords")
        cls.polymer = cls.env.ref("plasticos_material_profile.polymer_pp")
        cls.pellets = cls.env.ref("plasticos_material_profile.form_pellets")

    def _run(self, name, materials):
        partner = self.env["res.partner"].create({"name": name, "is_company": True, "supplier_rank": 1})
        run = self.env["plasticos.enrichment.run"].create({"partner_id": partner.id})
        source = self.env["plasticos.enrichment.source"].create(
            {"partner_id": partner.id, "source_type": "website", "url": "https://bales.example/materials"}
        )
        self.env["plasticos.enrichment.extraction"].create(
            {
                "run_id": run.id,
                "source_id": source.id,
                "material_json": materials,
                "confidence": 0.95,
                "governance_passed": True,
            }
        )
        run.write({"state": "validated"})
        return partner, run

    def test_bale_words_normalize_to_packaging_and_no_form(self):
        for word in ("bale", "bales", "baled", " Bales "):
            raw = dict(polymer="pp", form=word, confidence=0.9, source_sentence=f"PP {word} weekly")
            vals, provenance, unmapped = self.service.normalize_material(raw)
            self.assertEqual(vals.get("packaging_type_id"), self.bales.id, word)
            self.assertNotIn("form", vals, word)
            self.assertEqual(unmapped, [], word)
            row = next(item for item in provenance if item["target_field"] == "packaging_type_id")
            self.assertEqual(row["value"], str(self.bales.id))
            self.assertEqual(row["source_sentence"], f"PP {word} weekly")
        vals, _provenance, _unmapped = self.service.normalize_material({"polymer": "pp", "form": "pellets"})
        self.assertEqual(vals.get("form"), "PELL")
        self.assertNotIn("packaging_type_id", vals)

    def test_inject_creates_a_bales_profile_without_a_form(self):
        partner, run = self._run(
            "Bales Packaging Create Co",
            [{"polymer": "PP", "form": "bales", "confidence": 0.9, "source_sentence": "We ship PP in bales."}],
        )
        run.action_inject()
        self.assertEqual(run.state, "injected")
        profiles = self.env[PROFILE].search([("partner_id", "=", partner.id)])
        self.assertEqual(len(profiles), 1)
        self.assertEqual(profiles.polymer_id, self.polymer)
        self.assertEqual(profiles.packaging_type_id, self.bales)
        self.assertFalse(profiles.form_id)
        other = self.env.ref("plasticos_material_profile.form_other", raise_if_not_found=False)
        if other:
            self.assertNotEqual(profiles.form_id, other)
        rows = self.env[PROVENANCE].search([("run_id", "=", run.id)])
        by_field = {row.target_field: row for row in rows}
        self.assertEqual(by_field["packaging_type_id"].status, "written")
        self.assertEqual(by_field["packaging_type_id"].value_written, str(self.bales.id))
        self.assertEqual(by_field["packaging_type_id"].source_sentence, "We ship PP in bales.")
        self.assertNotIn("form_id", by_field)
        self.assertEqual(run.profiles_created, 1)

    def test_inject_merges_packaging_and_never_overwrites_it(self):
        partner, run = self._run(
            "Bales Packaging Merge Co",
            [{"polymer": "PP", "form": "baled"}, {"polymer": "PP", "form": "pellets"}],
        )
        empty = self.env[PROFILE].create({"partner_id": partner.id, "polymer_id": self.polymer.id})
        run.action_inject()
        self.assertEqual(empty.packaging_type_id, self.bales)
        self.assertFalse(empty.form_id)
        pellets = self.env[PROFILE].search([("partner_id", "=", partner.id), ("form_id", "=", self.pellets.id)])
        self.assertEqual(len(pellets), 1)
        self.assertFalse(pellets.packaging_type_id)
        self.assertEqual(self.env[PROFILE].search_count([("partner_id", "=", partner.id)]), 2)
        written = self.env[PROVENANCE].search([("run_id", "=", run.id), ("target_field", "=", "packaging_type_id")])
        self.assertEqual(written.mapped("status"), ["written"])

        partner_b, run_b = self._run("Bales Packaging Keep Co", [{"polymer": "PP", "form": "bales"}])
        kept = self.env[PROFILE].create(
            {"partner_id": partner_b.id, "polymer_id": self.polymer.id, "packaging_type_id": self.gaylords.id}
        )
        run_b.action_inject()
        self.assertEqual(kept.packaging_type_id, self.gaylords)
        self.assertFalse(kept.form_id)
        self.assertEqual(self.env[PROFILE].search_count([("partner_id", "=", partner_b.id)]), 1)
        skipped = self.env[PROVENANCE].search([("run_id", "=", run_b.id), ("target_field", "=", "packaging_type_id")])
        self.assertEqual(skipped.mapped("status"), ["skipped_immutable"])
        self.assertEqual(skipped.previous_value, str(self.gaylords.id))

    def test_inject_of_same_packaging_records_no_conflict(self):
        partner, run = self._run("Bales Packaging Same Co", [{"polymer": "PP", "form": "bales"}])
        same = self.env[PROFILE].create(
            {"partner_id": partner.id, "polymer_id": self.polymer.id, "packaging_type_id": self.bales.id}
        )
        run.action_inject()
        self.assertEqual(same.packaging_type_id, self.bales)
        rows = self.env[PROVENANCE].search([("run_id", "=", run.id), ("target_field", "=", "packaging_type_id")])
        self.assertFalse(rows)
