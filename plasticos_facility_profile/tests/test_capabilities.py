"""ADR-134 worked examples, detail fields, access, auto-link, and site logistics."""

from odoo import Command
from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, tagged

EXPECTED_DETAILS = {
    "shredding": ["shafts", "hp", "feed_opening_w_in", "feed_opening_l_in", "screen", "screen_size_in"],
    "grinding": ["hp", "throat_opening_w_in", "throat_opening_l_in", "screen_size_in"],
    "sink_float": ["separates"],
    "washing": ["water", "friction_washer", "dryer"],
    "metal_separation": ["method"],
    "drying": [],
    "sorting": ["method"],
    "baling": ["baler", "ram", "bale_weight_lb"],
    "pelletizing": ["screw", "screw_diameter_mm", "melt_filter", "vented"],
    "extrusion": ["screw", "screw_diameter_mm"],
    "compounding": ["screw", "screw_diameter_mm", "melt_filter", "vented"],
    "injection_molding": [],
    "blow_molding": [],
    "film_blowing": [],
    "film_casting": [],
    "thermoforming": [],
    "rotomolding": [],
    "compression_molding": [],
    "purification": [],
}

OPENING_FLOATS = {
    "shredding": ("feed_opening_w_in", "feed_opening_l_in"),
    "grinding": ("throat_opening_w_in", "throat_opening_l_in"),
}


