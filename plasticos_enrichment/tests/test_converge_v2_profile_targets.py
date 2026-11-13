"""Odoo runtime tests: converge v2 enrichment of material and facility profiles.

ADR-012 amendment 2026-11-13. A v2 run requests the mapped fields that are
empty on its target, stores the validated reply for review, and on whole-run
approval writes only admitted ``inferred`` / ``external_claim`` values through
the ``CONVERGE_V2_TARGETS`` mapping table, merge-not-overwrite, with one
provenance row per considered field. Gate is a test double; no network.
"""

from __future__ import annotations

from contextlib import contextmanager
from types import MappingProxyType, SimpleNamespace
from unittest.mock import patch

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.addons.plasticos_gate.services import gate_allowlists
from odoo.addons.plasticos_gate.services.gate_config import (
    GateAvailability,
    GateAvailabilityVerdict,
    GateCapability,
)
from odoo.addons.plasticos_gate.services.gate_contracts import CONVERGE_REQUEST_V2, CONVERGE_RESPONSE_V2
from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import tagged

_SEND = "odoo.addons.plasticos_gate.services.gate_client.send_converge_action"
_ENABLED = "odoo.addons.plasticos_gate.services.gate_config.gate_enrichment_enabled"
_CLASSIFY = "odoo.addons.plasticos_gate.services.gate_config.classify_gate_availability"
PROVENANCE = "plasticos.enrichment.provenance"
CARTRIDGE_VERSION = "0.5.0"


def _available():
    return GateAvailabilityVerdict(
        status=GateAvailability.AVAILABLE,
        available=True,
        capability=GateCapability.ENRICHMENT,
        reasons=[],
        gate_url_configured=True,
    )


def _source(ref="reply:1"):
    return {"source_type": "provider", "source_ref": ref, "method": "provider_reply", "independent": None}


def _v2_reply(body, specs, extra=None):
    """A response v2 (Revision 1) answering exactly the request's targets.

    ``specs`` maps a cartridge field to ``{"state", "value", "admitted", "unit",
    "unit_status"}``; a requested field without a spec is ``unknown``.
    """
    subject = body["subject"]
    identity = {"subject_ref": body["entity"]["id"], "subject_type": subject["type"], "role": subject.get("role")}
    evidence = {}
    admitted_values = {}
    for target in body["targets"]:
        name = target["field"]
        spec = specs.get(name, {"state": "unknown"})
        state = spec["state"]
        entry = {
            "state": state,
            "admitted": spec.get("admitted", False),
            "confidence": None,
            "sources": [],
            "derivation": None,
            "identity": identity,
            "declaration": target["type"],
            "conflict": None,
            "unknown_reason": None,
        }
        if state == "unknown":
            entry["unknown_reason"] = "no_evidence"
        elif state == "conflicting":
            entry["conflict"] = {
                "candidates": [
                    {"value": 1.0, "unit_status": "unknown", "confidence": 0.5, "sources": [_source("reply:a")]},
                    {"value": 2.0, "unit_status": "unknown", "confidence": 0.5, "sources": [_source("reply:b")]},
                ],
                "resolution": None,
            }
        else:
            entry["value"] = spec["value"]
            entry["confidence"] = spec.get("confidence", 0.9)
            if "unit" in spec:
                entry["unit_status"] = "stated"
                entry["unit"] = spec["unit"]
            else:
                entry["unit_status"] = spec.get("unit_status", "not_applicable")
            if state == "inferred":
                entry["derivation"] = {
                    "method": "test_rule",
                    "rule_or_model_version": "test-1.0.0",
                    "inputs": [],
                    "kb_fragment_ids": [],
                }
            else:
                entry["sources"] = [_source()]
        if entry["admitted"]:
            admitted_values[name] = spec["value"]
        evidence[name] = entry
    for name, entry in (extra or {}).items():
        # An entry the request did not target (a reply may carry more than asked).
        evidence[name] = {**entry, "identity": identity}
        if entry.get("admitted"):
            admitted_values[name] = entry["value"]
    return {
        "contract_version": CONVERGE_RESPONSE_V2,
        "state": "completed",
        "failure_reason": None,
        "fields": admitted_values,
        "confidence": 0.9,
        "resolution": {
            "cartridge_id": body["cartridge"]["id"],
            "cartridge_version": body["cartridge"]["version"],
            "cartridge_sha256": "test-sha",
            "node": body["node"],
        },
        "field_evidence": evidence,
        "proposals": [
            {
                "proposal_id": "p1",
                "proposal_type": "test",
                "identity": identity,
                "fields": list(evidence),
                "admitted_fields": list(admitted_values),
                "review": {"required": True, "reasons": []},
            }
        ],
    }


