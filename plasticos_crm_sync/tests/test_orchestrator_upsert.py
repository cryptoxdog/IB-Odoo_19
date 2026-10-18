"""TransactionCase: lead upsert idempotency + orphan resolve (requires Odoo runtime)."""

import base64
import inspect
from unittest.mock import MagicMock, patch

from odoo.addons.plasticos_crm_sync.adapters.base import CanonicalCall, CanonicalLead, CanonicalTableRow
from odoo.addons.plasticos_crm_sync.adapters.vanillasoft.adapter import contact_to_canonical
from odoo.addons.plasticos_crm_sync.services.orchestrator import SyncOrchestrator, _new_outcomes
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


class CrmSyncOrchestratorCase(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.connection = cls.env["plasticos.crm.connection"].create(
            {
                "name": "Test VS",
                "provider": "vanillasoft",
                "project_id": "139705",
                "enabled": False,
            }
        )

    def _lead(self, external_id, **kwargs):
        values = {
            "provider": "vanillasoft",
            "external_id": external_id,
            "company": "Test Co",
            "first_name": "Ada",
            "last_name": "Lovelace",
            "lead_status_raw": "New",
        }
        values.update(kwargs)
        return CanonicalLead(**values)

    def _facility(self, name):
        parent = self.env["res.partner"].create({"name": f"{name} Parent", "is_company": True})
        return self.env["res.partner"].create({"name": name, "is_company": True, "parent_id": parent.id})


@tagged("post_install", "-at_install")
class TestCrmSyncOrchestrator(CrmSyncOrchestratorCase):
    def test_upsert_lead_idempotent(self):
        orch = SyncOrchestrator(self.env)
        dto = CanonicalLead(
            provider="vanillasoft",
            external_id="vs-1001",
            company="Test Co",
            first_name="Ada",
            last_name="Lovelace",
            email="ada@example.com",
            lead_status_raw="New",
        )
        lead1 = orch._upsert_lead(self.connection, dto)
        lead2 = orch._upsert_lead(self.connection, dto)
        self.assertEqual(lead1.id, lead2.id)
        refs = self.env["plasticos.crm.external.ref"].search(
            [
                ("provider", "=", "vanillasoft"),
                ("external_id", "=", "vs-1001"),
                ("res_model", "=", "crm.lead"),
            ]
        )
        self.assertEqual(len(refs), 1)
        self.assertEqual(lead1.vanillasoft_id, "vs-1001")

    def test_orphan_call_resolves_after_contact(self):
        orch = SyncOrchestrator(self.env)
        call = CanonicalCall(
            provider="vanillasoft",
            external_id="call-9",
            contact_external_id="vs-2002",
            call_datetime_utc="2026-08-01T12:00:00Z",
            duration_seconds=30,
            user_name="Rep",
            result_code="LM",
            comment="orphan",
        )
        orch._upsert_calls(self.connection, [call], None)
        orphans = self.env["plasticos.crm.sync.orphan"].search(
            [
                ("connection_id", "=", self.connection.id),
                ("resolved", "=", False),
                ("kind", "=", "call"),
            ]
        )
        self.assertEqual(len(orphans), 1)

        lead_dto = CanonicalLead(
            provider="vanillasoft",
            external_id="vs-2002",
            company="Later Co",
            first_name="Bob",
            last_name="Builder",
        )
        orch._upsert_lead(self.connection, lead_dto)
        resolved = orch._resolve_orphans(self.connection, MagicMock(), None)
        self.assertEqual(resolved, 1)
        event = self.env["plasticos.crm.call.event"].search(
            [("provider", "=", "vanillasoft"), ("external_id", "=", "call-9")],
            limit=1,
        )
        self.assertTrue(event)
        self.assertEqual(event.lead_id.vanillasoft_id, "vs-2002")

    def _assert_identity_absent(self, external_id):
        leads = self.env["crm.lead"].with_context(active_test=False).search([("vanillasoft_id", "=", external_id)])
        refs = self.env["plasticos.crm.external.ref"].search(
            [("provider", "=", "vanillasoft"), ("external_id", "=", external_id), ("res_model", "=", "crm.lead")]
        )
        self.assertFalse(leads)
        self.assertFalse(refs)

    def test_failure_after_lead_insert_rolls_back_both_identity_rows(self):
        orch = SyncOrchestrator(self.env)
        orch.outcomes = _new_outcomes()
        dto = self._lead("vs-insert-fail")
        lead_model = type(self.env["crm.lead"])
        original = lead_model.create

        def boom(records, vals_list):
            original(records, vals_list)
            raise UserError("injected after lead insert")

        with patch.object(lead_model, "create", boom):
            returned = orch._upsert_lead(self.connection, dto)

        self.assertEqual(orch.last_lead_outcome, "failed")
        self.assertEqual(orch.outcomes["failed"], 1)
        self.assertEqual(orch.outcomes["created"], 0)
        self.assertFalse(returned)
        self.assertTrue(orch.error_rows)
        self._assert_identity_absent(dto.external_id)

        follow = orch._upsert_lead(self.connection, self._lead("vs-after-insert-fail"))
        self.assertEqual(orch.last_lead_outcome, "created")
        self.assertTrue(follow)
        self.assertEqual(follow.vanillasoft_id, "vs-after-insert-fail")

    def test_external_ref_create_failure_rolls_back_the_lead(self):
        orch = SyncOrchestrator(self.env)
        orch.outcomes = _new_outcomes()
        dto = self._lead("vs-ref-fail")
        ref_model = type(self.env["plasticos.crm.external.ref"])

        def boom(records, vals_list):
            raise UserError("injected ref failure")

        with patch.object(ref_model, "create", boom):
            returned = orch._upsert_lead(self.connection, dto)

        self.assertEqual(orch.last_lead_outcome, "failed")
        self.assertEqual(orch.outcomes["failed"], 1)
        self.assertEqual(orch.outcomes["created"], 0)
        self.assertFalse(returned)
        self._assert_identity_absent(dto.external_id)

    def test_usa_does_not_select_minor_outlying_islands(self):
        orch = SyncOrchestrator(self.env)
        us = self.env["res.country"].search([("code", "=", "US")], limit=1)
        um = self.env["res.country"].search([("code", "=", "UM")], limit=1)
        self.assertTrue(us)
        self.assertTrue(um)
        for raw in ("USA", "usa", "US", "United States", "United States Of America"):
            vals = orch._lead_vals_from_dto(self._lead("vs-country", country_code=raw, state_code="PA"))
            self.assertEqual(vals["country_id"], us.id, raw)
            state = self.env["res.country.state"].browse(vals["state_id"])
            self.assertEqual(state.code, "PA")
            self.assertEqual(state.country_id, us)
        minor = orch._lead_vals_from_dto(
            self._lead("vs-um", country_code="USA Minor Outlying Islands", state_code="PA")
        )
        self.assertEqual(minor["country_id"], um.id)
        self.assertFalse(minor["state_id"])

    def test_dead_lead_uses_the_existing_stage(self):
        orch = SyncOrchestrator(self.env)
        vals = orch._lead_vals_from_dto(self._lead("vs-dead", lead_status_raw="5=Dead Lead"))
        self.assertEqual(vals["stage_id"], self.env.ref("plasticos_crm_bridge.stage_dead_lead").id)

    def test_contact_name_collapses_whitespace(self):
        orch = SyncOrchestrator(self.env)
        spaced = orch._lead_vals_from_dto(self._lead("vs-name", first_name="  Ada   ", last_name=" \n Lovelace  "))
        self.assertEqual(spaced["contact_name"], "Ada Lovelace")
        blank = orch._lead_vals_from_dto(self._lead("vs-blank", first_name="   ", last_name="\t"))
        self.assertFalse(blank["contact_name"])

    def test_unmapped_source_and_owner_are_left_empty(self):
        self.env["res.users"].create({"name": "CRM3 Exact Owner", "login": "crm3-exact-owner"})
        self.env["res.users"].create({"name": "CRM3 Twin Owner", "login": "crm3-twin-a"})
        self.env["res.users"].create({"name": "CRM3 Twin Owner", "login": "crm3-twin-b"})
        orch = SyncOrchestrator(self.env)
        missing_source = orch._lead_vals_from_dto(self._lead("vs-source", lead_source_raw="Not A Mapped Source"))
        self.assertFalse(missing_source["source_id"])
        mapped = orch._lead_vals_from_dto(self._lead("vs-google", lead_source_raw="Google"))
        self.assertEqual(mapped["source_id"], self.env.ref("plasticos_crm_bridge.utm_source_google").id)
        exact = orch._lead_vals_from_dto(self._lead("vs-owner", owner_name="  CRM3 Exact Owner  "))
        self.assertEqual(self.env["res.users"].browse(exact["user_id"]).name, "CRM3 Exact Owner")
        self.assertFalse(orch._lead_vals_from_dto(self._lead("vs-missing", owner_name="No Such CRM3 Owner"))["user_id"])
        self.assertFalse(orch._lead_vals_from_dto(self._lead("vs-twin", owner_name="CRM3 Twin Owner"))["user_id"])

    def test_observed_aliases_land_on_native_lead_fields(self):
        self.env["res.users"].create({"name": "CRM3 Alias Owner", "login": "crm3-alias-owner"})
        dto = contact_to_canonical(
            {
                "contact_id": "vs-alias-land",
                "company": "Alias Co",
                "first_name": "Ada",
                "last_name": "Lovelace",
                "address1": "9 Observed St",
                "postal_code": "30301",
                "city": "Atlanta",
                "state": "GA",
                "country": "USA",
                "lead_status": "5=Dead Lead",
                "lead_source_name": "Google",
                "contact_owner": "CRM3 Alias Owner",
                "phone_numbers": [
                    {"name": "business", "number": "555-100-0003"},
                    {"name": "direct", "number": "555-100-0001"},
                    {"name": "mobile 1", "number": "555-100-0002"},
                ],
            }
        )
        lead = SyncOrchestrator(self.env)._upsert_lead(self.connection, dto)
        self.assertEqual(lead.street, "9 Observed St")
        self.assertEqual(lead.zip, "30301")
        self.assertEqual(lead.phone, "555-100-0001")
        self.assertEqual(lead.mobile, "555-100-0002")
        self.assertEqual(lead.country_id.code, "US")
        self.assertEqual(lead.state_id.code, "GA")
        self.assertEqual(lead.stage_id, self.env.ref("plasticos_crm_bridge.stage_dead_lead"))
        self.assertEqual(lead.source_id, self.env.ref("plasticos_crm_bridge.utm_source_google"))
        self.assertEqual(lead.user_id.name, "CRM3 Alias Owner")
        self.assertEqual(
            len(
                self.env["plasticos.crm.external.ref"].search(
                    [("external_id", "=", "vs-alias-land"), ("res_model", "=", "crm.lead")]
                )
            ),
            1,
        )

    def _profiles(self, facility):
        return self.env["plasticos.material.profile"].search([("partner_id", "=", facility.id)])

    def test_admitted_contact_normalizes_each_material_and_replays(self):
        from odoo.addons.plasticos_material_profile.models import material_normalizer

        facility = self._facility("Sync Materials")
        orch = SyncOrchestrator(self.env)
        orch.outcomes = _new_outcomes()
        contact_mark = self.connection.contact_watermark_utc
        call_mark = self.connection.call_watermark_utc
        dto = self._lead(
            "vs-mat-1",
            custom_fields={
                "Materials": "99 Clear LDPE Film; HDPE Drums | PC/ABS",
                "Material Form": "Film",
                "Not A Material": "PE",
            },
        )
        calls = []
        original = material_normalizer.normalize_material

        def wrapped(env, description, grade_evidence=None, structured=None):
            calls.append(description)
            return original(env, description, grade_evidence=grade_evidence, structured=structured)

        with patch.object(material_normalizer, "normalize_material", wrapped):
            lead = orch._upsert_lead(self.connection, dto)
        self.assertTrue(calls)
        self.assertFalse(self._profiles(facility))
        self.assertFalse(lead.partner_id)
        owned = self.env["plasticos.facility.profile"].search([("crm_lead_id", "=", lead.id)])
        self.assertEqual(len(owned), 1)
        self.assertFalse(owned.partner_id)
        self.assertFalse(any("facility unresolved" in row["message"] for row in orch.error_rows))
        self.assertEqual(lead.vanillasoft_id, "vs-mat-1")
        lead.partner_id = facility
        orch.error_rows.clear()
        calls.clear()
        with patch.object(material_normalizer, "normalize_material", wrapped):
            again = orch._upsert_lead(self.connection, dto)
        self.assertEqual(again, lead)
        self.assertIn("99 Clear LDPE Film", calls)
        self.assertIn("HDPE Drums", calls)
        self.assertIn("PC/ABS", calls)
        profiles = {profile.polymer_id.code: profile for profile in self._profiles(facility)}
        self.assertEqual(set(profiles), {"LDPE", "HDPE", "PC_ABS"})
        film = profiles["LDPE"]
        self.assertEqual(film.form_id.code, "FILM")
        self.assertEqual(film.sub_grade, "A")
        self.assertFalse(film.source_type_id)
        self.assertEqual(set(film.material_attribute_ids.mapped("code")), {"clean", "dry"})
        self.assertIn("99 Clear LDPE Film", film.freeform_notes or "")
        self.assertEqual(profiles["HDPE"].form_id.code, "DRUMS")
        self.assertFalse(profiles["HDPE"].sub_grade)
        self.assertFalse(profiles["HDPE"].material_attribute_ids)
        self.assertFalse(profiles["PC_ABS"].form_id)
        self.assertEqual(profiles["PC_ABS"].source_type_id.code, "POST_INDUSTRIAL")
        notes = film.freeform_notes
        attributes = set(film.material_attribute_ids.ids)
        with patch.object(material_normalizer, "normalize_material", wrapped):
            orch._upsert_lead(self.connection, dto)
        film = self._profiles(facility).filtered(lambda profile: profile.polymer_id.code == "LDPE")
        self.assertEqual(len(self._profiles(facility)), 3)
        self.assertEqual(film.freeform_notes, notes)
        self.assertEqual(set(film.material_attribute_ids.ids), attributes)
        self.assertEqual(orch.outcomes["created"], 1)
        self.assertEqual(orch.outcomes["failed"], 0)
        self.assertEqual(self.connection.contact_watermark_utc, contact_mark)
        self.assertEqual(self.connection.call_watermark_utc, call_mark)
        refs = self.env["plasticos.crm.external.ref"].search(
            [("provider", "=", "vanillasoft"), ("external_id", "=", "vs-mat-1"), ("res_model", "=", "crm.lead")]
        )
        self.assertEqual(len(refs), 1)

        orch._upsert_lead(self.connection, self._lead("vs-mat-1", custom_fields={"Materials": "95 Clear LDPE Film"}))
        film = self._profiles(facility).filtered(lambda profile: profile.polymer_id.code == "LDPE")
        self.assertEqual(film.sub_grade, "A")
        self.assertEqual(set(film.material_attribute_ids.mapped("code")), {"clean", "dry"})
        self.assertIn("95 Clear LDPE Film", film.freeform_notes or "")
        self.assertTrue(any("conflicts with stored grade" in row["message"] for row in orch.error_rows))
        self.assertEqual(len(self._profiles(facility)), 3)
        self.assertEqual(orch.outcomes["failed"], 0)

    def test_unresolved_material_is_reported_without_a_profile(self):
        facility = self._facility("Unresolved Material")
        orch = SyncOrchestrator(self.env)
        orch.outcomes = _new_outcomes()
        lead = orch._upsert_lead(self.connection, self._lead("vs-mat-unknown"))
        lead.partner_id = facility
        orch._upsert_lead(
            self.connection,
            self._lead("vs-mat-unknown", custom_fields={"Materials": "Pallets\nnot a polymer"}),
        )
        profiles = self._profiles(facility)
        self.assertEqual(profiles.polymer_id.code, "PLASTIC_PALLETS")
        self.assertFalse(profiles.form_id)
        self.assertTrue(any("not a polymer" in row["message"] for row in orch.error_rows))
        self.assertEqual(orch.outcomes["failed"], 0)
        self.assertEqual(lead.vanillasoft_id, "vs-mat-unknown")

    def test_ambiguous_facility_is_not_invented(self):
        parent = self.env["res.partner"].create({"name": "Ambiguous Parent", "is_company": True})
        self.env["res.partner"].create({"name": "Child A", "is_company": True, "parent_id": parent.id})
        self.env["res.partner"].create({"name": "Child B", "is_company": True, "parent_id": parent.id})
        orch = SyncOrchestrator(self.env)
        lead = orch._upsert_lead(self.connection, self._lead("vs-mat-ambiguous"))
        lead.partner_id = parent
        before = self.env["plasticos.material.profile"].search_count([])
        orch._upsert_lead(self.connection, self._lead("vs-mat-ambiguous", custom_fields={"Materials": "Pallets"}))
        self.assertEqual(self.env["plasticos.material.profile"].search_count([]), before)
        self.assertTrue(any("ambiguous" in row["message"] for row in orch.error_rows))
        self.assertEqual(lead.vanillasoft_id, "vs-mat-ambiguous")

    def test_grade_c_profile_has_neither_clean_nor_dry(self):
        facility = self._facility("Grade C")
        orch = SyncOrchestrator(self.env)
        lead = orch._upsert_lead(self.connection, self._lead("vs-grade-c"))
        lead.partner_id = facility
        orch._upsert_lead(self.connection, self._lead("vs-grade-c", custom_fields={"Materials": "90 Clear LDPE Film"}))
        profile = self._profiles(facility)
        self.assertEqual(profile.polymer_id.code, "LDPE")
        self.assertEqual(profile.form_id.code, "FILM")
        self.assertEqual(profile.sub_grade, "C")
        self.assertFalse(profile.material_attribute_ids)
        self.assertFalse(profile.source_type_id)

    def test_table_row_uses_the_shared_normalizer_and_replays(self):
        from odoo.addons.plasticos_material_profile.models import material_normalizer

        facility = self._facility("Table Materials")
        orch = SyncOrchestrator(self.env)
        lead = orch._upsert_lead(self.connection, self._lead("vs-table-mat"))
        lead.partner_id = facility

        class Adapter:
            def iter_table_rows(self, contact_id):
                yield CanonicalTableRow(
                    provider="vanillasoft",
                    contact_external_id=contact_id,
                    table_id="9",
                    table_name="Materials",
                    external_row_id="row-1",
                    fields={"Material": "Pallets"},
                )

        calls = []
        original = material_normalizer.normalize_material

        def wrapped(env, description, grade_evidence=None, structured=None):
            calls.append(description)
            return original(env, description, grade_evidence=grade_evidence, structured=structured)

        with patch.object(material_normalizer, "normalize_material", wrapped):
            orch._sync_tables_for_lead(self.connection, Adapter(), "vs-table-mat", lead)
        self.assertIn("Pallets", calls)
        profile = self._profiles(facility)
        self.assertEqual(profile.polymer_id.code, "PLASTIC_PALLETS")
        self.assertFalse(profile.form_id)
        notes = profile.freeform_notes
        with patch.object(material_normalizer, "normalize_material", wrapped):
            orch._sync_tables_for_lead(self.connection, Adapter(), "vs-table-mat", lead)
        profile = self._profiles(facility)
        self.assertEqual(len(profile), 1)
        self.assertEqual(profile.freeform_notes, notes)

    def test_manual_and_scheduled_entry_points_share_the_normalizer_path(self):
        manual = inspect.getsource(type(self.connection).action_sync_now)
        scheduled = inspect.getsource(type(self.connection)._cron_sync_all)
        self.assertIn("run_connection", manual)
        self.assertIn("run_connection", scheduled)
        self.assertIn("_sync_contacts", inspect.getsource(SyncOrchestrator.run_connection))
        self.assertIn("_upsert_lead", inspect.getsource(SyncOrchestrator._sync_contacts))
        self.assertIn("_apply_contact_materials", inspect.getsource(SyncOrchestrator._upsert_lead))
        self.assertIn("_sync_tables_for_lead", inspect.getsource(SyncOrchestrator._sync_contacts))
        self.assertIn("_apply_contact_materials", inspect.getsource(SyncOrchestrator._sync_tables_for_lead))

    def test_three_source_materials_become_three_profiles_and_replay(self):
        """One distinct source material becomes one profile. Replay adds none."""
        facility = self._facility("Three Materials")
        orch = SyncOrchestrator(self.env)
        lead = orch._upsert_lead(self.connection, self._lead("vs-three-materials"))
        lead.partner_id = facility
        dto = self._lead(
            "vs-three-materials",
            custom_fields={"Materials": "HDPE Drums\nLDPE Film\nPP Supersacs"},
        )
        orch._upsert_lead(self.connection, dto)
        profiles = self._profiles(facility)
        by_polymer = {profile.polymer_id.code: profile for profile in profiles}
        self.assertEqual(set(by_polymer), {"HDPE", "LDPE", "PP"})
        self.assertEqual(by_polymer["HDPE"].form_id.code, "DRUMS")
        self.assertEqual(by_polymer["LDPE"].form_id.code, "FILM")
        self.assertFalse(by_polymer["LDPE"].sub_grade)
        self.assertFalse(by_polymer["LDPE"].material_attribute_ids)
        self.assertFalse(by_polymer["PP"].form_id)
        self.assertEqual(len(profiles), 3)
        owned = self.env["plasticos.facility.profile"].search([("partner_id", "=", facility.id)])
        self.assertEqual(len(owned), 1)
        self.assertEqual(lead.facility_profile_id, owned)
        self.assertEqual(set(profiles.facility_profile_id), {owned})
        notes = {code: profile.freeform_notes for code, profile in by_polymer.items()}
        orch._upsert_lead(self.connection, dto)
        replayed = self._profiles(facility)
        self.assertEqual(len(replayed), 3)
        self.assertEqual(
            {profile.polymer_id.code: profile.freeform_notes for profile in replayed},
            notes,
        )
        self.assertEqual(self.env["plasticos.facility.profile"].search_count([("partner_id", "=", facility.id)]), 1)

    def test_unknown_form_creates_one_profile_and_replays(self):
        """Polymer is required. An unknown form is stored empty and reused."""
        facility = self._facility("Nullable Form")
        orch = SyncOrchestrator(self.env)
        lead = orch._upsert_lead(self.connection, self._lead("vs-null-form"))
        lead.partner_id = facility
        orch.outcomes = _new_outcomes()
        orch.error_rows.clear()
        dto = self._lead(
            "vs-null-form",
            custom_fields={"Materials": "HDPE Drums\nLDPE Film\nPP Supersacs\nPC/ABS\nPallets"},
        )
        orch._upsert_lead(self.connection, dto)
        profiles = self._profiles(facility)
        by_polymer = {profile.polymer_id.code: profile for profile in profiles}
        self.assertEqual(set(by_polymer), {"HDPE", "LDPE", "PP", "PC_ABS", "PLASTIC_PALLETS"})
        self.assertEqual(by_polymer["HDPE"].form_id.code, "DRUMS")
        self.assertEqual(by_polymer["LDPE"].form_id.code, "FILM")
        self.assertFalse(by_polymer["PP"].form_id)
        self.assertFalse(by_polymer["PC_ABS"].form_id)
        self.assertFalse(by_polymer["PLASTIC_PALLETS"].form_id)
        self.assertFalse(orch.error_rows)
        self.assertEqual(orch.outcomes["failed"], 0)
        self.assertEqual(orch.outcomes["deferred"], 0)
        ids = {code: profile.id for code, profile in by_polymer.items()}
        orch._upsert_lead(self.connection, dto)
        replayed = {profile.polymer_id.code: profile for profile in self._profiles(facility)}
        self.assertEqual({code: profile.id for code, profile in replayed.items()}, ids)
        self.assertFalse(replayed["PP"].form_id)
        self.assertFalse(replayed["PC_ABS"].form_id)
        self.assertFalse(replayed["PLASTIC_PALLETS"].form_id)
        self.assertEqual((replayed["PP"].freeform_notes or "").splitlines().count("PP Supersacs"), 1)
        self.assertEqual((replayed["PC_ABS"].freeform_notes or "").splitlines().count("PC/ABS"), 1)
        self.assertEqual((replayed["PLASTIC_PALLETS"].freeform_notes or "").splitlines().count("Pallets"), 1)
        self.assertEqual(orch.outcomes["failed"], 0)
        self.assertEqual(orch.outcomes["deferred"], 0)

    def test_new_lead_without_partner_owns_one_facility_and_replays(self):
        """A VanillaSoft lead with no partner owns one facility and its materials."""
        partners_before = self.env["res.partner"].search_count([])
        orch = SyncOrchestrator(self.env)
        orch.outcomes = _new_outcomes()
        dto = self._lead(
            "vs-lead-owned",
            custom_fields={"Materials": "HDPE Drums\nLDPE Film\nPP Supersacs"},
        )
        lead = orch._upsert_lead(self.connection, dto)
        self.assertFalse(lead.partner_id)
        self.assertEqual(self.env["res.partner"].search_count([]), partners_before)
        facilities = self.env["plasticos.facility.profile"].search([("crm_lead_id", "=", lead.id)])
        self.assertEqual(len(facilities), 1)
        facility = facilities
        self.assertFalse(facility.partner_id)
        self.assertFalse(facility.equipment_type_ids)
        self.assertFalse(facility.accepted_polymer_ids)
        self.assertFalse(facility.process_type)
        self.assertFalse(facility.form_preference_id)
        self.assertFalse(facility.capacity_lbs_month)
        profiles = self.env["plasticos.material.profile"].search([("facility_profile_id", "=", facility.id)])
        by_polymer = {profile.polymer_id.code: profile for profile in profiles}
        self.assertEqual(set(by_polymer), {"HDPE", "LDPE", "PP"})
        self.assertEqual(by_polymer["HDPE"].form_id.code, "DRUMS")
        self.assertEqual(by_polymer["LDPE"].form_id.code, "FILM")
        self.assertFalse(by_polymer["PP"].form_id)
        self.assertFalse(profiles.mapped("partner_id"))
        self.assertFalse(orch.error_rows)
        ids = {code: profile.id for code, profile in by_polymer.items()}
        orch._upsert_lead(self.connection, dto)
        replayed = self.env["plasticos.material.profile"].search([("facility_profile_id", "=", facility.id)])
        self.assertEqual({profile.polymer_id.code: profile.id for profile in replayed}, ids)
        self.assertEqual(len(self.env["plasticos.facility.profile"].search([("crm_lead_id", "=", lead.id)])), 1)
        self.assertEqual(self.env["res.partner"].search_count([]), partners_before)
        other = orch._upsert_lead(
            self.connection,
            self._lead("vs-lead-owned-other", custom_fields={"Materials": "PP Supersacs"}),
        )
        other_facility = self.env["plasticos.facility.profile"].search([("crm_lead_id", "=", other.id)])
        self.assertEqual(len(other_facility), 1)
        self.assertNotEqual(other_facility, facility)
        other_profiles = self.env["plasticos.material.profile"].search(
            [("facility_profile_id", "=", other_facility.id)]
        )
        self.assertEqual(len(other_profiles), 1)
        self.assertEqual(other_profiles.polymer_id.code, "PP")
        self.assertFalse(other_profiles.form_id)
        self.assertNotEqual(other_profiles.id, by_polymer["PP"].id)
        location = self._facility("Verified Later")
        lead.partner_id = location
        orch._upsert_lead(self.connection, dto)
        facility = self.env["plasticos.facility.profile"].browse(facility.id)
        self.assertEqual(facility.partner_id, location)
        self.assertEqual(facility.crm_lead_id, lead)
        self.assertEqual(lead.facility_profile_id, facility)
        linked = self.env["plasticos.material.profile"].search([("facility_profile_id", "=", facility.id)])
        self.assertEqual({profile.polymer_id.code: profile.id for profile in linked}, ids)
        self.assertEqual(set(linked.mapped("partner_id")), {location})
        self.assertFalse(facility.equipment_type_ids)
        self.assertFalse(facility.accepted_polymer_ids)
        self.assertEqual(self.env["plasticos.facility.profile"].search_count([("partner_id", "=", location.id)]), 1)
        self.assertEqual(self.env["plasticos.material.profile"].search_count([("partner_id", "=", location.id)]), 3)

    def test_approved_aliases_create_one_facility_and_replay(self):
        orch = SyncOrchestrator(self.env)
        dto = self._lead(
            "vs-aliases",
            custom_fields={"Materials": "LDPE Film A\n3-7 Commingled\n1-7 Commingled\nHDPE Drums (HMW-HDPE)"},
        )
        lead = orch._upsert_lead(self.connection, dto)
        facility = self.env["plasticos.facility.profile"].search([("crm_lead_id", "=", lead.id)])
        self.assertEqual(len(facility), 1)
        profiles = self.env["plasticos.material.profile"].search([("facility_profile_id", "=", facility.id)])
        by_polymer = {profile.polymer_id.code: profile for profile in profiles}
        self.assertEqual(set(by_polymer), {"LDPE", "3_7_COMMINGLED_BOTTLES", "1_7_COMMINGLED_BOTTLES", "HDPE_HMW"})
        self.assertEqual(by_polymer["LDPE"].form_id.code, "FILM")
        self.assertEqual(by_polymer["LDPE"].sub_grade, "A")
        self.assertFalse(by_polymer["LDPE"].material_attribute_ids)
        self.assertEqual(by_polymer["3_7_COMMINGLED_BOTTLES"].form_id.code, "BOTTLES")
        self.assertFalse(by_polymer["3_7_COMMINGLED_BOTTLES"].source_type_id)
        self.assertEqual(by_polymer["1_7_COMMINGLED_BOTTLES"].form_id.code, "BOTTLES")
        self.assertFalse(by_polymer["1_7_COMMINGLED_BOTTLES"].source_type_id)
        self.assertEqual(by_polymer["HDPE_HMW"].form_id.code, "DRUMS")
        ids = {code: profile.id for code, profile in by_polymer.items()}
        orch._upsert_lead(self.connection, dto)
        replayed = self.env["plasticos.material.profile"].search([("facility_profile_id", "=", facility.id)])
        self.assertEqual({profile.polymer_id.code: profile.id for profile in replayed}, ids)

    def test_material_database_failure_rolls_back_and_the_batch_continues(self):
        orch = SyncOrchestrator(self.env)
        orch.outcomes = _new_outcomes()
        profiles_before = self.env["plasticos.material.profile"].search_count([])
        facilities_before = self.env["plasticos.facility.profile"].search_count([])
        profile_model = type(self.env["plasticos.material.profile"])
        original = profile_model.create

        def boom(records, vals_list):
            created = original(records, vals_list)
            records.env.cr.execute("SELECT 1 FROM plasticos_material_profile_missing_for_rollback")
            return created

        failed_dto = self._lead("vs-mat-rollback", custom_fields={"Materials": "HDPE Drums\nLDPE Film"})
        with patch.object(profile_model, "create", boom):
            failed = orch._upsert_lead(self.connection, failed_dto)
        self.assertEqual(failed.vanillasoft_id, "vs-mat-rollback")
        self.assertEqual(orch.last_lead_outcome, "created")
        self.assertEqual(orch.outcomes["created"], 1)
        self.assertEqual(orch.outcomes["failed"], 0)
        self.assertTrue(any("material normalization failed" in row["message"] for row in orch.error_rows))
        self.assertFalse(self.env["plasticos.facility.profile"].search([("crm_lead_id", "=", failed.id)]))
        self.assertEqual(self.env["plasticos.material.profile"].search_count([]), profiles_before)
        self.assertEqual(self.env["plasticos.facility.profile"].search_count([]), facilities_before)

        nxt = orch._upsert_lead(
            self.connection, self._lead("vs-mat-after-rollback", custom_fields={"Materials": "PP Supersacs"})
        )
        self.assertEqual(orch.last_lead_outcome, "created")
        self.assertEqual(orch.outcomes["created"], 2)
        nxt_facility = self.env["plasticos.facility.profile"].search([("crm_lead_id", "=", nxt.id)])
        self.assertEqual(len(nxt_facility), 1)
        nxt_profile = self.env["plasticos.material.profile"].search([("facility_profile_id", "=", nxt_facility.id)])
        self.assertEqual(nxt_profile.polymer_id.code, "PP")
        self.assertFalse(nxt_profile.form_id)

        recovered = orch._upsert_lead(self.connection, failed_dto)
        self.assertEqual(recovered, failed)
        recovered_facility = self.env["plasticos.facility.profile"].search([("crm_lead_id", "=", failed.id)])
        self.assertEqual(len(recovered_facility), 1)
        recovered_profiles = self.env["plasticos.material.profile"].search(
            [("facility_profile_id", "=", recovered_facility.id)]
        )
        self.assertEqual({profile.polymer_id.code for profile in recovered_profiles}, {"HDPE", "LDPE"})

    def test_existing_facility_profiles_are_reconciled_without_duplicates(self):
        location = self._facility("Already Profiled")
        existing_facility = self.env["plasticos.facility.profile"].create({"partner_id": location.id})
        pp = self.env["plasticos.polymer"].search([("code", "=", "PP")], limit=1)
        existing_pp = self.env["plasticos.material.profile"].create(
            {"partner_id": location.id, "polymer_id": pp.id, "freeform_notes": "already there"}
        )
        orch = SyncOrchestrator(self.env)
        dto = self._lead(
            "vs-reconcile",
            custom_fields={"Materials": "HDPE Drums\nLDPE Film\nPP Supersacs"},
        )
        lead = orch._upsert_lead(self.connection, dto)
        provisional = self.env["plasticos.facility.profile"].search([("crm_lead_id", "=", lead.id)])
        self.assertEqual(len(provisional), 1)
        self.assertNotEqual(provisional, existing_facility)
        provisional_ids = {
            profile.polymer_id.code: profile.id
            for profile in self.env["plasticos.material.profile"].search([("facility_profile_id", "=", provisional.id)])
        }
        lead.partner_id = location
        orch._upsert_lead(self.connection, dto)
        self.assertFalse(provisional.exists())
        self.assertEqual(self.env["plasticos.facility.profile"].search_count([("partner_id", "=", location.id)]), 1)
        kept = self.env["plasticos.facility.profile"].search([("partner_id", "=", location.id)])
        self.assertEqual(kept, existing_facility)
        self.assertEqual(kept.crm_lead_id, lead)
        materials = self.env["plasticos.material.profile"].search([("partner_id", "=", location.id)])
        by_polymer = {profile.polymer_id.code: profile for profile in materials}
        self.assertEqual(set(by_polymer), {"HDPE", "LDPE", "PP"})
        self.assertEqual(by_polymer["PP"], existing_pp)
        self.assertEqual(by_polymer["HDPE"].id, provisional_ids["HDPE"])
        self.assertEqual(by_polymer["LDPE"].id, provisional_ids["LDPE"])
        self.assertEqual(by_polymer["HDPE"].facility_profile_id, existing_facility)
        self.assertIn("PP Supersacs", existing_pp.freeform_notes or "")
        self.assertEqual((existing_pp.freeform_notes or "").splitlines().count("PP Supersacs"), 1)
        orch._upsert_lead(self.connection, dto)
        self.assertEqual(self.env["plasticos.material.profile"].search_count([("partner_id", "=", location.id)]), 3)
        self.assertEqual(self.env["plasticos.facility.profile"].search_count([("partner_id", "=", location.id)]), 1)
        self.assertEqual(lead.facility_profile_id, existing_facility)

    def test_standalone_company_facility_is_reused_and_replays(self):
        company = self.env["res.partner"].create({"name": "Standalone Mill", "is_company": True})
        self.assertTrue(company.is_facility)
        partners_before = self.env["res.partner"].search_count([])
        orch = SyncOrchestrator(self.env)
        dto = self._lead("vs-standalone", custom_fields={"Materials": "HDPE Drums"})
        lead = orch._upsert_lead(self.connection, dto)
        lead.partner_id = company
        orch._upsert_lead(self.connection, dto)
        self.assertEqual(self.env["res.partner"].search_count([]), partners_before)
        self.assertFalse(company.child_ids.filtered("is_company"))
        profiles = self._profiles(company)
        self.assertEqual(len(profiles), 1)
        self.assertEqual(profiles.polymer_id.code, "HDPE")
        self.assertEqual(profiles.form_id.code, "DRUMS")
        self.assertEqual(lead.facility_profile_id.partner_id, company)
        profile_id = profiles.id
        facility_id = lead.facility_profile_id.id
        orch._upsert_lead(self.connection, dto)
        self.assertEqual(self._profiles(company).id, profile_id)
        self.assertEqual(lead.facility_profile_id.id, facility_id)
        self.assertEqual(self.env["plasticos.facility.profile"].search_count([("partner_id", "=", company.id)]), 1)

    def test_two_leads_keep_provenance_on_one_verified_facility(self):
        location = self._facility("Shared Mill")
        orch = SyncOrchestrator(self.env)
        first_dto = self._lead("vs-share-a", custom_fields={"Materials": "HDPE Drums\nLDPE Film"})
        second_dto = self._lead("vs-share-b", custom_fields={"Materials": "PP Supersacs"})
        first = orch._upsert_lead(self.connection, first_dto)
        second = orch._upsert_lead(self.connection, second_dto)
        first_facility = self.env["plasticos.facility.profile"].search([("crm_lead_id", "=", first.id)])
        second_facility = self.env["plasticos.facility.profile"].search([("crm_lead_id", "=", second.id)])
        self.assertEqual(len(first_facility), 1)
        self.assertEqual(len(second_facility), 1)
        self.assertNotEqual(first_facility, second_facility)
        first.partner_id = location
        orch._upsert_lead(self.connection, first_dto)
        shared = self.env["plasticos.facility.profile"].search([("partner_id", "=", location.id)])
        self.assertEqual(len(shared), 1)
        self.assertEqual(shared.crm_lead_id, first)
        self.assertEqual(first.facility_profile_id, shared)
        second.partner_id = location
        orch._upsert_lead(self.connection, second_dto)
        self.assertFalse(second_facility.exists())
        shared = self.env["plasticos.facility.profile"].search([("partner_id", "=", location.id)])
        self.assertEqual(len(shared), 1)
        self.assertEqual(shared.crm_lead_id, first)
        self.assertEqual(first.facility_profile_id, shared)
        self.assertEqual(second.facility_profile_id, shared)
        self.assertEqual(set(shared.associated_lead_ids), {first, second})
        self.assertEqual(first.partner_id, location)
        self.assertEqual(second.partner_id, location)
        materials = self.env["plasticos.material.profile"].search([("partner_id", "=", location.id)])
        self.assertEqual({profile.polymer_id.code for profile in materials}, {"HDPE", "LDPE", "PP"})
        ids = {profile.polymer_id.code: profile.id for profile in materials}
        orch._upsert_lead(self.connection, first_dto)
        orch._upsert_lead(self.connection, second_dto)
        replayed = self.env["plasticos.material.profile"].search([("partner_id", "=", location.id)])
        self.assertEqual({profile.polymer_id.code: profile.id for profile in replayed}, ids)
        self.assertEqual(self.env["plasticos.facility.profile"].search_count([("partner_id", "=", location.id)]), 1)
        self.assertEqual(shared.crm_lead_id, first)
        self.assertEqual(second.facility_profile_id, shared)

    def test_material_collision_merges_evidence_and_keeps_downstream_refs(self):
        location = self._facility("Collision Mill")
        existing_facility = self.env["plasticos.facility.profile"].create({"partner_id": location.id})
        hdpe = self.env["plasticos.polymer"].search([("code", "=", "HDPE")], limit=1)
        drums = self.env["plasticos.material.form"].search([("code", "=", "DRUMS")], limit=1)
        source = self.env["plasticos.source.type"].search([("code", "=", "POST_INDUSTRIAL")], limit=1)
        existing = self.env["plasticos.material.profile"].create(
            {
                "partner_id": location.id,
                "facility_profile_id": existing_facility.id,
                "polymer_id": hdpe.id,
                "form_id": drums.id,
                "freeform_notes": "already there",
            }
        )
        orch = SyncOrchestrator(self.env)
        dto = self._lead("vs-collision", custom_fields={"Materials": "HDPE Drums"})
        lead = orch._upsert_lead(self.connection, dto)
        provisional = self.env["plasticos.material.profile"].search([("facility_profile_id.crm_lead_id", "=", lead.id)])
        self.assertEqual(len(provisional), 1)
        provisional.source_type_id = source
        intake = self.env["plasticos.intake"].create(
            {
                "partner_id": location.id,
                "facility_id": location.id,
                "polymer_id": hdpe.id,
                "form_id": drums.id,
                "quantity_per_load_lbs": 1000,
                "material_profile_id": provisional.id,
            }
        )
        lead.partner_id = location
        orch._upsert_lead(self.connection, dto)
        self.assertFalse(provisional.exists())
        self.assertEqual(intake.material_profile_id, existing)
        self.assertEqual(existing.source_type_id, source)
        self.assertIn("already there", existing.freeform_notes)
        self.assertIn("HDPE Drums", existing.freeform_notes)
        self.assertEqual(self.env["plasticos.material.profile"].search_count([("partner_id", "=", location.id)]), 1)
        orch._upsert_lead(self.connection, dto)
        self.assertEqual(intake.material_profile_id, existing)
        self.assertEqual(self.env["plasticos.material.profile"].search_count([("partner_id", "=", location.id)]), 1)

    def test_conflicting_grade_keeps_both_material_profiles(self):
        location = self._facility("Grade Conflict")
        existing_facility = self.env["plasticos.facility.profile"].create({"partner_id": location.id})
        ldpe = self.env["plasticos.polymer"].search([("code", "=", "LDPE")], limit=1)
        film = self.env["plasticos.material.form"].search([("code", "=", "FILM")], limit=1)
        existing = self.env["plasticos.material.profile"].create(
            {
                "partner_id": location.id,
                "facility_profile_id": existing_facility.id,
                "polymer_id": ldpe.id,
                "form_id": film.id,
                "sub_grade": "C",
            }
        )
        orch = SyncOrchestrator(self.env)
        orch.outcomes = _new_outcomes()
        dto = self._lead("vs-grade-conflict", custom_fields={"Materials": "LDPE Film A"})
        lead = orch._upsert_lead(self.connection, dto)
        provisional_facility = self.env["plasticos.facility.profile"].search([("crm_lead_id", "=", lead.id)])
        provisional = self.env["plasticos.material.profile"].search(
            [("facility_profile_id", "=", provisional_facility.id)]
        )
        self.assertEqual(provisional.sub_grade, "A")
        lead.partner_id = location
        orch._upsert_lead(self.connection, dto)
        self.assertTrue(provisional.exists())
        self.assertTrue(provisional_facility.exists())
        self.assertEqual(existing.sub_grade, "C")
        self.assertEqual(provisional.sub_grade, "A")
        self.assertTrue(any("cannot be combined" in row["message"] for row in orch.error_rows))
        self.assertEqual(orch.outcomes["failed"], 0)
        self.assertEqual(lead.partner_id, location)

    def test_collision_preserves_followers_without_duplicate_subscriptions(self):
        from odoo import fields

        location = self._facility("Follower Mill")
        existing_facility = self.env["plasticos.facility.profile"].create({"partner_id": location.id})
        hdpe = self.env["plasticos.polymer"].search([("code", "=", "HDPE")], limit=1)
        drums = self.env["plasticos.material.form"].search([("code", "=", "DRUMS")], limit=1)
        existing = self.env["plasticos.material.profile"].create(
            {
                "partner_id": location.id,
                "facility_profile_id": existing_facility.id,
                "polymer_id": hdpe.id,
                "form_id": drums.id,
            }
        )
        comment = self.env.ref("mail.mt_comment")
        note = self.env.ref("mail.mt_note")
        shared = self.env["res.partner"].create({"name": "Shared Follower"})
        only_provisional = self.env["res.partner"].create({"name": "Provisional Only Follower"})
        unrelated = self.env["res.partner"].create({"name": "Facility Follower"})
        Follower = self.env["mail.followers"]
        survivor_follow = Follower.create(
            {
                "res_model": "plasticos.material.profile",
                "res_id": existing.id,
                "partner_id": shared.id,
                "subtype_ids": [fields.Command.link(comment.id)],
            }
        )
        facility_follow = Follower.create(
            {
                "res_model": "plasticos.facility.profile",
                "res_id": existing_facility.id,
                "partner_id": unrelated.id,
                "subtype_ids": [fields.Command.link(comment.id)],
            }
        )
        orch = SyncOrchestrator(self.env)
        dto = self._lead("vs-followers", custom_fields={"Materials": "HDPE Drums"})
        lead = orch._upsert_lead(self.connection, dto)
        provisional = self.env["plasticos.material.profile"].search([("facility_profile_id.crm_lead_id", "=", lead.id)])
        moved = Follower.create(
            {
                "res_model": "plasticos.material.profile",
                "res_id": provisional.id,
                "partner_id": only_provisional.id,
                "subtype_ids": [fields.Command.link(comment.id)],
            }
        )
        duplicate = Follower.create(
            {
                "res_model": "plasticos.material.profile",
                "res_id": provisional.id,
                "partner_id": shared.id,
                "subtype_ids": [fields.Command.link(note.id)],
            }
        )
        mails_before = self.env["mail.mail"].search_count([])
        survivor_id = existing.id
        lead.partner_id = location
        orch._upsert_lead(self.connection, dto)
        self.assertFalse(provisional.exists())
        self.assertFalse(duplicate.exists())
        self.assertTrue(existing.exists())
        self.assertEqual(existing.id, survivor_id)
        self.assertEqual(survivor_follow.res_id, existing.id)
        self.assertEqual(set(survivor_follow.subtype_ids), {comment, note})
        self.assertEqual(moved.res_id, existing.id)
        self.assertEqual(moved.subtype_ids, comment)
        on_survivor = Follower.search([("res_model", "=", "plasticos.material.profile"), ("res_id", "=", existing.id)])
        self.assertEqual(set(on_survivor.partner_id), {shared, only_provisional})
        self.assertEqual(len(on_survivor.filtered(lambda row: row.partner_id == shared)), 1)
        self.assertEqual(facility_follow.res_id, existing_facility.id)
        self.assertEqual(facility_follow.subtype_ids, comment)
        self.assertEqual(self.env["mail.mail"].search_count([]), mails_before)
        orch._upsert_lead(self.connection, dto)
        replayed = Follower.search([("res_model", "=", "plasticos.material.profile"), ("res_id", "=", existing.id)])
        self.assertEqual(set(replayed), set(on_survivor))
        self.assertEqual(self.env["plasticos.material.profile"].search_count([("partner_id", "=", location.id)]), 1)

    def test_scheduled_message_blocks_material_deletion(self):
        from odoo import fields

        location = self._facility("Scheduled Mill")
        existing_facility = self.env["plasticos.facility.profile"].create({"partner_id": location.id})
        hdpe = self.env["plasticos.polymer"].search([("code", "=", "HDPE")], limit=1)
        drums = self.env["plasticos.material.form"].search([("code", "=", "DRUMS")], limit=1)
        existing = self.env["plasticos.material.profile"].create(
            {
                "partner_id": location.id,
                "facility_profile_id": existing_facility.id,
                "polymer_id": hdpe.id,
                "form_id": drums.id,
            }
        )
        orch = SyncOrchestrator(self.env)
        orch.outcomes = _new_outcomes()
        dto = self._lead("vs-scheduled", custom_fields={"Materials": "HDPE Drums"})
        lead = orch._upsert_lead(self.connection, dto)
        provisional = self.env["plasticos.material.profile"].search([("facility_profile_id.crm_lead_id", "=", lead.id)])
        scheduled = self.env["mail.scheduled.message"].create(
            {
                "model": "plasticos.material.profile",
                "res_id": provisional.id,
                "author_id": self.env.user.partner_id.id,
                "scheduled_date": fields.Datetime.add(fields.Datetime.now(), days=1),
                "body": "keep this note",
            }
        )
        lead.partner_id = location
        orch._upsert_lead(self.connection, dto)
        self.assertTrue(provisional.exists())
        self.assertEqual(existing.partner_id, location)
        self.assertEqual(scheduled.res_id, provisional.id)
        self.assertTrue(any("cannot be moved" in row["message"] for row in orch.error_rows))
        self.assertEqual(orch.outcomes["failed"], 0)

    def test_verified_partner_without_facility_profile_attaches_canonical_materials(self):
        company = self.env["res.partner"].create({"name": "Canonical Mill", "is_company": True})
        self.assertTrue(company.is_facility)
        hdpe = self.env["plasticos.polymer"].search([("code", "=", "HDPE")], limit=1)
        drums = self.env["plasticos.material.form"].search([("code", "=", "DRUMS")], limit=1)
        existing = self.env["plasticos.material.profile"].create(
            {
                "partner_id": company.id,
                "polymer_id": hdpe.id,
                "form_id": drums.id,
                "freeform_notes": "already canonical",
            }
        )
        partners_before = self.env["res.partner"].search_count([])
        orch = SyncOrchestrator(self.env)
        lead = orch._upsert_lead(self.connection, self._lead("vs-canonical"))
        lead.partner_id = company
        self.assertFalse(self.env["plasticos.facility.profile"].search([("partner_id", "=", company.id)]))
        orch._upsert_lead(self.connection, self._lead("vs-canonical", custom_fields={"Materials": "HDPE Drums"}))
        facility = lead.facility_profile_id
        self.assertEqual(facility.partner_id, company)
        self.assertEqual(facility.crm_lead_id, lead)
        self.assertEqual(existing.facility_profile_id, facility)
        self.assertEqual(existing.partner_id, company)
        self.assertIn("already canonical", existing.freeform_notes or "")
        self.assertIn("HDPE Drums", existing.freeform_notes or "")
        self.assertFalse(company.child_ids)
        self.assertEqual(self.env["res.partner"].search_count([]), partners_before)
        visible = self.env["plasticos.material.profile"].search(lead.action_view_material_profiles()["domain"])
        self.assertIn(existing, visible)
        self.assertEqual(lead.material_profile_count, 1)
        material_id = existing.id
        facility_id = facility.id
        orch._upsert_lead(self.connection, self._lead("vs-canonical", custom_fields={"Materials": "HDPE Drums"}))
        self.assertEqual(existing.id, material_id)
        self.assertEqual(lead.facility_profile_id.id, facility_id)
        self.assertEqual(self.env["plasticos.facility.profile"].search_count([("partner_id", "=", company.id)]), 1)
        second = orch._upsert_lead(self.connection, self._lead("vs-canonical-b"))
        second.partner_id = company
        orch._upsert_lead(self.connection, self._lead("vs-canonical-b", custom_fields={"Materials": "LDPE Film"}))
        self.assertEqual(second.facility_profile_id, facility)
        self.assertEqual(facility.crm_lead_id, lead)
        self.assertIn(second, facility.associated_lead_ids)
        self.assertEqual(self.env["plasticos.facility.profile"].search_count([("partner_id", "=", company.id)]), 1)
        self.assertFalse(company.child_ids)

    def test_lead_owned_materials_are_visible_from_the_crm_action(self):
        lead = SyncOrchestrator(self.env)._upsert_lead(
            self.connection, self._lead("vs-nav", custom_fields={"Materials": "PP Supersacs"})
        )
        self.assertFalse(lead.partner_id)
        profile = self.env["plasticos.material.profile"].search([("facility_profile_id.crm_lead_id", "=", lead.id)])
        self.assertEqual(len(profile), 1)
        visible = self.env["plasticos.material.profile"].search(lead.action_view_material_profiles()["domain"])
        self.assertEqual(visible, profile)
        self.assertEqual(lead.material_profile_count, 1)


@tagged("post_install", "-at_install", "-standard", "crm_sync_semantic_kernel")
class TestCrmSyncSemanticKernelCollision(CrmSyncOrchestratorCase):
    """Collision cases on plasticos_semantic_kernel models.

    plasticos_crm_sync does not depend on that optional module, so the standard
    run excludes these. Run them on a clone with it installed:
    ``-i plasticos_semantic_kernel -u plasticos_crm_sync --test-tags crm_sync_semantic_kernel``.
    """

    def test_collision_keeps_cascade_dependents_and_image_attachments(self):
        from odoo import fields

        location = self._facility("Cascade Mill")
        existing_facility = self.env["plasticos.facility.profile"].create({"partner_id": location.id})
        hdpe = self.env["plasticos.polymer"].search([("code", "=", "HDPE")], limit=1)
        drums = self.env["plasticos.material.form"].search([("code", "=", "DRUMS")], limit=1)
        existing = self.env["plasticos.material.profile"].create(
            {
                "partner_id": location.id,
                "facility_profile_id": existing_facility.id,
                "polymer_id": hdpe.id,
                "form_id": drums.id,
            }
        )
        orch = SyncOrchestrator(self.env)
        dto = self._lead("vs-cascade", custom_fields={"Materials": "HDPE Drums"})
        lead = orch._upsert_lead(self.connection, dto)
        provisional = self.env["plasticos.material.profile"].search([("facility_profile_id.crm_lead_id", "=", lead.id)])
        observation = self.env["plasticos.material.observation"].create(
            {
                "material_profile_id": provisional.id,
                "feature_id": "moisture",
                "value_state": "observed",
                "method": "scale",
                "observed_at": fields.Datetime.now(),
                "source_system": "crm-sync-test",
            }
        )
        specification = self.env["plasticos.material.specification"].create(
            {
                "name": "Cascade spec",
                "polymer_id": hdpe.id,
                "form_id": drums.id,
                "legacy_material_profile_id": provisional.id,
            }
        )
        supply = self.env["plasticos.supply.opportunity"].create(
            {
                "name": "Cascade supply",
                "material_profile_id": provisional.id,
                "supplier_partner_id": location.id,
            }
        )
        image = self.env["ir.attachment"].create(
            {
                "name": "bale.png",
                "res_model": "plasticos.material.profile",
                "res_id": provisional.id,
                "mimetype": "image/png",
                "datas": base64.b64encode(b"bale-image"),
            }
        )
        lead.partner_id = location
        orch._upsert_lead(self.connection, dto)
        self.assertFalse(provisional.exists())
        self.assertTrue(observation.exists())
        self.assertEqual(observation.material_profile_id, existing)
        self.assertEqual(specification.legacy_material_profile_id, existing)
        self.assertEqual(supply.material_profile_id, existing)
        self.assertEqual(image.res_model, "plasticos.material.profile")
        self.assertEqual(image.res_id, existing.id)
        self.assertEqual(image.datas, base64.b64encode(b"bale-image"))

    def test_computed_material_reference_blocks_deletion(self):
        from odoo import fields

        location = self._facility("Computed Mill")
        existing_facility = self.env["plasticos.facility.profile"].create({"partner_id": location.id})
        hdpe = self.env["plasticos.polymer"].search([("code", "=", "HDPE")], limit=1)
        drums = self.env["plasticos.material.form"].search([("code", "=", "DRUMS")], limit=1)
        existing = self.env["plasticos.material.profile"].create(
            {
                "partner_id": location.id,
                "facility_profile_id": existing_facility.id,
                "polymer_id": hdpe.id,
                "form_id": drums.id,
            }
        )
        orch = SyncOrchestrator(self.env)
        orch.outcomes = _new_outcomes()
        dto = self._lead("vs-computed", custom_fields={"Materials": "HDPE Drums"})
        lead = orch._upsert_lead(self.connection, dto)
        provisional = self.env["plasticos.material.profile"].search([("facility_profile_id.crm_lead_id", "=", lead.id)])
        observation = self.env["plasticos.material.observation"].create(
            {
                "material_profile_id": provisional.id,
                "feature_id": "weight",
                "value_state": "reported",
                "method": "ticket",
                "observed_at": fields.Datetime.now(),
                "source_system": "crm-sync-test",
            }
        )
        transaction = self.env["plasticos.transaction"].create({"name": "TX-COMPUTED"})
        self.env.cr.execute(
            "UPDATE plasticos_transaction SET supplier_profile_id = %s WHERE id = %s",
            (provisional.id, transaction.id),
        )
        transaction.invalidate_recordset(["supplier_profile_id"])
        comment = self.env.ref("mail.mt_comment")
        survivor_partner = self.env["res.partner"].create({"name": "Computed Survivor Follower"})
        provisional_partner = self.env["res.partner"].create({"name": "Computed Provisional Follower"})
        survivor_follow = self.env["mail.followers"].create(
            {
                "res_model": "plasticos.material.profile",
                "res_id": existing.id,
                "partner_id": survivor_partner.id,
                "subtype_ids": [fields.Command.link(comment.id)],
            }
        )
        provisional_follow = self.env["mail.followers"].create(
            {
                "res_model": "plasticos.material.profile",
                "res_id": provisional.id,
                "partner_id": provisional_partner.id,
                "subtype_ids": [fields.Command.link(comment.id)],
            }
        )
        lead.partner_id = location
        orch._upsert_lead(self.connection, dto)
        self.assertTrue(provisional.exists())
        self.assertEqual(observation.material_profile_id, provisional)
        self.assertEqual(survivor_follow.res_id, existing.id)
        self.assertEqual(survivor_follow.subtype_ids, comment)
        self.assertEqual(provisional_follow.res_id, provisional.id)
        self.assertTrue(any("cannot be moved" in row["message"] for row in orch.error_rows))
        self.assertEqual(orch.outcomes["failed"], 0)
        self.env.cr.execute("SELECT supplier_profile_id FROM plasticos_transaction WHERE id = %s", (transaction.id,))
        self.assertEqual(self.env.cr.fetchone()[0], provisional.id)