@tagged("post_install", "-at_install")
class TestCapabilities(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.parent = cls.env["res.partner"].create({"name": "C5 Capability Parent", "is_company": True})
        cls.Type = cls.env["plasticos.capability.type"]
        cls.Capability = cls.env["plasticos.capability"]
        cls.Profile = cls.env["plasticos.material.profile"]

    def _ref(self, xmlid):
        return self.env.ref(f"plasticos_material_profile.{xmlid}")

    def _type(self, code):
        record = self.Type.search([("code", "=", code)], limit=1)
        self.assertTrue(record, f"capability type {code} is missing from seed data")
        return record

    def _site(self, name):
        return self.env["res.partner"].create({"name": name, "parent_id": self.parent.id, "type": "delivery"})

    def _facility(self, site):
        return self.env["plasticos.facility.profile"].create({"partner_id": site.id})

    def _capability(self, facility, code, **extra):
        vals = {
            "facility_profile_id": facility.id,
            "capability_type_id": self._type(code).id,
        }
        vals.update(extra)
        return self.Capability.create(vals)

    def _material(self, partner, polymer_xml, direction, **extra):
        vals = {
            "partner_id": partner.id,
            "polymer_id": self._ref(polymer_xml).id,
            "direction": direction,
        }
        vals.update(extra)
        return self.Profile.create(vals)

    def _shown_details(self, capability):
        return [row["name"] for row in capability.read(["details"])[0]["details"]]

    def test_seed_is_the_canonical_list(self):
        found = self.Type.search([]).mapped("code")
        self.assertEqual(sorted(found), sorted(EXPECTED_DETAILS))
        for code, names in EXPECTED_DETAILS.items():
            definition = self._type(code).details_definition or []
            self.assertEqual([row["name"] for row in definition], names)
            for row in definition:
                self.assertTrue(row["name"].replace("_", "").isalnum())
                self.assertEqual(row["name"], row["name"].lower())
        for code, openings in OPENING_FLOATS.items():
            kinds = {row["name"]: row["type"] for row in self._type(code).details_definition}
            for opening in openings:
                self.assertEqual(kinds[opening], "float")

    def test_row_shows_only_its_own_detail_fields(self):
        facility = self._facility(self._site("C5 Detail Site"))
        shred = self._capability(facility, "shredding", sequence=1)
        metal = self._capability(facility, "metal_separation", sequence=2)
        drying = self._capability(facility, "drying", sequence=3)
        self.assertEqual(self._shown_details(shred), EXPECTED_DETAILS["shredding"])
        self.assertNotIn("method", self._shown_details(shred))
        self.assertEqual(self._shown_details(metal), ["method"])
        self.assertNotIn("shafts", self._shown_details(metal))
        self.assertEqual(self._shown_details(drying), [])

    def test_mixed_type_write_raises_and_grouped_writes_succeed(self):
        facility = self._facility(self._site("C5 Mixed Write Site"))
        shred = self._capability(facility, "shredding", sequence=1)
        other = self._capability(facility, "shredding", sequence=2)
        metal = self._capability(facility, "metal_separation", sequence=3)
        with self.assertRaises(UserError):
            (shred | metal).write({"details": {"shafts": "single"}})
        (shred | other).write({"details": {"shafts": "quad", "screen": False}})
        for row in (shred, other):
            values = {item["name"]: item.get("value") for item in row.read(["details"])[0]["details"]}
            self.assertEqual(values["shafts"], "quad")
            self.assertFalse(values["screen"])
        self.assertEqual(self._shown_details(metal), ["method"])

    def test_type_change_drops_details_and_warns(self):
        facility = self._facility(self._site("C5 Type Change Site"))
        shred = self._capability(facility, "shredding")
        shred.write({"details": {"shafts": "single", "screen": True}})
        draft = self.Capability.new({"capability_type_id": self._type("grinding").id}, origin=shred)
        warning = draft._onchange_capability_type_id()
        self.assertIn("drops", warning["warning"]["message"].lower())
        self.assertFalse(draft.details)
        shred.write({"capability_type_id": self._type("grinding").id})
        shown = self._shown_details(shred)
        self.assertEqual(shown, EXPECTED_DETAILS["grinding"])
        self.assertNotIn("shafts", shown)

    def test_operations_manager_acl(self):
        manager = self.env["res.users"].create(
            {
                "name": "C5 Ops Manager",
                "login": "c5.bcap.ops",
                "group_ids": [Command.set([self.env.ref("plasticos_security_base.group_operations_manager").id])],
            }
        )
        sales = self.env["res.users"].create(
            {
                "name": "C5 Sales Rep",
                "login": "c5.bcap.sales",
                "group_ids": [Command.set([self.env.ref("plasticos_security_base.group_sales_rep").id])],
            }
        )
        logistics = self.env["res.users"].create(
            {
                "name": "C5 Logistics",
                "login": "c5.bcap.logistics",
                "group_ids": [Command.set([self.env.ref("plasticos_security_base.group_logistics").id])],
            }
        )
        accounting = self.env["res.users"].create(
            {
                "name": "C5 Accounting",
                "login": "c5.bcap.accounting",
                "group_ids": [Command.set([self.env.ref("plasticos_security_base.group_accounting").id])],
            }
        )
        shred = self._type("shredding")
        for reader in (sales, logistics, accounting, manager):
            shred.with_user(reader).check_access("read")
        shred.with_user(manager).check_access("write")
        self.Type.with_user(manager).check_access("create")
        for blocked in (sales, logistics, accounting):
            with self.assertRaises(AccessError):
                shred.with_user(blocked).check_access("write")
            with self.assertRaises(AccessError):
                self.Type.with_user(blocked).check_access("create")

    def test_autolink_when_the_site_has_one_capability(self):
        site = self._site("C5 Autolink Site")
        facility = self._facility(site)
        first = self._material(site, "polymer_hdpe", "in", material_grade_id=self._ref("material_grade_toters").id)
        second = self._material(site, "polymer_pp", "out", form_id=self._ref("form_pellets").id)
        self.assertFalse(first.capability_id)
        self.assertFalse(second.capability_id)
        only = self._capability(facility, "shredding")
        self.assertEqual(first.capability_id, only)
        self.assertEqual(second.capability_id, only)
        first.write({"capability_id": False})
        self.assertFalse(first.capability_id)
        third = self._material(site, "polymer_hdpe", "out", form_id=self._ref("form_regrind").id)
        self.assertEqual(third.capability_id, only)
        self.assertFalse(first.capability_id)
        self._capability(facility, "grinding")
        fourth = self._material(site, "polymer_pp", "in", material_grade_id=self._ref("material_grade_pallets").id)
        self.assertFalse(fourth.capability_id)
        self.assertEqual(second.capability_id, only)

    def test_worked_examples(self):
        border = self._worked_border()
        solvent = self._worked_solvent()
        lines = self._worked_three_lines()
        mrf = self._worked_mrf()
        self.assertEqual(len(border.capability_ids), 3)
        self.assertEqual(len(solvent.capability_ids), 4)
        self.assertEqual(len(lines.capability_ids), 3)
        self.assertEqual(mrf.capability_ids.model, "V60")
        self.assertEqual(mrf.capability_ids.capability_type_id.code, "baling")

    def _worked_border(self):
        site = self._site("C5 Border Shred Site")
        facility = self._facility(site)
        shred = self._capability(facility, "shredding", sequence=1)
        metal = self._capability(facility, "metal_separation", sequence=2)
        grind = self._capability(facility, "grinding", sequence=3, rated_capacity_lb_hr=2000)
        shred.write({"details": {"shafts": "single", "screen": False}})
        metal.write({"details": {"method": "magnet"}})
        pallets = self._material(
            site,
            "polymer_pp_pe",
            "in",
            material_grade_id=self._ref("material_grade_pallets").id,
            packaging_type_id=self._ref("packaging_stacked").id,
            rate_lb_hr=1000,
            capability_id=shred.id,
            freeform_notes="must precut",
        )
        toters = self._material(
            site,
            "polymer_hdpe",
            "in",
            material_grade_id=self._ref("material_grade_toters").id,
            packaging_type_id=self._ref("packaging_loose").id,
            rate_lb_hr=2000,
            capability_id=shred.id,
        )
        baled = self._material(
            site,
            "polymer_hdpe",
            "in",
            material_grade_id=self._ref("material_grade_baled_toters").id,
            packaging_type_id=self._ref("packaging_bales").id,
            capability_id=shred.id,
        )
        out_pallets = self._material(
            site,
            "polymer_pp_pe",
            "out",
            form_id=self._ref("form_regrind").id,
            material_grade_id=self._ref("material_grade_pallets").id,
            capability_id=grind.id,
        )
        out_toters = self._material(
            site,
            "polymer_hdpe",
            "out",
            form_id=self._ref("form_regrind").id,
            material_grade_id=self._ref("material_grade_toters").id,
            origin_process_type="injection",
            capability_id=grind.id,
        )
        self.assertFalse(shred.model)
        self.assertIn("PP/PE · Pallets · 1000 lb/hr", shred.in_material_chips)
        self.assertIn("HDPE · Toters · 2000 lb/hr", shred.in_material_chips)
        self.assertIn("HDPE · Baled Toters", shred.in_material_chips)
        baled_chip = next(part for part in shred.in_material_chips.split(" | ") if "Baled Toters" in part)
        self.assertEqual(baled_chip, "HDPE · Baled Toters")
        self.assertEqual(pallets.freeform_notes, "must precut")
        self.assertEqual(toters.packaging_type_id, self._ref("packaging_loose"))
        self.assertFalse(metal.in_material_chips)
        self.assertFalse(metal.out_material_chips)
        self.assertIn("PP/PE · Regrind · Pallets", grind.out_material_chips)
        self.assertIn("HDPE · Regrind · Toters", grind.out_material_chips)
        self.assertEqual(grind.rated_capacity_lb_hr, 2000)
        self.assertEqual(out_pallets.capability_id, grind)
        self.assertEqual(out_toters.origin_process_type, "injection")
        self.assertEqual(self._shown_details(shred), EXPECTED_DETAILS["shredding"])
        self.assertEqual(self._shown_details(grind), EXPECTED_DETAILS["grinding"])
        return facility

    def _worked_solvent(self):
        site = self._site("C5 Solvent PP Plant")
        facility = self._facility(site)
        shred = self._capability(facility, "shredding", sequence=1)
        self._capability(facility, "grinding", sequence=2)
        self._capability(facility, "washing", sequence=3)
        pellet = self._capability(facility, "pelletizing", sequence=4)
        supersacs = self._material(
            site,
            "polymer_pp",
            "in",
            material_grade_id=self._ref("material_grade_superacs").id,
            capability_id=shred.id,
        )
        pellets = self._material(
            site,
            "polymer_pp",
            "out",
            form_id=self._ref("form_pellets").id,
            capability_id=pellet.id,
            material_attribute_ids=[Command.link(self._ref("attr_repro").id)],
        )
        self.assertEqual(supersacs.material_grade_id.name, "Supersacs")
        self.assertIn("PP · Supersacs", shred.in_material_chips)
        self.assertIn("PP · Pellets", pellet.out_material_chips)
        self.assertIn(self._ref("attr_repro"), pellets.material_attribute_ids)
        self.assertEqual(
            [cap.capability_type_id.code for cap in facility.capability_ids],
            [
                "shredding",
                "grinding",
                "washing",
                "pelletizing",
            ],
        )
        return facility

    def _worked_three_lines(self):
        site = self._site("C5 Three Shred Lines")
        facility = self._facility(site)
        grades = ("material_grade_buckets", "material_grade_drums", "material_grade_crates")
        models = ("Line A", "Line B", "Line C")
        lines = self.Capability.create(
            [
                {
                    "facility_profile_id": facility.id,
                    "sequence": index,
                    "capability_type_id": self._type("shredding").id,
                    "model": model,
                }
                for index, model in enumerate(models, start=1)
            ]
        )
        for line, grade in zip(lines, grades, strict=True):
            material = self._material(
                site,
                "polymer_hdpe",
                "in",
                material_grade_id=self._ref(grade).id,
                capability_id=line.id,
            )
            self.assertEqual(material.capability_id, line)
            self.assertIn("HDPE", line.in_material_chips)
        self.assertEqual(lines.mapped("model"), list(models))
        self.assertEqual(set(lines.mapped("capability_type_id.code")), {"shredding"})
        return facility

    def _worked_mrf(self):
        site = self._site("C5 V60 MRF")
        facility = self._facility(site)
        baling = self._capability(facility, "baling", sequence=1, model="V60")
        self.assertEqual(baling.model, "V60")
        self.assertFalse(baling.details)
        self.assertEqual(self._shown_details(baling), EXPECTED_DETAILS["baling"])
        self.assertNotIn("shafts", self._shown_details(baling))
        return facility

    def test_site_logistics_visibility_and_blank_means_unknown(self):
        company = self.env["res.partner"].create({"name": "C5 Standalone Company", "is_company": True})
        self.assertTrue(company.is_facility)
        self.assertEqual(company.default_delivery_term, "appointment")
        for name in (
            "loading_docks",
            "export_container_loading",
            "truck_scale",
            "dock_rule_confirmed_on",
            "shipping_hours",
        ):
            self.assertFalse(company[name])
            self.assertIsNone(self.env["res.partner"]._fields[name].default)
        defaults = self.env["res.partner"].default_get(["default_delivery_term"])
        self.assertEqual(defaults.get("default_delivery_term"), "appointment")
        site = self.env["res.partner"].create(
            {"name": "C5 Child Address Site", "parent_id": company.id, "type": "delivery"}
        )
        person = self.env["res.partner"].create({"name": "C5 Person", "parent_id": company.id, "type": "contact"})
        self.assertEqual(site.company_type, "site")
        self.assertTrue(site.is_facility)
        self.assertEqual(person.company_type, "person")
        self.assertFalse(person.is_facility)
        self.assertFalse(company.is_facility)
        arch = self.env.ref("plasticos_facility_profile.view_partner_form_profile_tab").arch
        start = arch.index('string="Site logistics"')
        group = arch[start : arch.index("</group>", start)]
        self.assertIn('invisible="not is_facility"', group)
        for field_name in (
            "default_delivery_term",
            "dock_rule_confirmed_on",
            "shipping_hours",
            "tz",
            "loading_docks",
            "export_container_loading",
            "truck_scale",
        ):
            self.assertIn(f'name="{field_name}"', group)
        form = self.env.ref("plasticos_facility_profile.view_facility_profile_form").arch
        self.assertIn('widget="handle"', form)
        self.assertIn('widget="properties"', form)
        self.assertIn("in_material_chips", form)
        self.assertIn("out_material_chips", form)