class _Gate:
    """Gate double: records the request body and answers with ``reply(body)``."""

    def __init__(self, reply):
        self.reply = reply
        self.bodies = []

    def __call__(self, env, *, payload, correlation_id=None, idempotency_key=None):
        self.bodies.append(payload)
        packet = SimpleNamespace(header=SimpleNamespace(packet_id="pkt-v2-1", correlation_id="corr-v2-1"))
        return {"packet": packet, "payload": self.reply(payload)}


@tagged("post_install", "-at_install", "plasticos", "enrichment", "gate")
class TestConvergeV2ProfileTargets(PlasticosTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._skip_if_model_missing("plasticos.enrichment.run", "plasticos.facility.profile")
        cls.registry_enter_test_mode_cls()
        tags = cls.env["plasticos.company.role.tag"]
        cls.tag_supplier = tags.search([("code", "=", "supplier")], limit=1) or tags.create(
            {"name": "Supplier", "code": "supplier"}
        )
        cls.tag_buyer = tags.search([("code", "=", "buyer")], limit=1) or tags.create(
            {"name": "Buyer", "code": "buyer"}
        )
        cls.hdpe = cls._get_or_create_polymer(code="hdpe", name="HDPE")

    def setUp(self):
        super().setUp()
        self._set_param("plasticos.gate.converge_contract", "v2")
        self._set_param("plasticos.gate.converge_cartridge_id", "plasticos")
        self._set_param("plasticos.gate.converge_cartridge_version", CARTRIDGE_VERSION)

    # ── helpers ──────────────────────────────────────────────────────────

    def _set_param(self, key, value):
        icp = self.env["ir.config_parameter"].sudo()
        previous = icp.get_param(key) or ""
        icp.set_param(key, value)
        self.addCleanup(icp.set_param, key, previous)

    @contextmanager
    def _request_rollback(self):
        savepoint = self.env.cr.savepoint(flush=True)
        try:
            with patch.object(self.env.cr, "rollback", savepoint.rollback):
                yield
        finally:
            savepoint.close(rollback=False)

    @contextmanager
    def _raises(self, exc_type):
        try:
            yield
        except exc_type:
            return
        self.fail(f"{exc_type.__name__} not raised")

    def _supplier_facility_profile(self, name, **vals):
        partner = self._create_partner(name, supplier_rank=1, company_role_tag_ids=[(6, 0, self.tag_supplier.ids)])
        return self.env["plasticos.facility.profile"].create({"partner_id": partner.id, **vals})

    def _buyer_facility_profile(self, name, **vals):
        company = self._create_partner(f"{name} Co", customer_rank=1)
        site = self.env["res.partner"].create(
            {
                "name": name,
                "parent_id": company.id,
                "is_company": True,
                "type": "other",
                "company_role_tag_ids": [(6, 0, self.tag_buyer.ids)],
            }
        )
        return self.env["plasticos.facility.profile"].create({"partner_id": site.id, **vals})

    def _start(self, profile):
        action = profile.action_start_enrichment_run()
        return self.env["plasticos.enrichment.run"].browse(action["res_id"])

    def _execute(self, run, gate):
        with patch(_CLASSIFY, return_value=_available()), patch(_ENABLED, return_value=True), patch(_SEND, gate):
            run.action_execute()

    def _provenance(self, run):
        return {p.target_field: p for p in self.env[PROVENANCE].search([("run_id", "=", run.id)])}

    # ── (1) supplier material profile ────────────────────────────────────

    def test_supplier_facility_profile_run_writes_only_admitted_claims_into_that_profile(self):
        profile = self._supplier_facility_profile("V2 Supplier One")
        other = self._supplier_facility_profile("V2 Supplier One Other")
        run = self._start(profile)
        self.assertEqual(run.partner_id, profile.partner_id)
        self.assertEqual(run.facility_profile_id, profile)
        gate = _Gate(
            lambda body: _v2_reply(
                body,
                {
                    "min_density": {"state": "external_claim", "admitted": True, "value": 0.94, "unit": "g/cm3"},
                    "max_density": {"state": "inferred", "admitted": True, "value": 0.96, "unit": "g/cm3"},
                    "max_mfi": {"state": "external_claim", "admitted": False, "value": 0.7, "unit": "g/10min"},
                },
            )
        )
        self._execute(run, gate)

        body = gate.bodies[0]
        self.assertEqual(body["contract"], CONVERGE_REQUEST_V2)
        self.assertEqual(body["cartridge"], {"id": "plasticos", "version": CARTRIDGE_VERSION})
        self.assertEqual(body["subject"], {"type": "material", "role": "supplier"})
        self.assertEqual(body["entity"]["id"], f"res.partner:{profile.partner_id.id}")
        self.assertNotIn("schema", body)
        self.assertEqual(run.state, "review")
        self.assertFalse(profile.density_min, "nothing is written before approval")

        run.action_inject()
        self.assertEqual(run.state, "injected")
        self.assertAlmostEqual(profile.density_min, 0.94)
        self.assertAlmostEqual(profile.density_max, 0.96)
        self.assertFalse(profile.melt_index_max, "an unadmitted claim is never written")
        self.assertFalse(other.density_min, "only the targeted profile is written")
        self.assertEqual(run.fields_written, 2)
        rows = self._provenance(run)
        self.assertLessEqual({"density_min", "density_max", "melt_index_min", "melt_index_max"}, set(rows))
        for row in rows.values():
            self.assertEqual((row.target_model, row.target_res_id), ("plasticos.facility.profile", profile.id))
        self.assertEqual(rows["density_min"].status, "written")
        self.assertEqual(rows["melt_index_max"].status, "skipped_not_admitted")
        self.assertEqual(rows["melt_index_min"].status, "skipped_unknown")

    # ── (2) buyer facility profile ───────────────────────────────────────

    def test_buyer_facility_profile_run_writes_codes_and_percent(self):
        profile = self._buyer_facility_profile("V2 Buyer Site", density_max=0.97)
        run = self._start(profile)
        gate = _Gate(
            lambda body: _v2_reply(
                body,
                {
                    "processed_polymers": {
                        "state": "external_claim",
                        "admitted": True,
                        "value": [{"code": "HDPE"}, {"code": "NOT-A-POLYMER"}],
                    },
                    "contamination_tolerance": {
                        "state": "external_claim",
                        "admitted": True,
                        "value": 4.0,
                        "unit": "percent",
                    },
                },
            )
        )
        self._execute(run, gate)
        body = gate.bodies[0]
        self.assertEqual(body["subject"], {"type": "material", "role": "buyer"})
        self.assertNotIn("max_density", [t["field"] for t in body["targets"]], "a filled field is not requested")
        self.assertIn("max_density", [o["field"] for o in body["observations"]])

        run.action_inject()
        self.assertEqual(profile.accepted_polymer_ids, self.hdpe)
        self.assertAlmostEqual(profile.contamination_tolerance_pct, 4.0)
        self.assertAlmostEqual(profile.density_max, 0.97)
        rows = self._provenance(run)
        self.assertEqual(rows["accepted_polymer_ids"].status, "written")
        self.assertIn("NOT-A-POLYMER", rows["accepted_polymer_ids"].value_written)
        self.assertEqual(rows["accepted_polymer_ids"].target_res_id, profile.id)
        self.assertFalse(
            self.env["plasticos.polymer"].search([("code", "=ilike", "NOT-A-POLYMER")]),
            "no master record is created",
        )

    # ── (3) unknown and conflicting ──────────────────────────────────────

    def test_unknown_and_conflicting_write_nothing_and_are_recorded(self):
        profile = self._supplier_facility_profile("V2 Supplier Three")
        run = self._start(profile)
        gate = _Gate(
            lambda body: _v2_reply(
                body,
                {
                    "max_density": {"state": "conflicting"},
                    "min_mfi": {"state": "external_claim", "admitted": True, "value": 0.5, "unit": "g/10min"},
                },
            )
        )
        self._execute(run, gate)
        run.action_inject()
        self.assertFalse(profile.density_min)
        self.assertFalse(profile.density_max)
        self.assertAlmostEqual(profile.melt_index_min, 0.5)
        rows = self._provenance(run)
        self.assertEqual(rows["density_min"].status, "skipped_unknown")
        self.assertEqual(rows["density_max"].status, "skipped_conflicting")

    # ── (4) merge-not-overwrite ──────────────────────────────────────────

    def test_a_field_filled_before_approval_is_not_overwritten(self):
        profile = self._supplier_facility_profile("V2 Supplier Four")
        run = self._start(profile)
        gate = _Gate(
            lambda body: _v2_reply(
                body,
                {
                    "min_density": {"state": "external_claim", "admitted": True, "value": 0.94, "unit": "g/cm3"},
                    "max_density": {"state": "external_claim", "admitted": True, "value": 0.96, "unit": "g/cm3"},
                },
            )
        )
        self._execute(run, gate)
        profile.write({"density_min": 0.91})
        run.action_inject()
        self.assertAlmostEqual(profile.density_min, 0.91)
        self.assertAlmostEqual(profile.density_max, 0.96)
        row = self._provenance(run)["density_min"]
        self.assertEqual(row.status, "skipped_immutable")
        self.assertEqual(row.previous_value, "0.91")

    # ── (5) units ────────────────────────────────────────────────────────

    def test_a_number_with_a_missing_or_different_unit_is_skipped(self):
        profile = self._supplier_facility_profile("V2 Supplier Five")
        run = self._start(profile)
        gate = _Gate(
            lambda body: _v2_reply(
                body,
                {
                    "min_density": {"state": "external_claim", "admitted": True, "value": 940.0, "unit": "kg/m3"},
                    "max_density": {"state": "external_claim", "admitted": True, "value": 0.96},
                    "max_mfi": {"state": "external_claim", "admitted": True, "value": 0.7, "unit": "g/10min"},
                },
            )
        )
        self._execute(run, gate)
        run.action_inject()
        self.assertFalse(profile.density_min)
        self.assertFalse(profile.density_max)
        self.assertAlmostEqual(profile.melt_index_max, 0.7)
        rows = self._provenance(run)
        self.assertEqual(rows["density_min"].status, "skipped_unit")
        self.assertEqual(rows["density_max"].status, "skipped_unit")

    # ── (6) v1-shaped reply to a v2 request ──────────────────────────────

    def test_a_v1_shaped_reply_writes_nothing_and_records_why(self):
        profile = self._supplier_facility_profile("V2 Supplier Six")
        run = self._start(profile)
        gate = _Gate(
            lambda body: {
                "state": "completed",
                "failure_reason": None,
                "fields": {"min_density": 0.94},
                "confidence": 0.9,
            }
        )
        run_id = run.id
        with self._request_rollback(), self._raises(UserError):
            self._execute(run, gate)
        self.env.invalidate_all()
        run = self.env["plasticos.enrichment.run"].browse(run_id)
        self.assertEqual(run.state, "degraded")
        self.assertIn("v1_reply", " ".join(run.validation_issues or []))
        self.assertEqual(run.gate_packet_id, "pkt-v2-1", "the rejected reply's packet id is kept on the run")
        self.assertEqual(run.gate_correlation_id, "corr-v2-1")
        self.assertFalse(profile.density_min)
        self.assertFalse(self.env[PROVENANCE].search([("run_id", "=", run_id)]))

    # ── (7) the v1 partner run is unchanged ──────────────────────────────

    def test_v1_partner_run_is_unchanged(self):
        self._set_param("plasticos.gate.converge_contract", "v1")
        self._set_param("plasticos.gate.auto_writeback", "0")
        partner = self._create_partner("V1 Partner", supplier_rank=1)
        run = self.env["plasticos.enrichment.run"].create({"partner_id": partner.id})
        gate = _Gate(
            lambda body: {
                "state": "completed",
                "failure_reason": None,
                "fields": {"website": "https://v1.example", "comment": "never written"},
                "confidence": 0.9,
            }
        )
        self._execute(run, gate)
        body = gate.bodies[0]
        self.assertNotIn("contract", body)
        self.assertEqual(
            sorted(body["schema"]), ["city", "email", "name", "phone", "street", "street2", "website", "zip"]
        )
        self.assertEqual(run.state, "review")
        self.assertEqual(run.gate_proposal["proposed_partner_fields"], {"website": "https://v1.example"})
        run.action_inject()
        self.assertEqual(partner.website, "https://v1.example")
        row = self.env[PROVENANCE].search([("run_id", "=", run.id)])
        self.assertEqual((row.target_model, row.target_field, row.status), ("res.partner", "website", "written"))

    def test_a_profile_run_under_v1_never_reaches_gate(self):
        self._set_param("plasticos.gate.converge_contract", "v1")
        profile = self._supplier_facility_profile("V1 Profile")
        run = self._start(profile)
        gate = _Gate(lambda body: {})
        run_id = run.id
        with self._request_rollback(), self._raises(UserError):
            self._execute(run, gate)
        self.assertEqual(gate.bodies, [])
        self.env.invalidate_all()
        run = self.env["plasticos.enrichment.run"].browse(run_id)
        self.assertEqual(run.state, "degraded")
        self.assertIn("converge contract v2", " ".join(run.validation_issues or []))

    # ── facility profile open by model definition (ADR-012 amendment (b)) ──

    def _with_declarations(self, **extra):
        """Simulate a reviewed cartridge vocabulary that also declares ``extra`` (material subject)."""
        base = gate_allowlists.PLASTICOS_CARTRIDGES["0.5.0"]
        vocabulary = gate_allowlists.CartridgeVocabulary(
            gate_allowlists._freeze({**gate_allowlists._thaw(base.declarations), **extra}),
            MappingProxyType({**base.subjects, **dict.fromkeys(extra, gate_allowlists.V2_SUBJECT_MATERIAL)}),
        )
        return patch.object(gate_allowlists, "PLASTICOS_CARTRIDGES", MappingProxyType({"0.5.0": vocabulary}))

    def test_a_same_named_eligible_facility_field_is_requested_and_written_without_an_alias(self):
        self.assertNotIn("freeform_notes", gate_allowlists.FACILITY_PROFILE_V2_ALIASES)
        profile = self._buyer_facility_profile("V2 Buyer Notes")
        run = self._start(profile)
        gate = _Gate(
            lambda body: _v2_reply(
                body, {"freeform_notes": {"state": "external_claim", "admitted": True, "value": "Takes mixed bales"}}
            )
        )
        with self._with_declarations(freeform_notes={"type": "string"}):
            self._execute(run, gate)
            self.assertIn("freeform_notes", [t["field"] for t in gate.bodies[0]["targets"]])
            run.action_inject()
        self.assertEqual(profile.freeform_notes, "Takes mixed bales")
        row = self._provenance(run)["freeform_notes"]
        self.assertEqual((row.status, row.target_res_id), ("written", profile.id))

    def test_a_never_target_is_refused_even_when_the_reply_proposes_it(self):
        profile = self._buyer_facility_profile("V2 Buyer Active")
        run = self._start(profile)
        proposed_active = {
            "state": "external_claim",
            "admitted": True,
            "value": False,
            "unit_status": "not_applicable",
            "confidence": 0.95,
            "sources": [_source()],
            "derivation": None,
            "declaration": {"type": "bool"},
            "conflict": None,
            "unknown_reason": None,
        }
        gate = _Gate(
            lambda body: _v2_reply(
                body,
                {
                    "contamination_tolerance": {
                        "state": "external_claim",
                        "admitted": True,
                        "value": 3.0,
                        "unit": "percent",
                    }
                },
                extra={"active": proposed_active},
            )
        )
        with self._with_declarations(active={"type": "bool"}):
            self._execute(run, gate)
            self.assertNotIn("active", [t["field"] for t in gate.bodies[0]["targets"]])
            run.action_inject()
        self.assertTrue(profile.active)
        self.assertAlmostEqual(profile.contamination_tolerance_pct, 3.0)
        self.assertNotIn("active", self._provenance(run))

    def test_an_approval_that_writes_nothing_is_not_marked_injected(self):
        profile = self._supplier_facility_profile("V2 Supplier Nothing Left")
        run = self._start(profile)
        gate = _Gate(
            lambda body: _v2_reply(
                body,
                {"min_density": {"state": "external_claim", "admitted": True, "value": 0.94, "unit": "g/cm3"}},
            )
        )
        self._execute(run, gate)
        self.assertEqual(run.state, "review")
        profile.write({"density_min": 0.92})
        with self.assertRaises(UserError):
            run.action_inject()
        self.assertEqual(run.state, "review")
        self.assertAlmostEqual(profile.density_min, 0.92)
        self.assertFalse(run.injected_at)

    # ── run target integrity ─────────────────────────────────────────────

    def test_run_partner_must_be_the_profile_partner(self):
        profile = self._supplier_facility_profile("V2 Supplier Eight")
        stranger = self._create_partner("Stranger")
        with self.assertRaises(ValidationError):
            self.env["plasticos.enrichment.run"].create({"partner_id": stranger.id, "facility_profile_id": profile.id})

    def test_a_material_profile_cannot_start_a_v2_run(self):
        """ADR-012 amendment 2026-11-13 (d): the `material` subject is a facility's capability."""
        self.assertNotIn("material_profile_id", self.env["plasticos.enrichment.run"]._fields)
        partner = self._create_partner("V2 Material Owner", supplier_rank=1)
        material = self._create_material_profile(partner=partner, polymer=self.hdpe)
        self.assertFalse(hasattr(material, "action_start_enrichment_run"))
        run = self.env["plasticos.enrichment.run"].create({"partner_id": partner.id})
        self.assertEqual(run._v2_target(), ("partner", partner))
