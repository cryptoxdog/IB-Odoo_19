"""TransactionCase: lead upsert idempotency + orphan resolve (requires Odoo runtime)."""

import importlib.util
import inspect
from pathlib import Path
from unittest.mock import MagicMock, patch

from odoo import Command, fields
from odoo.addons.plasticos_crm_sync.adapters.base import (
    EXCLUDED_SOURCE_FIELDS,
    CanonicalCall,
    CanonicalLead,
    CanonicalTableRow,
)
from odoo.addons.plasticos_crm_sync.adapters.vanillasoft.adapter import contact_to_canonical
from odoo.addons.plasticos_crm_sync.services.import_summary import (
    OPTIONAL_CONTEXT,
    REQUIRED_MAPPING,
    build_run_summary,
    business_acceptance,
)
from odoo.addons.plasticos_crm_sync.services.orchestrator import (
    SyncOrchestrator,
    _material_inputs,
    _new_outcomes,
    _parse_material_sections,
)
from odoo.addons.plasticos_crm_sync.services.owner_crosswalk import BLANK_OWNER_LOGIN, OWNER_LOGIN_BY_SOURCE
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

    def setUp(self):
        super().setUp()
        self._ensure_mapped_salespeople()

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

    def _ensure_salesperson(self, login):
        users = self.env["res.users"].with_context(no_reset_password=True)
        user = users.search([("login", "=ilike", login)], limit=1)
        internal = self.env.ref("base.group_user")
        salesman = self.env.ref("sales_team.group_sale_salesman")
        if not user:
            user = users.create(
                {
                    "name": login,
                    "login": login,
                    "email": login,
                    "group_ids": [Command.set([internal.id, salesman.id])],
                }
            )
        elif user.share or not user.has_group("sales_team.group_sale_salesman"):
            user.write({"group_ids": [Command.link(internal.id), Command.link(salesman.id)]})
        return user

    def _ensure_mapped_salespeople(self):
        for login in set(OWNER_LOGIN_BY_SOURCE.values()):
            self._ensure_salesperson(login)


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
        self.assertEqual(vals["stage_id"], self.env.ref("plasticos_crm_bridge.stage_new").id)

    def test_contact_name_collapses_whitespace(self):
        orch = SyncOrchestrator(self.env)
        spaced = orch._lead_vals_from_dto(self._lead("vs-name", first_name="  Ada   ", last_name=" \n Lovelace  "))
        self.assertEqual(spaced["contact_name"], "Ada Lovelace")
        blank = orch._lead_vals_from_dto(self._lead("vs-blank", first_name="   ", last_name="\t"))
        self.assertFalse(blank["contact_name"])

    def test_unmapped_source_falls_back_to_other_and_keeps_the_source_text(self):
        self._ensure_mapped_salespeople()
        orch = SyncOrchestrator(self.env)
        missing_source = orch._lead_vals_from_dto(self._lead("vs-source", lead_source_raw="Not A Mapped Source"))
        self.assertEqual(missing_source["source_id"], self.env.ref("plasticos_crm_bridge.utm_source_other").id)
        lead = orch._upsert_lead(self.connection, self._lead("vs-source", lead_source_raw="Not A Mapped Source"))
        self.assertIn("VanillaSoft Lead Source: Not A Mapped Source", lead.description)
        blank = orch._lead_vals_from_dto(self._lead("vs-blank-source", lead_source_raw=""))
        self.assertFalse(blank["source_id"])
        mapped = orch._lead_vals_from_dto(self._lead("vs-google", lead_source_raw="Google"))
        self.assertEqual(mapped["source_id"], self.env.ref("plasticos_crm_bridge.utm_source_google").id)
        self.assertEqual(self.env["res.users"].browse(mapped["user_id"]).login, BLANK_OWNER_LOGIN)

    def test_extra_numbers_and_notes_persist_in_the_description_and_replay(self):
        self._ensure_salesperson("ib@scrapmanagement.com")
        raw = {
            "contact_id": "vs-phone-fidelity",
            "company": "Synthetic Co",
            "first_name": "Ada",
            "last_name": "Byron",
            "state": "Pennsylvania",
            "country": "USA",
            "contact_owner": "ibeylin@ucsincny.com",
            "custom_fields": [{"name": "Notes", "value": "synthetic note"}],
            "phone_numbers": [
                {"name": "direct", "number": "555-100-0001"},
                {"name": "mobile 1", "number": "+44 7700 900123"},
                {"name": "mobile 2", "number": "555-100-0002"},
                {"name": "fax", "number": "555-100-0003"},
            ],
        }
        orch = SyncOrchestrator(self.env)
        orch.outcomes = _new_outcomes()
        lead = orch._upsert_lead(self.connection, contact_to_canonical(raw))
        self.assertEqual(orch.last_lead_outcome, "created")
        self.assertEqual(lead.phone, "555-100-0001")
        self.assertEqual(lead.mobile, "555-100-0002", "the valid second mobile fills the field the first cannot")
        self.assertEqual(lead.state_id.code, "PA")
        for line in (
            "VanillaSoft ContactID vs-phone-fidelity Notes: synthetic note",
            "VanillaSoft phone (mobile 1): +44 7700 900123",
            "VanillaSoft phone (fax): 555-100-0003",
        ):
            self.assertIn(line, lead.description)
        self.assertNotIn("555-100-0002", lead.description)
        stored = lead.description
        again = orch._upsert_lead(self.connection, contact_to_canonical(raw))
        self.assertEqual(again, lead)
        self.assertEqual(orch.last_lead_outcome, "unchanged")
        self.assertEqual(lead.description, stored)

    def test_locked_owner_emails_persist_on_the_lead_and_replay(self):
        self._ensure_mapped_salespeople()
        orch = SyncOrchestrator(self.env)
        orch.outcomes = _new_outcomes()
        for source, login in OWNER_LOGIN_BY_SOURCE.items():
            external_id = "vs-owner-" + source.split("@", 1)[0]
            dto = self._lead(external_id, owner_name=f"  {source.upper()}  ")
            lead = orch._upsert_lead(self.connection, dto)
            self.assertEqual(orch.last_lead_outcome, "created", source)
            self.assertEqual(lead.user_id.login, login, source)
            again = orch._upsert_lead(self.connection, dto)
            self.assertEqual(again, lead)
            self.assertEqual(orch.last_lead_outcome, "unchanged", source)
            self.assertEqual(again.user_id.login, login, source)

    def test_blank_owner_falls_back_to_mack(self):
        self._ensure_salesperson(BLANK_OWNER_LOGIN)
        orch = SyncOrchestrator(self.env)
        for owner_name in ("", "   ", "False", "[blank / no owner]"):
            external_id = "vs-blank-" + (owner_name.strip() or "empty")
            lead = orch._upsert_lead(self.connection, self._lead(external_id, owner_name=owner_name))
            self.assertEqual(lead.user_id.login, BLANK_OWNER_LOGIN, owner_name)

    def test_unresolved_owner_does_not_clear_an_existing_salesperson(self):
        self._ensure_salesperson("lm@scrapmanagement.com")
        orch = SyncOrchestrator(self.env)
        orch.outcomes = _new_outcomes()
        dto = self._lead("vs-owner-keep", owner_name="lm@ucsincny.com")
        lead = orch._upsert_lead(self.connection, dto)
        self.assertEqual(lead.user_id.login, "lm@scrapmanagement.com")
        kept = orch._upsert_lead(self.connection, self._lead("vs-owner-keep", owner_name="CRM3 Exact Owner"))
        self.assertEqual(kept, lead)
        self.assertEqual(orch.last_lead_outcome, "failed")
        self.assertEqual(orch.outcomes["failed"], 1)
        self.assertEqual(lead.user_id.login, "lm@scrapmanagement.com")
        self.assertFalse(
            orch._upsert_lead(self.connection, self._lead("vs-owner-new-bad", owner_name="No Such CRM3 Owner"))
        )

    def test_observed_aliases_land_on_native_lead_fields(self):
        self._ensure_salesperson("ib@scrapmanagement.com")
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
                "contact_owner": "ibeylin@ucsincny.com",
                "phone_numbers": [
                    {"name": "business", "number": "555-100-0003"},
                    {"name": "direct", "number": "555-100-0001"},
                    {"name": "mobile 1", "number": "555-100-0002"},
                ],
            }
        )
        lead = SyncOrchestrator(self.env)._upsert_lead(self.connection, dto)
        self.assertEqual(lead.name, "Alias Co — Ada Lovelace")
        self.assertEqual(lead.partner_name, "Alias Co")
        self.assertEqual(lead.contact_name, "Ada Lovelace")
        self.assertEqual(lead.street, "9 Observed St")
        self.assertEqual(lead.city, "Atlanta")
        self.assertEqual(lead.zip, "30301")
        self.assertEqual(lead.phone, "555-100-0001")
        self.assertEqual(lead.mobile, "555-100-0002")
        self.assertEqual(lead.country_id.code, "US")
        self.assertEqual(lead.state_id.code, "GA")
        self.assertEqual(lead.stage_id, self.env.ref("plasticos_crm_bridge.stage_new"))
        self.assertIn("VanillaSoft ContactID vs-alias-land Lead Status: 5=Dead Lead", lead.description or "")
        self.assertEqual(lead.source_id, self.env.ref("plasticos_crm_bridge.utm_source_google"))
        self.assertEqual(lead.user_id.login, "ib@scrapmanagement.com")
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

    def test_comma_separated_material_phrases_split_and_hints_do_not(self):
        phrases, hints, _weak = _material_inputs({"Materials": "LDPE, HDPE Drums", "Material Form": "Roll, Film"})
        self.assertEqual(phrases, ["LDPE", "HDPE Drums"])
        self.assertEqual(hints["material form"], "Roll, Film")

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

        def wrapped(env, description, grade_evidence=None, structured=None, *, crm_aliases=False):
            calls.append(description)
            return original(
                env,
                description,
                grade_evidence=grade_evidence,
                structured=structured,
                crm_aliases=crm_aliases,
            )

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
        self.assertEqual(profiles["HDPE"].material_grade_id.code, "DRUMS")
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
        status, excerpt = orch._completion(
            self.env["plasticos.crm.sync.run"].new(
                {
                    "connection_id": self.connection.id,
                    "contacts_seen": 1,
                    "contacts_created": 1,
                    "contacts_failed": 0,
                    "calls_failed": 0,
                }
            ),
            [],
        )
        self.assertEqual(status, "partial")
        self.assertIn("not a polymer", excerpt)
        self.assertIn("required mapping", excerpt)

    def test_completion_excerpt_drops_credential_values(self):
        orch = SyncOrchestrator(self.env)
        orch.error_rows.append(
            {
                "record_ref": "vs-secret",
                "message": "VanillaSoft HTTP 401 password=hunter2",
                "category": "required_mapping",
            }
        )
        status, excerpt = orch._completion(
            self.env["plasticos.crm.sync.run"].new(
                {
                    "connection_id": self.connection.id,
                    "contacts_seen": 1,
                    "contacts_failed": 1,
                    "calls_failed": 0,
                }
            ),
            [],
        )
        self.assertEqual(status, "failed")
        self.assertIn("vs-secret", excerpt)
        self.assertIn("HTTP 401", excerpt)
        self.assertNotIn("hunter2", excerpt)
        self.assertNotIn("password=", excerpt.casefold())

    def test_material_only_failure_is_persisted_partial_and_replay_preserves_erp_values(self):
        """MAT-STATUS-01. The contact and the recognized profile stay. The unresolved
        material keeps the stored run partial, and a second import does not hide that.
        """
        facility = self._facility("Status Mill")
        facility.comment = "ERP-OWNED-SENTINEL"
        other = self._facility("Untouched Mill")
        other.comment = "ERP-OTHER"
        orch = SyncOrchestrator(self.env)
        orch.outcomes = _new_outcomes()
        lead = orch._upsert_lead(self.connection, self._lead("vs-status-mat"))
        lead.partner_id = facility
        orch._upsert_lead(
            self.connection,
            self._lead("vs-status-mat", custom_fields={"Materials": "Pallets\nnot a polymer"}),
        )
        self.assertEqual(orch.outcomes["failed"], 0)
        profiles = self._profiles(facility)
        self.assertEqual(profiles.polymer_id.code, "PLASTIC_PALLETS")
        profile_id = profiles.id
        self.assertIn("ERP-OWNED-SENTINEL", facility.comment or "")
        self.assertIn("ERP-OTHER", other.comment or "")
        self.assertFalse(self.connection.last_success_at)

        run = self.env["plasticos.crm.sync.run"].create(
            {
                "connection_id": self.connection.id,
                "kind": "incremental",
                "contacts_seen": 1,
                "contacts_created": 1,
                "contacts_upserted": 1,
                "contacts_failed": 0,
                "calls_failed": 0,
            }
        )
        status, excerpt = orch._completion(run, [])
        self.assertEqual(status, "partial")
        run.write({"status": status, "error_excerpt": excerpt or False, "finished_at": fields.Datetime.now()})
        stored = self.env["plasticos.crm.sync.run"].browse(run.id)
        stored.invalidate_recordset()
        self.assertEqual(stored.status, "partial")
        self.assertIn("not a polymer", stored.error_excerpt)
        self.assertEqual(stored.contacts_failed, 0)
        summary = build_run_summary(stored, error_rows=[dict(row) for row in orch.error_rows])
        self.assertEqual(summary["final_status"], stored.status)
        self.assertTrue(summary["errors"])
        self.assertEqual(business_acceptance(summary), "FAIL")

        leads_before = self.env["crm.lead"].search_count([("vanillasoft_id", "=", "vs-status-mat")])
        replay = SyncOrchestrator(self.env)
        replay.outcomes = _new_outcomes()
        again = replay._upsert_lead(
            self.connection,
            self._lead("vs-status-mat", custom_fields={"Materials": "Pallets\nnot a polymer"}),
        )
        self.assertEqual(again, lead)
        self.assertEqual(self.env["crm.lead"].search_count([("vanillasoft_id", "=", "vs-status-mat")]), leads_before)
        self.assertEqual(self._profiles(facility).id, profile_id)
        self.assertIn("ERP-OWNED-SENTINEL", facility.comment or "")
        self.assertIn("ERP-OTHER", other.comment or "")
        self.assertTrue(any("not a polymer" in row["message"] for row in replay.error_rows))
        status_again, excerpt_again = replay._completion(stored, [])
        self.assertEqual(status_again, "partial")
        self.assertIn("not a polymer", excerpt_again)
        self.assertEqual(stored.status, "partial")
        replay_summary = build_run_summary(stored, error_rows=[dict(row) for row in replay.error_rows])
        self.assertEqual(replay_summary["final_status"], "partial")
        self.assertEqual(business_acceptance(replay_summary), "FAIL")

    def _run_connection(self, connection, leads):
        """Production ``run_connection`` against this test cursor.

        The durable second cursor and ``commit`` are redirected so the audit
        row and ``last_success_at`` stay inside the test transaction. The
        completion write itself is the production method.
        """
        from datetime import UTC, datetime

        recent = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

        class _Adapter:
            def healthcheck(self):
                return True

            def iter_contacts(self, **_kwargs):
                yield leads, recent, False

            def iter_calls(self, **_kwargs):
                return iter(())

            def iter_table_rows(self, _contact_external_id):
                return iter(())

        self.env["ir.config_parameter"].sudo().set_param("plasticos_crm_sync.approved_contact_crosswalk", "")
        orch = SyncOrchestrator(self.env)
        orch._build_adapter = lambda _connection: _Adapter()
        orch._try_advisory_lock = lambda _key: True
        orch._advisory_unlock = lambda _key: None

        def create_run(connection_id, vals=None):
            run = self.env["plasticos.crm.sync.run"].create(
                {
                    "connection_id": connection_id,
                    "status": "running",
                    "started_at": fields.Datetime.now(),
                    **(vals or {}),
                }
            )
            return run.id

        orch._create_sync_run_durable = create_run
        original_commit = self.env.cr.commit
        self.env.cr.commit = lambda: None
        try:
            run = orch.run_connection(connection)
        finally:
            self.env.cr.commit = original_commit
        run.invalidate_recordset()
        connection.invalidate_recordset()
        return orch, run

    def test_run_connection_optional_context_succeeds_and_material_stays_partial(self):
        """F-310-01/02. The persisted run comes from ``run_connection``, not a manual write."""
        untouched = self.env["res.partner"].create(
            {"name": "ERP Untouched", "is_company": True, "comment": "ERP-OWNED"}
        )
        optional = self.env["plasticos.crm.connection"].create(
            {"name": "Optional VS", "provider": "vanillasoft", "project_id": "139705", "enabled": False}
        )
        lead = self._lead(
            "vs-opt-status",
            mobile="+44 7700 900123",
            country_code="Narnia",
            state_code="Atlantis",
            modified_utc="2026-10-26T12:00:00Z",
        )
        orch, run = self._run_connection(optional, [lead])
        self.assertEqual(run.status, "success")
        self.assertTrue(optional.last_success_at)
        self.assertTrue(orch.error_rows)
        self.assertTrue(all(row["category"] == OPTIONAL_CONTEXT for row in orch.error_rows))
        self.assertNotIn("required mapping", run.error_excerpt or "")
        stored_lead = self.env["crm.lead"].search([("vanillasoft_id", "=", "vs-opt-status")])
        self.assertEqual(len(stored_lead), 1)
        self.assertIn("Narnia", stored_lead.description or "")
        self.assertIn("+44 7700 900123", stored_lead.description or "")
        summary = build_run_summary(run, error_rows=[dict(row) for row in orch.error_rows])
        self.assertEqual(summary["final_status"], "success")
        self.assertEqual(business_acceptance(summary), "PASS")
        replay_orch, replay = self._run_connection(optional, [lead])
        self.assertEqual(replay.status, "success")
        self.assertEqual(self.env["crm.lead"].search_count([("vanillasoft_id", "=", "vs-opt-status")]), 1)
        self.assertTrue(all(row["category"] == OPTIONAL_CONTEXT for row in replay_orch.error_rows))
        self.assertEqual(run.status, "success")

        material = self.env["plasticos.crm.connection"].create(
            {"name": "Material VS", "provider": "vanillasoft", "project_id": "139706", "enabled": False}
        )
        missing = self._lead(
            "vs-mat-status-run",
            custom_fields={"Materials": "not a polymer"},
            modified_utc="2026-10-26T12:00:00Z",
        )
        mat_orch, mat_run = self._run_connection(material, [missing])
        self.assertEqual(mat_run.contacts_failed, 0)
        self.assertEqual(mat_run.status, "partial")
        self.assertFalse(material.last_success_at)
        self.assertTrue(
            any(
                row["category"] == REQUIRED_MAPPING and "not a polymer" in row["message"] for row in mat_orch.error_rows
            )
        )
        mat_summary = build_run_summary(mat_run, error_rows=[dict(row) for row in mat_orch.error_rows])
        self.assertEqual(mat_summary["final_status"], "partial")
        self.assertEqual(mat_summary["records_rejected"], 0)
        self.assertEqual(business_acceptance(mat_summary), "FAIL")
        self.assertIn("ERP-OWNED", untouched.comment or "")
        _replay_orch, replay_mat = self._run_connection(material, [missing])
        self.assertEqual(replay_mat.status, "partial")
        self.assertEqual(mat_run.status, "partial")
        self.assertFalse(material.last_success_at)
        self.assertEqual(self.env["crm.lead"].search_count([("vanillasoft_id", "=", "vs-mat-status-run")]), 1)
        self.assertIn("ERP-OWNED", untouched.comment or "")

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

        def wrapped(env, description, grade_evidence=None, structured=None, *, crm_aliases=False):
            calls.append(description)
            return original(
                env,
                description,
                grade_evidence=grade_evidence,
                structured=structured,
                crm_aliases=crm_aliases,
            )

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
        self.assertEqual(by_polymer["HDPE"].material_grade_id.code, "DRUMS")
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
        self.assertEqual(by_polymer["HDPE"].material_grade_id.code, "DRUMS")
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
        self.assertEqual(by_polymer["HDPE"].material_grade_id.code, "DRUMS")
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
        self.assertEqual(by_polymer["3_7_COMMINGLED_BOTTLES"].material_grade_id.code, "BOTTLES")
        self.assertFalse(by_polymer["3_7_COMMINGLED_BOTTLES"].source_type_id)
        self.assertEqual(by_polymer["1_7_COMMINGLED_BOTTLES"].material_grade_id.code, "BOTTLES")
        self.assertFalse(by_polymer["1_7_COMMINGLED_BOTTLES"].source_type_id)
        self.assertEqual(by_polymer["HDPE_HMW"].material_grade_id.code, "DRUMS")
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
        supersacs = self.env["plasticos.material.grade"].search([("code", "=", "SUPERACS")], limit=1)
        existing_pp = self.env["plasticos.material.profile"].create(
            {
                "partner_id": location.id,
                "polymer_id": pp.id,
                "material_grade_id": supersacs.id,
                "freeform_notes": "already there",
            }
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
        self.assertEqual(profiles.material_grade_id.code, "DRUMS")
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
        drums = self.env["plasticos.material.grade"].search([("code", "=", "DRUMS")], limit=1)
        source = self.env["plasticos.source.type"].search([("code", "=", "POST_INDUSTRIAL")], limit=1)
        existing = self.env["plasticos.material.profile"].create(
            {
                "partner_id": location.id,
                "facility_profile_id": existing_facility.id,
                "polymer_id": hdpe.id,
                "material_grade_id": drums.id,
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
                "form_id": self.env["plasticos.material.form"].search([("code", "=", "OTHER")], limit=1).id,
                "material_grade_id": drums.id,
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
        drums = self.env["plasticos.material.grade"].search([("code", "=", "DRUMS")], limit=1)
        existing = self.env["plasticos.material.profile"].create(
            {
                "partner_id": location.id,
                "facility_profile_id": existing_facility.id,
                "polymer_id": hdpe.id,
                "material_grade_id": drums.id,
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
        drums = self.env["plasticos.material.grade"].search([("code", "=", "DRUMS")], limit=1)
        existing = self.env["plasticos.material.profile"].create(
            {
                "partner_id": location.id,
                "facility_profile_id": existing_facility.id,
                "polymer_id": hdpe.id,
                "material_grade_id": drums.id,
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
        drums = self.env["plasticos.material.grade"].search([("code", "=", "DRUMS")], limit=1)
        existing = self.env["plasticos.material.profile"].create(
            {
                "partner_id": company.id,
                "polymer_id": hdpe.id,
                "material_grade_id": drums.id,
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

    def test_approved_contact_notes_append_to_the_erp_comment_and_replay(self):
        person = self.env["res.partner"].create(
            {"name": "ERP Person", "phone": "555-0100", "comment": "negotiate prices\nrequest PO"}
        )
        self.env["ir.model.data"].create(
            {
                "module": "plasticos_transaction",
                "name": "legacy_erp_contact_77",
                "model": "res.partner",
                "res_id": person.id,
                "noupdate": True,
            }
        )
        erp_comment = person.comment
        orch = SyncOrchestrator(self.env)
        orch._crosswalk = {"vs-n1": "77", "vs-n2": "77"}
        orch._crosswalk_ready = True
        first = self._lead("vs-n1", contact_note="CRM history & terms")
        second = self._lead("vs-n2", contact_note="second contact\nnote")
        leads_before = self.env["crm.lead"].with_context(active_test=False).search_count([])

        orch.outcomes = _new_outcomes()
        orch._upsert_lead(self.connection, first)
        orch._upsert_lead(self.connection, second)
        self.assertEqual(orch.outcomes["updated"], 2)
        appended = person.comment
        self.assertTrue(appended.startswith(erp_comment))
        self.assertIn("<p>VanillaSoft ContactID vs-n1 Notes: CRM history &amp; terms</p>", appended)
        self.assertIn("second contact", appended)

        orch.outcomes = _new_outcomes()
        orch._upsert_lead(self.connection, first)
        orch._upsert_lead(self.connection, second)
        self.assertEqual(orch.outcomes["unchanged"], 2)
        self.assertEqual(orch.outcomes["failed"], 0)
        self.assertEqual(person.comment, appended)
        self.assertEqual(person.phone, "555-0100")
        self.assertEqual(self.env["crm.lead"].with_context(active_test=False).search_count([]), leads_before)

    def test_shared_person_attributes_colliding_notes_and_keeps_erp_text(self):
        company = self.env["res.partner"].create({"name": "ERP Company", "is_company": True})
        country = self.env.ref("base.us")
        state = self.env["res.country.state"].search([("country_id", "=", country.id), ("code", "=", "PA")], limit=1)
        self.assertTrue(state)
        person = self.env["res.partner"].create(
            {
                "name": "ERP Person",
                "email": "erp-person@example.test",
                "phone": "555-0100",
                "mobile": "215-555-0140",
                "street": "1 ERP Way",
                "city": "Philadelphia",
                "zip": "19103",
                "state_id": state.id,
                "country_id": country.id,
                "parent_id": company.id,
                "comment": "<p>ERP manual</p><p>shared history</p>",
            }
        )
        self._erp_marker(person, "88")
        orch = SyncOrchestrator(self.env)
        orch._crosswalk = {"vs-a": "88", "vs-b": "88"}
        orch._crosswalk_ready = True
        leads_before = self.env["crm.lead"].with_context(active_test=False).search_count([])
        contact_a = self._lead(
            "vs-a",
            contact_note="shared history",
            email="crm@example.test",
            phone="999-555-0199",
            mobile="999-555-0188",
            street="9 CRM St",
            city="CRM City",
            zip="00000",
            state_code="NY",
            country_code="CA",
            owner_name="sa@scrapmanagement.com",
            lead_source_raw="Google",
            custom_fields={
                "Notes (MRP)": "mrp note",
                "Notes (LDPE)": "ldpe note",
                "Notes (HDPE)": "hdpe note",
                "Notes (PP)": "pp note",
                "Notes (PPS)": "PPS-PROFILE-ONLY",
                "Last Result Code": "LM",
                "Last Call Date": "2024-03-05 14:10",
            },
        )
        contact_b = self._lead("vs-b", contact_note="shared history")
        orch.outcomes = _new_outcomes()
        orch._upsert_lead(self.connection, contact_a)
        orch._upsert_lead(self.connection, contact_b)
        comment = person.comment or ""
        for line in (
            "ERP manual",
            ">shared history<",
            "VanillaSoft ContactID vs-a Notes: shared history",
            "VanillaSoft ContactID vs-a Notes (MRP): mrp note",
            "VanillaSoft ContactID vs-a Notes (LDPE): ldpe note",
            "VanillaSoft ContactID vs-a Notes (HDPE): hdpe note",
            "VanillaSoft ContactID vs-a Notes (PP): pp note",
            "VanillaSoft ContactID vs-a Last Result Code: LM",
            "VanillaSoft ContactID vs-a Last Call Date: 2024-03-05 14:10",
            "VanillaSoft ContactID vs-b Notes: shared history",
        ):
            self.assertIn(line, comment)
        self.assertNotIn("PPS-PROFILE-ONLY", comment)
        self.assertNotIn("Contact Owner", comment)
        self.assertNotIn("Lead Source", comment)
        self.assertNotIn("sa@scrapmanagement.com", comment)
        self.assertEqual(person.name, "ERP Person")
        self.assertEqual(person.parent_id, company)
        self.assertEqual(person.email, "erp-person@example.test")
        self.assertEqual(person.phone, "555-0100")
        self.assertEqual(person.mobile, "215-555-0140")
        self.assertEqual(person.street, "1 ERP Way")
        self.assertEqual(person.city, "Philadelphia")
        self.assertEqual(person.zip, "19103")
        self.assertEqual(person.state_id, state)
        self.assertEqual(person.country_id, country)
        self.assertEqual(self.env["crm.lead"].with_context(active_test=False).search_count([]), leads_before)
        stored = person.comment
        orch.outcomes = _new_outcomes()
        orch._upsert_lead(self.connection, contact_a)
        orch._upsert_lead(self.connection, contact_b)
        self.assertEqual(orch.outcomes["unchanged"], 2)
        self.assertEqual(person.comment, stored)

    def test_approved_person_keeps_the_erp_phone_and_drops_disabled_numbers(self):
        person = self.env["res.partner"].create({"name": "ERP Person", "phone": "215-555-0101"})
        self._erp_marker(person, "91")
        orch = SyncOrchestrator(self.env)
        orch._crosswalk = {"vs-ph": "91"}
        orch._crosswalk_ready = True
        dto = contact_to_canonical(
            {
                "contact_id": "vs-ph",
                "phone_numbers": [
                    {"name": "Direct", "number": "(215) 555-0101"},
                    {"name": "Mobile 1", "number": "215-555-0102"},
                    {"name": "Fax", "number": "215-555-0101"},
                    {"name": "Home", "number": "215-555-0106", "disabled": True},
                ],
            }
        )
        leads_before = self.env["crm.lead"].with_context(active_test=False).search_count([])
        orch._upsert_lead(self.connection, dto)
        self.assertEqual(person.phone, "215-555-0101")
        lines = [(line.label, line.number) for line in person.phone_line_ids]
        self.assertEqual(lines, [("mobile", "215-555-0102"), ("fax", "215-555-0101")])
        self.assertNotIn("215-555-0106", [number for _label, number in lines])
        self.assertEqual(self.env["crm.lead"].with_context(active_test=False).search_count([]), leads_before)
        orch._upsert_lead(self.connection, dto)
        self.assertEqual([(line.label, line.number) for line in person.phone_line_ids], lines)

    def test_approved_person_without_a_lead_keeps_provider_calls(self):
        person = self.env["res.partner"].create(
            {
                "name": "ERP Person",
                "phone": "215-555-0101",
                "comment": "<p>ERP manual</p>",
            }
        )
        self._erp_marker(person, "77")
        partners_before = self.env["res.partner"].with_context(active_test=False).search_count([])
        leads_before = self.env["crm.lead"].with_context(active_test=False).search_count([])
        run = self.env["plasticos.crm.sync.run"].create({"connection_id": self.connection.id, "kind": "incremental"})
        orch = SyncOrchestrator(self.env)
        early = CanonicalCall(
            provider="vanillasoft",
            external_id="call-person-early",
            contact_external_id="vs-person-1",
            call_datetime_utc="2024-03-05T14:10:00Z",
            duration_seconds=45,
            user_name="Rep",
            result_code="LM",
            comment="left a message",
        )
        orch._upsert_calls(self.connection, [early], run)
        self.assertEqual(run.orphans_buffered, 1)
        self.assertFalse(self.env["plasticos.crm.call.event"].search([("external_id", "=", "call-person-early")]))
        pending = self.env["plasticos.crm.sync.orphan"].search(
            [
                ("connection_id", "=", self.connection.id),
                ("external_id", "=", "call-person-early"),
                ("kind", "=", "call"),
                ("resolved", "=", False),
            ]
        )
        self.assertEqual(len(pending), 1)

        orch._crosswalk = {"vs-person-1": "77"}
        orch._crosswalk_ready = True
        bound = orch._upsert_lead(self.connection, self._lead("vs-person-1", contact_note="CRM history"))
        self.assertFalse(bound)
        self.assertEqual(self.env["crm.lead"].with_context(active_test=False).search_count([]), leads_before)
        self.assertEqual(self.env["res.partner"].with_context(active_test=False).search_count([]), partners_before)
        self.assertEqual(person.phone, "215-555-0101")
        self.assertIn("ERP manual", person.comment or "")

        resolved = orch._resolve_orphans(self.connection, MagicMock(), run)
        self.assertEqual(resolved, 1)
        self.assertEqual(run.orphans_resolved, 1)
        self.assertTrue(pending.resolved)
        event = self.env["plasticos.crm.call.event"].search(
            [("provider", "=", "vanillasoft"), ("external_id", "=", "call-person-early")]
        )
        self.assertEqual(len(event), 1)
        self.assertEqual(event.partner_id, person)
        self.assertFalse(event.lead_id)
        self.assertEqual(event.contact_external_id, "vs-person-1")
        self.assertEqual(event.result_code, "LM")
        self.assertEqual(event.comment, "left a message")
        self.assertEqual(event.duration_seconds, 45)
        self.assertEqual(event.user_name, "Rep")
        self.assertEqual(fields.Datetime.to_string(event.call_datetime_utc), "2024-03-05 14:10:00")

        direct = CanonicalCall(
            provider="vanillasoft",
            external_id="call-person-direct",
            contact_external_id="vs-person-1",
            call_datetime_utc="2024-03-06T09:00:00Z",
            duration_seconds=12,
            user_name="Rep",
            result_code="NA",
            comment="no answer",
        )
        self.assertEqual(orch._upsert_calls(self.connection, [direct], run), 1)
        self.assertEqual(run.orphans_buffered, 1)
        landed = self.env["plasticos.crm.call.event"].search(
            [("provider", "=", "vanillasoft"), ("external_id", "=", "call-person-direct")]
        )
        self.assertEqual(len(landed), 1)
        self.assertEqual(landed.partner_id, person)
        self.assertFalse(landed.lead_id)
        self.assertEqual(landed.contact_external_id, "vs-person-1")
        self.assertEqual(landed.result_code, "NA")
        self.assertEqual(landed.comment, "no answer")
        self.assertEqual(fields.Datetime.to_string(landed.call_datetime_utc), "2024-03-06 09:00:00")

        refs = self.env["plasticos.crm.external.ref"].search(
            [("provider", "=", "vanillasoft"), ("external_id", "=", "vs-person-1")]
        )
        self.assertEqual(len(refs), 1)
        self.assertEqual(refs.res_model, "res.partner")
        self.assertEqual(refs.res_id, person.id)
        self.assertFalse(refs.lead_id)
        stored_comment = person.comment
        stored_phone = person.phone
        self.assertEqual(orch._upsert_calls(self.connection, [early, direct], run), 0)
        self.assertEqual(
            self.env["plasticos.crm.call.event"].search_count([("contact_external_id", "=", "vs-person-1")]),
            2,
        )
        self.assertEqual(person.comment, stored_comment)
        self.assertEqual(person.phone, stored_phone)
        self.assertEqual(event.partner_id, person)
        self.assertFalse(event.lead_id)
        self.assertEqual(landed.partner_id, person)
        self.assertFalse(landed.lead_id)

    def _erp_marker(self, partner, ct_id):
        self.env["ir.model.data"].create(
            {
                "module": "plasticos_transaction",
                "name": f"legacy_erp_contact_{ct_id}",
                "model": "res.partner",
                "res_id": partner.id,
                "noupdate": True,
            }
        )

    def test_persisted_person_ref_is_kept_when_the_crosswalk_is_unset(self):
        person = self.env["res.partner"].create({"name": "Archived ERP Person", "active": False})
        self._erp_marker(person, "99")
        dto = self._lead("vs-keep", contact_note="bound once")
        Ref = self.env["plasticos.crm.external.ref"]
        Lead = self.env["crm.lead"].with_context(active_test=False)

        approved = SyncOrchestrator(self.env)
        approved._crosswalk = {"vs-keep": "99"}
        approved._crosswalk_ready = True
        approved.outcomes = _new_outcomes()
        approved._upsert_lead(self.connection, dto)
        self.assertEqual(approved.outcomes["updated"], 1)
        leads_before = Lead.search_count([])
        comment = person.comment

        unset = SyncOrchestrator(self.env)
        unset._crosswalk = None
        unset._crosswalk_ready = True
        unset.outcomes = _new_outcomes()
        unset._upsert_lead(self.connection, dto)
        unset._upsert_lead(self.connection, dto)
        self.assertEqual(unset.last_lead_outcome, "unchanged")
        self.assertEqual(unset.outcomes["unchanged"], 2)
        self.assertEqual(unset.outcomes["created"], 0)
        self.assertEqual(Lead.search_count([]), leads_before)
        self.assertFalse(Lead.search([("vanillasoft_id", "=", "vs-keep")]))
        refs = Ref.search([("provider", "=", "vanillasoft"), ("external_id", "=", "vs-keep")])
        self.assertEqual(len(refs), 1)
        self.assertEqual((refs.res_model, refs.res_id), ("res.partner", person.id))
        self.assertEqual(person.comment, comment)

    def test_approved_material_failure_is_contained_and_the_page_continues(self):
        facility = self._facility("Approved Mill")
        self.env["plasticos.facility.profile"].create({"partner_id": facility.id})
        person = self.env["res.partner"].create({"name": "Approved Buyer", "parent_id": facility.id})
        self._erp_marker(person, "88")
        lead_a = self.env["crm.lead"].create({"name": "A", "vanillasoft_id": "vs-am1", "partner_id": person.id})
        lead_b = self.env["crm.lead"].create({"name": "B", "vanillasoft_id": "vs-am2", "partner_id": person.id})
        orch = SyncOrchestrator(self.env)
        orch._crosswalk = {"vs-am1": "88", "vs-am2": "88"}
        orch._crosswalk_ready = True
        orch.outcomes = _new_outcomes()
        profiles = self.env["plasticos.material.profile"]
        profiles_before = profiles.search_count([])
        profile_model = type(profiles)
        original = profile_model.create

        def boom(records, vals_list):
            created = original(records, vals_list)
            records.env.cr.execute("SELECT 1 FROM plasticos_material_profile_missing_for_rollback")
            return created

        with patch.object(profile_model, "create", boom):
            first = orch._upsert_lead(self.connection, self._lead("vs-am1", custom_fields={"Materials": "HDPE Drums"}))
        self.assertEqual(first, lead_a)
        self.assertEqual(orch.last_lead_outcome, "updated")
        self.assertEqual(orch.outcomes["failed"], 0)
        self.assertTrue(any("material normalization failed" in row["message"] for row in orch.error_rows))
        self.assertEqual(profiles.search_count([]), profiles_before)
        ref_a = self.env["plasticos.crm.external.ref"].search([("external_id", "=", "vs-am1")])
        self.assertEqual((ref_a.res_model, ref_a.res_id), ("res.partner", person.id))

        second = orch._upsert_lead(self.connection, self._lead("vs-am2", custom_fields={"Materials": "PP Supersacs"}))
        self.assertEqual(second, lead_b)
        self.assertEqual(orch.outcomes["updated"], 2)
        stored = profiles.search([("partner_id", "=", facility.id)])
        self.assertEqual(stored.mapped("polymer_id.code"), ["PP"])

    def test_excluded_source_columns_stay_out_of_every_persisted_path(self):
        """Approved data lands. The 35 excluded columns do not, on any write path."""
        tokens = (
            "EXCL-LOAD-READY",
            "EXCL-FOB",
            "EXCL-MELT",
            "EXCL-DENSITY",
            "EXCL-EQUIPMENT",
            "EXCL-PRICE",
            "EXCL-NAICS",
        )
        custom = {
            "Notes": "operator wrote that the melt looked high",
            "Buyer/Supplier": "Supplier",
            "Last Result Code": "LM",
            "Load Ready": "EXCL-LOAD-READY",
            "FOB/FAS (MRP)": "EXCL-FOB",
            "Melt (LDPE)": "EXCL-MELT",
            "Density (HDPE)": "EXCL-DENSITY",
            "Equipment": "EXCL-EQUIPMENT",
            "Price Quoted (PP)": "EXCL-PRICE",
            "NAICS Code  Description": "EXCL-NAICS",
            "Materials": "HDPE Drums",
        }
        dto = contact_to_canonical(
            {
                "contact_id": "vs-excl-1",
                "company": "Exclusion Co",
                "first_name": "Ada",
                "last_name": "Lovelace",
                "email": "ada-excl@example.test",
                "phone": "215-555-0199",
                "Address 1": "12 Dock St",
                "Zip Code": "19103",
                "zip": "19019",
                "custom_fields": [{"name": key, "value": value} for key, value in custom.items()],
            }
        )
        self.assertEqual(dto.street, "12 Dock St")
        self.assertEqual(dto.zip, "19019")
        self.assertNotIn("Load Ready", dto.custom_fields)

        orch = SyncOrchestrator(self.env)
        lead = orch._upsert_lead(self.connection, dto)
        lead.delivery_term = "fcfs"
        again = orch._upsert_lead(self.connection, dto)
        self.assertEqual(again, lead)
        text = lead.description or ""
        self.assertIn("operator wrote that the melt looked high", text)
        self.assertIn("VanillaSoft Buyer/Supplier: Supplier", text)
        self.assertIn("VanillaSoft ContactID vs-excl-1 Last Result Code: LM", text)
        self.assertEqual(lead.email_from, "ada-excl@example.test")
        self.assertEqual(lead.phone, "215-555-0199")
        self.assertEqual(lead.street, "12 Dock St")
        self.assertEqual(lead.zip, "19019")
        self.assertEqual(lead.delivery_term, "fcfs")
        self._assert_tokens_absent(tokens, text)
        self._assert_tokens_absent(tokens, self._profile_notes(lead))

        class Adapter:
            def iter_table_rows(self, contact_id):
                yield CanonicalTableRow(
                    provider="vanillasoft",
                    contact_external_id=contact_id,
                    table_id="9",
                    table_name="Materials",
                    external_row_id="excl-row",
                    fields={
                        "Material": "HDPE Drums",
                        "Notes": "ordinary notes mention Load Ready",
                        "FOB/FAS (HDPE)": "EXCL-FOB",
                        "Equipment": "EXCL-EQUIPMENT",
                        "Load Ready": "EXCL-LOAD-READY",
                    },
                )

        row_model = self.env["plasticos.crm.external.table.row"]
        dirty = row_model.create(
            {
                "provider": "vanillasoft",
                "lead_id": lead.id,
                "contact_external_id": "vs-excl-1",
                "table_id": "9",
                "table_name": "Materials",
                "external_row_id": "excl-row",
                "fields_json": {"Material": "HDPE Drums", "FOB/FAS (HDPE)": "EXCL-FOB"},
            }
        )
        orch._sync_tables_for_lead(self.connection, Adapter(), "vs-excl-1", lead)
        orch._sync_tables_for_lead(self.connection, Adapter(), "vs-excl-1", lead)
        self.assertEqual(row_model.search_count([("external_row_id", "=", "excl-row")]), 1)
        stored = dirty.fields_json
        self.assertEqual(stored.get("Material"), "HDPE Drums")
        self.assertIn("ordinary notes mention Load Ready", stored.get("Notes") or "")
        self.assertNotIn("FOB/FAS (HDPE)", stored)
        self._assert_tokens_absent(tokens, str(stored))
        self._assert_tokens_absent(tokens, self._profile_notes(lead))

        orphan_model = self.env["plasticos.crm.sync.orphan"]
        orch._sync_tables_for_lead(self.connection, Adapter(), "vs-excl-orphan", None)
        buffered = orphan_model.search([("contact_external_id", "=", "vs-excl-orphan"), ("kind", "=", "table_row")])
        self.assertEqual(len(buffered), 1)
        self._assert_tokens_absent(tokens, str(buffered.payload_json))
        dirty_orphan = orphan_model.create(
            {
                "connection_id": self.connection.id,
                "provider": "vanillasoft",
                "kind": "table_row",
                "contact_external_id": "vs-excl-1",
                "external_id": "excl-dirty-orphan",
                "payload_json": {
                    "provider": "vanillasoft",
                    "contact_external_id": "vs-excl-1",
                    "table_id": "8",
                    "table_name": "Materials",
                    "external_row_id": "excl-dirty-orphan",
                    "fields": {
                        "Material": "Pallets",
                        "Melt (LDPE)": "EXCL-MELT",
                        "Load Ready": "EXCL-LOAD-READY",
                    },
                },
            }
        )
        orch._resolve_orphans(self.connection, Adapter(), None)
        landed = row_model.search([("external_row_id", "=", "excl-dirty-orphan")])
        self.assertEqual(len(landed), 1)
        self.assertEqual(landed.fields_json.get("Material"), "Pallets")
        self._assert_tokens_absent(tokens, str(landed.fields_json))
        self.assertTrue(dirty_orphan.resolved)
        self.assertEqual(dirty_orphan.payload_json["fields"].get("Material"), "Pallets")
        self.assertNotIn("Melt (LDPE)", dirty_orphan.payload_json["fields"])
        self.assertNotIn("Load Ready", dirty_orphan.payload_json["fields"])
        self._assert_tokens_absent(tokens, self._profile_notes(lead))

        person = self.env["res.partner"].create(
            {
                "name": "ERP Exclusion Person",
                "phone": "555-0100",
                "street": "ERP DOCK",
                "comment": "ERP-OWNED sentinel",
            }
        )
        self._erp_marker(person, "8801")
        approved = SyncOrchestrator(self.env)
        approved._crosswalk = {"vs-excl-person": "8801"}
        approved._crosswalk_ready = True
        approved.outcomes = _new_outcomes()
        person_dto = contact_to_canonical(
            {
                "contact_id": "vs-excl-person",
                "email": "person@example.test",
                "phone": "215-555-0188",
                "Address 1": "SHOULD NOT REPLACE",
                "custom_fields": [
                    {"name": "Notes", "value": "approved history"},
                    {"name": "Buyer/Supplier", "value": "Buyer"},
                    {"name": "Load Ready", "value": "EXCL-LOAD-READY"},
                    {"name": "Equipment", "value": "EXCL-EQUIPMENT"},
                ],
            }
        )
        approved._upsert_lead(self.connection, person_dto)
        approved._upsert_lead(self.connection, person_dto)
        comment = str(person.comment)
        self.assertIn("ERP-OWNED sentinel", comment)
        self.assertIn("approved history", comment)
        self.assertIn("Buyer/Supplier", comment)
        self.assertNotIn("EXCL-LOAD-READY", comment)
        self.assertNotIn("EXCL-EQUIPMENT", comment)
        self.assertEqual(person.street, "ERP DOCK")
        self.assertEqual(person.phone, "555-0100")
        leads = self.env["crm.lead"].with_context(active_test=False)
        self.assertFalse(leads.search([("vanillasoft_id", "=", "vs-excl-person")]))

        call = CanonicalCall(
            provider="vanillasoft",
            external_id="call-excl-1",
            contact_external_id="vs-excl-1",
            call_datetime_utc="2024-03-05T14:10:00Z",
            comment="discussed melt index; Load Ready was said in the call",
            result_code="LM",
        )
        orch._upsert_calls(self.connection, [call], None)
        orch._upsert_calls(self.connection, [call], None)
        events = self.env["plasticos.crm.call.event"].search([("external_id", "=", "call-excl-1")])
        self.assertEqual(len(events), 1)
        self.assertIn("discussed melt index", events.comment)
        self.assertIn("Load Ready was said in the call", events.comment)

    def _profile_notes(self, lead):
        profiles = self.env["plasticos.material.profile"].search([("facility_profile_id.crm_lead_id", "=", lead.id)])
        facilities = self.env["plasticos.facility.profile"].search([("crm_lead_id", "=", lead.id)])
        return " ".join(
            [*(profile.freeform_notes or "" for profile in profiles), *(fac.freeform_notes or "" for fac in facilities)]
        )

    def _assert_tokens_absent(self, tokens, text):
        for token in tokens:
            self.assertNotIn(token, text or "")

    def test_upgrade_removes_importer_owned_legacy_exclusions_only(self):
        """An installed database keeps human notes and loses labelled excluded columns."""
        excluded_html = "".join(
            f"<p>VanillaSoft {name}: EXCL-{index}</p><p>VanillaSoft ContactID 42 {name}: EXCL-PERSON-{index}</p>"
            for index, name in enumerate(EXCLUDED_SOURCE_FIELDS)
        )
        kept_html = (
            "<p>ERP-OWNED sentinel</p>"
            "<p>operator wrote that the melt looked high</p>"
            "<p>VanillaSoft Buyer/Supplier: Supplier</p>"
            "<p>VanillaSoft Notes: FOB was a word in the note</p>"
        )
        lead = self.env["crm.lead"].create(
            {
                "name": "Legacy Lead",
                "vanillasoft_id": "vs-legacy-lead",
                "description": kept_html + excluded_html,
                "delivery_term": "fcfs",
            }
        )
        person = (
            self.env["res.partner"]
            .with_context(active_test=False)
            .create(
                {
                    "name": "Legacy ERP Person",
                    "active": False,
                    "street": "ERP DOCK",
                    "phone": "555-0100",
                    "comment": kept_html + excluded_html,
                }
            )
        )
        self.env["plasticos.crm.external.ref"].create(
            {
                "provider": "vanillasoft",
                "external_id": "vs-legacy-person",
                "res_model": "res.partner",
                "res_id": person.id,
            }
        )
        fields = {name: f"EXCL-{index}" for index, name in enumerate(EXCLUDED_SOURCE_FIELDS)}
        fields["Material"] = "HDPE Drums"
        fields["Notes"] = "Load Ready is mentioned in ordinary notes"
        row = self.env["plasticos.crm.external.table.row"].create(
            {
                "provider": "vanillasoft",
                "lead_id": lead.id,
                "contact_external_id": "vs-legacy-lead",
                "table_id": "9",
                "external_row_id": "legacy-row",
                "fields_json": dict(fields),
            }
        )
        other = self.env["plasticos.crm.external.table.row"].create(
            {
                "provider": "other",
                "contact_external_id": "other-1",
                "table_id": "9",
                "external_row_id": "other-row",
                "fields_json": {"Load Ready": "KEEP-OTHER", "Material": "HDPE Drums"},
            }
        )
        unresolved = self.env["plasticos.crm.sync.orphan"].create(
            {
                "connection_id": self.connection.id,
                "provider": "vanillasoft",
                "kind": "table_row",
                "contact_external_id": "vs-legacy-lead",
                "external_id": "legacy-orphan",
                "resolved": False,
                "payload_json": {
                    "provider": "vanillasoft",
                    "fields": dict(fields),
                    "comment": "discussed melt index; Load Ready was said in the call",
                },
            }
        )
        resolved = self.env["plasticos.crm.sync.orphan"].create(
            {
                "connection_id": self.connection.id,
                "provider": "vanillasoft",
                "kind": "table_row",
                "contact_external_id": "vs-legacy-lead",
                "external_id": "legacy-orphan-resolved",
                "resolved": True,
                "payload_json": {"provider": "vanillasoft", "fields": dict(fields)},
            }
        )
        call = self.env["plasticos.crm.call.event"].create(
            {
                "provider": "vanillasoft",
                "external_id": "legacy-call",
                "contact_external_id": "vs-legacy-lead",
                "lead_id": lead.id,
                "comment": "discussed melt index; Load Ready was said in the call",
            }
        )
        location = self._facility("Legacy Notes")
        facility = self.env["plasticos.facility.profile"].create(
            {
                "partner_id": location.id,
                "freeform_notes": "Load Ready was discussed by the operator",
            }
        )
        migration = self._load_exclusion_migration()
        migration.migrate(self.env.cr, None)
        self.assertIn("EXCL-0", lead.description)
        migration.migrate(self.env.cr, "19.0.1.9.1")
        lead.invalidate_recordset()
        person.invalidate_recordset()
        row.invalidate_recordset()
        other.invalidate_recordset()
        unresolved.invalidate_recordset()
        resolved.invalidate_recordset()
        self.assertEqual(lead.description, kept_html)
        self.assertEqual(str(person.comment), kept_html)
        self.assertFalse(person.active)
        self.assertEqual(person.street, "ERP DOCK")
        self.assertEqual(person.phone, "555-0100")
        self.assertEqual(lead.delivery_term, "fcfs")
        self.assertEqual(set(row.fields_json), {"Material", "Notes"})
        self.assertEqual(row.fields_json["Notes"], "Load Ready is mentioned in ordinary notes")
        self.assertEqual(other.fields_json["Load Ready"], "KEEP-OTHER")
        self.assertEqual(set(unresolved.payload_json["fields"]), {"Material", "Notes"})
        self.assertEqual(unresolved.payload_json["comment"], "discussed melt index; Load Ready was said in the call")
        self.assertFalse(unresolved.resolved)
        self.assertEqual(set(resolved.payload_json["fields"]), {"Material", "Notes"})
        self.assertTrue(resolved.resolved)
        self.assertEqual(call.comment, "discussed melt index; Load Ready was said in the call")
        self.assertEqual(facility.freeform_notes, "Load Ready was discussed by the operator")
        again_lead = lead.description
        again_comment = str(person.comment)
        migration.migrate(self.env.cr, "19.0.1.9.1")
        lead.invalidate_recordset()
        person.invalidate_recordset()
        self.assertEqual(lead.description, again_lead)
        self.assertEqual(str(person.comment), again_comment)

    def _lead_profiles(self, lead):
        return self.env["plasticos.material.profile"].search([("facility_profile_id.crm_lead_id", "=", lead.id)])

    def test_production_section_parser_splits_phrases_not_hints(self):
        sections = _parse_material_sections(
            {
                "Materials": "LDPE, HDPE Drums",
                "Material Form": "Roll, Film",
                "Notes": "keep, this note",
            }
        )
        slot = sections[""]
        self.assertEqual(slot["phrases"], ["LDPE", "HDPE Drums"])
        self.assertEqual(slot["hints"], ["Roll, Film"])
        self.assertEqual(slot["notes"], [("Notes", "keep, this note")])
        self.assertIn("_split_commas", inspect.getsource(_parse_material_sections))

    def test_upsert_lead_splits_comma_phrases_and_replays(self):
        orch = SyncOrchestrator(self.env)
        dto = self._lead("vs-comma-prod", custom_fields={"Materials": "LDPE, HDPE Drums"})
        lead = orch._upsert_lead(self.connection, dto)
        profiles = self._lead_profiles(lead)
        by_polymer = {profile.polymer_id.code: profile for profile in profiles}
        self.assertEqual(set(by_polymer), {"LDPE", "HDPE"})
        self.assertEqual(by_polymer["LDPE"].form_id.code, "FILM")
        self.assertEqual(by_polymer["HDPE"].material_grade_id.code, "DRUMS")
        ids = {code: profile.id for code, profile in by_polymer.items()}
        orch._upsert_lead(self.connection, dto)
        replayed = self._lead_profiles(lead)
        self.assertEqual({profile.polymer_id.code: profile.id for profile in replayed}, ids)
        self.assertEqual(len(replayed), 2)

    def test_form_hint_comma_stays_one_hint(self):
        orch = SyncOrchestrator(self.env)
        lead = orch._upsert_lead(
            self.connection,
            self._lead(
                "vs-comma-hint",
                custom_fields={
                    "Materials": "LDPE, HDPE Drums",
                    "Material Form": "Roll, Film",
                    "Notes": "buyer said roll, film in passing",
                },
            ),
        )
        profiles = self._lead_profiles(lead)
        self.assertEqual(set(profiles.mapped("polymer_id.code")), {"LDPE", "HDPE"})
        self.assertEqual(len(profiles), 2)
        self.assertEqual(profiles.filtered(lambda profile: profile.polymer_id.code == "LDPE").form_id.code, "FILM")
        self.assertEqual(
            profiles.filtered(lambda profile: profile.polymer_id.code == "HDPE").material_grade_id.code, "DRUMS"
        )
        self.assertTrue(any("type hint is not contact-unique" in row["message"] for row in orch.error_rows))
        self.assertFalse(any("Roll" == row["message"] or "Film" == row["message"] for row in orch.error_rows))

    def test_section_hint_does_not_broadcast_across_comma_phrases(self):
        orch = SyncOrchestrator(self.env)
        lead = orch._upsert_lead(
            self.connection,
            self._lead(
                "vs-comma-section",
                custom_fields={
                    "Materials": "HDPE Drums, PP",
                    "Type (LDPE)": "Roll, Film",
                    "Notes (MRF's)": "see, later",
                },
            ),
        )
        profiles = self._lead_profiles(lead)
        self.assertEqual(set(profiles.mapped("polymer_id.code")), {"HDPE", "PP"})
        self.assertFalse(profiles.filtered(lambda profile: profile.polymer_id.code == "LDPE"))
        self.assertFalse(profiles.filtered(lambda profile: profile.form_id.code == "FILM"))
        self.assertEqual(
            profiles.filtered(lambda profile: profile.polymer_id.code == "HDPE").material_grade_id.code, "DRUMS"
        )
        self.assertFalse(profiles.filtered(lambda profile: profile.polymer_id.code == "PP").form_id)

    def test_mixed_delimiters_and_repeated_phrases_stay_unique(self):
        orch = SyncOrchestrator(self.env)
        lead = orch._upsert_lead(
            self.connection,
            self._lead(
                "vs-comma-mix",
                custom_fields={"Materials": "LDPE,  HDPE Drums; LDPE | PP\nHDPE Drums"},
            ),
        )
        profiles = self._lead_profiles(lead)
        self.assertEqual(set(profiles.mapped("polymer_id.code")), {"LDPE", "HDPE", "PP"})
        self.assertEqual(len(profiles), 3)
        self.assertEqual(profiles.filtered(lambda profile: profile.polymer_id.code == "LDPE").form_id.code, "FILM")
        self.assertEqual(
            profiles.filtered(lambda profile: profile.polymer_id.code == "HDPE").material_grade_id.code, "DRUMS"
        )
        self.assertFalse(profiles.filtered(lambda profile: profile.polymer_id.code == "PP").form_id)

    def test_unknown_comma_phrase_stays_unresolved(self):
        orch = SyncOrchestrator(self.env)
        lead = orch._upsert_lead(
            self.connection,
            self._lead("vs-comma-unknown", custom_fields={"Materials": "LDPE, not a polymer"}),
        )
        profiles = self._lead_profiles(lead)
        self.assertEqual(profiles.mapped("polymer_id.code"), ["LDPE"])
        self.assertFalse(profiles.filtered(lambda profile: profile.polymer_id.code == "OTHER"))
        self.assertTrue(any("not a polymer" in row["message"] for row in orch.error_rows))
        self.assertEqual(orch.last_lead_outcome, "created")

    def test_hint_only_and_notes_only_create_no_polymer(self):
        orch = SyncOrchestrator(self.env)
        hinted = orch._upsert_lead(
            self.connection,
            self._lead("vs-comma-hint-only", custom_fields={"Material Form": "Roll, Film"}),
        )
        self.assertFalse(self._lead_profiles(hinted))
        self.assertTrue(any("BLOCKED_UNRESOLVED: Roll, Film" in row["message"] for row in orch.error_rows))
        noted = orch._upsert_lead(
            self.connection,
            self._lead("vs-comma-notes-only", custom_fields={"Notes": "roll, film was mentioned"}),
        )
        self.assertFalse(self._lead_profiles(noted))
        self.assertFalse(self.env["plasticos.facility.profile"].search([("crm_lead_id", "=", noted.id)]))

    def test_run_connection_persists_comma_split_profiles(self):
        connection = self.env["plasticos.crm.connection"].create(
            {"name": "Comma VS", "provider": "vanillasoft", "project_id": "139707", "enabled": False}
        )
        dto = self._lead(
            "vs-comma-run",
            custom_fields={"Materials": "LDPE, HDPE Drums"},
            modified_utc="2026-10-26T12:00:00Z",
        )
        _orch, run = self._run_connection(connection, [dto])
        stored = self.env["crm.lead"].search([("vanillasoft_id", "=", "vs-comma-run")])
        self.assertEqual(len(stored), 1)
        profiles = self._lead_profiles(stored)
        by_polymer = {profile.polymer_id.code: profile for profile in profiles}
        self.assertEqual(set(by_polymer), {"LDPE", "HDPE"})
        self.assertEqual(by_polymer["LDPE"].form_id.code, "FILM")
        self.assertEqual(by_polymer["HDPE"].material_grade_id.code, "DRUMS")
        self.assertEqual(run.contacts_failed, 0)
        ids = {code: profile.id for code, profile in by_polymer.items()}
        self._run_connection(connection, [dto])
        replayed = self._lead_profiles(stored)
        self.assertEqual({profile.polymer_id.code: profile.id for profile in replayed}, ids)

    def test_approved_lead_splits_comma_phrases(self):
        facility = self._facility("Comma Approved Mill")
        self.env["plasticos.facility.profile"].create({"partner_id": facility.id})
        person = self.env["res.partner"].create({"name": "Comma Buyer", "parent_id": facility.id})
        self._erp_marker(person, "3231")
        lead = self.env["crm.lead"].create(
            {"name": "Comma Approved", "vanillasoft_id": "vs-comma-appr", "partner_id": person.id}
        )
        orch = SyncOrchestrator(self.env)
        orch._crosswalk = {"vs-comma-appr": "3231"}
        orch._crosswalk_ready = True
        returned = orch._upsert_lead(
            self.connection,
            self._lead("vs-comma-appr", custom_fields={"Materials": "LDPE, HDPE Drums"}),
        )
        self.assertEqual(returned, lead)
        profiles = self.env["plasticos.material.profile"].search([("partner_id", "=", facility.id)])
        by_polymer = {profile.polymer_id.code: profile for profile in profiles}
        self.assertEqual(set(by_polymer), {"LDPE", "HDPE"})
        self.assertEqual(by_polymer["LDPE"].form_id.code, "FILM")
        self.assertEqual(by_polymer["HDPE"].material_grade_id.code, "DRUMS")
        self.assertEqual(
            self.env["plasticos.facility.profile"].search_count([("partner_id", "=", facility.id)]),
            1,
        )
        ids = {code: profile.id for code, profile in by_polymer.items()}
        orch._upsert_lead(
            self.connection,
            self._lead("vs-comma-appr", custom_fields={"Materials": "LDPE, HDPE Drums"}),
        )
        replayed = self.env["plasticos.material.profile"].search([("partner_id", "=", facility.id)])
        self.assertEqual({profile.polymer_id.code: profile.id for profile in replayed}, ids)

    def test_person_path_splits_commas_without_a_new_facility(self):
        facility = self._facility("Comma Person Facility")
        self.env["plasticos.facility.profile"].create({"partner_id": facility.id})
        person = self.env["res.partner"].create({"name": "Comma Person", "parent_id": facility.id})
        self._erp_marker(person, "3232")
        orch = SyncOrchestrator(self.env)
        orch._crosswalk = {"vs-comma-person": "3232"}
        orch._crosswalk_ready = True
        leads_before = self.env["crm.lead"].with_context(active_test=False).search_count([])
        orch._upsert_lead(
            self.connection,
            self._lead("vs-comma-person", custom_fields={"Materials": "LDPE, HDPE Drums"}),
        )
        self.assertEqual(self.env["crm.lead"].with_context(active_test=False).search_count([]), leads_before)
        self.assertEqual(self.env["plasticos.facility.profile"].search_count([("partner_id", "=", facility.id)]), 1)
        profiles = self.env["plasticos.material.profile"].search([("partner_id", "=", facility.id)])
        by_polymer = {profile.polymer_id.code: profile for profile in profiles}
        self.assertEqual(set(by_polymer), {"LDPE", "HDPE"})
        self.assertEqual(by_polymer["LDPE"].form_id.code, "FILM")
        self.assertEqual(by_polymer["HDPE"].material_grade_id.code, "DRUMS")

    def test_super_sacks_replay_fills_empty_packaging_and_keeps_a_different_color(self):
        facility = self._facility("Super Sack Replay")
        orch = SyncOrchestrator(self.env)
        orch.outcomes = _new_outcomes()
        lead = orch._upsert_lead(self.connection, self._lead("vs-sacks"))
        lead.partner_id = facility
        orch._upsert_lead(self.connection, self._lead("vs-sacks", custom_fields={"Materials": "Super Sacks"}))
        profile = self._profiles(facility)
        self.assertEqual(profile.polymer_id.code, "PP")
        self.assertEqual(profile.material_grade_id.code, "SUPERACS")
        self.assertEqual(profile.packaging_type_id.code, "bales")
        self.assertEqual(profile.material_attribute_ids.mapped("code"), ["lined"])
        red = self.env["plasticos.material.color"].search([("code", "=", "RED")], limit=1)
        profile.write({"packaging_type_id": False, "color_id": red.id})
        orch.error_rows.clear()
        orch._upsert_lead(self.connection, self._lead("vs-sacks", custom_fields={"Materials": "Super Sacks"}))
        profile = self._profiles(facility)
        self.assertEqual(profile.packaging_type_id.code, "bales")
        self.assertEqual(profile.color_id.code, "RED")
        self.assertEqual(profile.material_attribute_ids.mapped("code"), ["lined"])
        self.assertFalse(any(row.get("category") == REQUIRED_MAPPING for row in orch.error_rows))

    def test_mixed_density_repro_stays_unresolved(self):
        facility = self._facility("Regrind Replay")
        orch = SyncOrchestrator(self.env)
        orch.outcomes = _new_outcomes()
        lead = orch._upsert_lead(self.connection, self._lead("vs-regrind"))
        lead.partner_id = facility
        phrase = "ldpe/lldpe clear repro"
        orch.error_rows.clear()
        orch._upsert_lead(self.connection, self._lead("vs-regrind", custom_fields={"Materials": phrase}))
        self.assertFalse(self._profiles(facility))
        self.assertTrue(
            any(
                row.get("category") == REQUIRED_MAPPING and "unresolved material" in row.get("message", "")
                for row in orch.error_rows
            )
        )

    def test_worksheet_normalizer_rejects_bare_ldpe_and_conflicts(self):
        from odoo.addons.plasticos_material_profile.models.material_normalizer import normalize_material

        bare = normalize_material(self.env, "LDPE")
        self.assertEqual(bare.unresolved, ("unresolved material",))
        self.assertFalse(bare.polymer)
        conflict = normalize_material(self.env, "HDPE Drums", structured={"type": "LDPE Film"})
        self.assertEqual(conflict.unresolved, ("conflicting material evidence",))
        self.assertFalse(conflict.polymer)
        source = (
            Path(__file__).resolve().parents[2] / "plasticos_transaction/models/native_document_import.py"
        ).read_text()
        self.assertIn("normalize_material(", source)
        self.assertNotIn("normalize_crm_material", source)

    def _load_exclusion_migration(self):
        path = (
            Path(inspect.getfile(SyncOrchestrator)).resolve().parents[1]
            / "migrations"
            / "19.0.1.9.4"
            / "post-migrate.py"
        )
        spec = importlib.util.spec_from_file_location("plasticos_crm_sync_migrate_190194", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
