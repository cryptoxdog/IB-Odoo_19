"""Documents owns the VGM verdict Logistics records. These cases construct plasticos.document."""

from unittest.mock import patch

from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase, tagged

JOURNEY = "plasticos.iso.journey"
FACT = "plasticos.iso.journey.fact"


@tagged("post_install", "-at_install", "plasticos", "documents", "export")
class TestDocumentsVgmEvidence(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.lb = cls.env.ref("uom.product_uom_lb")
        cls.kg = cls.env.ref("uom.product_uom_kgm")

    def _attach(self, record, name="evidence.pdf"):
        return self.env["ir.attachment"].create(
            {"name": name, "raw": b"%PDF-1.4 documents vgm evidence", "res_model": record._name, "res_id": record.id}
        )

    def _journey(self, cycle, iso="MSCU1234567"):
        result = self.env[JOURNEY].action_register_iso_journey(
            self.company.id, cycle, "40HC", None, iso, "SL-9", f"op-{cycle}"
        )
        self.assertEqual(result["status"], "applied")
        return self.env[JOURNEY].browse(result["record_id"])

    def _fact(self, journey, kind):
        return self.env[FACT].search([("journey_id", "=", journey.id), ("fact_kind", "=", kind)])

    def _weigh(self, kind, journey, weight, uom, basis, attachment, reference, key="w"):
        command = getattr(self.env[FACT], f"action_record_{kind}")
        return command(journey.id, weight, uom.id, basis, attachment.id if attachment else None, reference, key)

    def test_vgm_from_the_documents_verdict(self):
        """A verified Documents verified_gross_mass row on the journey supplies the original."""
        journey = self._journey("DOCS-VGM")
        original = self._attach(journey, "vgm-declaration.pdf")
        tag = self.env["plasticos.document.tag"].search([], limit=1)
        self.assertTrue(tag, "the Documents fixture seeds document tags")
        shell = self.env["plasticos.document"].create(
            {
                "name": "VGM declaration",
                "tag_id": tag.id,
                "res_model": "documents.document",
                "res_id": 0,
                "attachment_id": original.id,
            }
        )
        verifier = self.env["res.users"].create(
            {
                "name": "Docs VGM Verifier",
                "login": "docs_vgm_verifier",
                "group_ids": [
                    (
                        6,
                        0,
                        [
                            self.env.ref("base.group_user").id,
                            self.env.ref("plasticos_documents.group_documents_user").id,
                        ],
                    )
                ],
            }
        )
        document = shell.with_user(verifier)._associate_scope(
            JOURNEY,
            journey.id,
            "carrier VGM mail booking-rev-3",
            obligation_kind="verified_gross_mass",
            operation_revision_key="booking-rev-3",
            coverage_key="container-1",
        )
        document.with_user(verifier).action_verify()
        document = document.with_user(self.env.user)
        self.assertEqual(document.subject_company_id, self.company)
        verdict = self.env["plasticos.document"].get_scoped_evidence_verdict(
            self.company.id, JOURNEY, journey.id, "verified_gross_mass", "booking-rev-3"
        )
        self.assertEqual(verdict, {"status": "applied", "record_id": document.id})
        other = self._attach(journey, "not-the-verified-original.pdf")
        mismatch = self._weigh(
            "verified_gross_mass", journey, 22000, self.kg, "documents_verified_gross_mass", other, "booking-rev-3"
        )
        self.assertEqual(mismatch["status"], "blocked")
        result = self._weigh(
            "verified_gross_mass", journey, 22000, self.kg, "documents_verified_gross_mass", None, "booking-rev-3"
        )
        self.assertEqual(result["status"], "applied")
        fact = self._fact(journey, "verified_gross_mass")
        self.assertEqual((fact.verified_document_id, fact.evidence_attachment_id), (document.id, original))
        self.assertEqual((fact.weight, fact.weight_uom_id), (22000.0, self.kg))

    def test_documents_basis_refuses_dangling_or_foreign_documents(self):
        """The verdict's document must exist and be about this exact journey in its company."""
        journey = self._journey("DOCS-VGM-DANGLING")
        other_journey = self._journey("DOCS-VGM-OTHER", iso="TGHU7654321")
        tag = self.env["plasticos.document.tag"].search([], limit=1)
        foreign = self.env["plasticos.document"].create(
            {
                "name": "VGM of another container",
                "res_model": JOURNEY,
                "res_id": other_journey.id,
                "attachment_id": self._attach(other_journey, "other-vgm.pdf").id,
                "tag_id": tag.id,
            }
        )
        found = self.env["plasticos.document"].search([], order="id desc", limit=1)
        missing_id = (found.id if found else 0) + 1000
        document_class = type(self.env["plasticos.document"])
        for label, record_id in (("dangling", missing_id), ("other journey", foreign.id)):
            with (
                self.subTest(label=label),
                patch.object(
                    document_class,
                    "get_scoped_evidence_verdict",
                    lambda *args, record_id=record_id: {"status": "applied", "record_id": record_id},
                ),
            ):
                result = self._weigh(
                    "verified_gross_mass", journey, 9, self.lb, "documents_verified_gross_mass", None, "rev-1"
                )
                self.assertEqual(result["status"], "blocked")
        self.assertFalse(self._fact(journey, "verified_gross_mass"))

    def test_unverified_documents_verdict_refuses_vgm(self):
        """An unverified Documents verdict does not record a weight."""
        journey = self._journey("DOCS-VGM-UNVERIFIED")
        document_class = type(self.env["plasticos.document"])
        with patch.object(
            document_class,
            "get_scoped_evidence_verdict",
            lambda *args: {"status": "blocked", "reason": "evidence awaits verification"},
        ):
            result = self._weigh(
                "verified_gross_mass", journey, 9, self.lb, "documents_verified_gross_mass", None, "rev-1"
            )
        self.assertEqual(result["status"], "blocked")
        self.assertFalse(self._fact(journey, "verified_gross_mass"))

    def test_documents_vgm_edge_cases(self):
        """No declared VGM obligation is not_available; a foreign company or a hidden row is blocked."""
        journey = self._journey("DOCS-VGM-N4")
        document_class = type(self.env["plasticos.document"])
        with patch.object(document_class, "_scoped_obligation_kinds", lambda model: frozenset()):
            result = self.env[FACT].action_record_verified_gross_mass(
                journey.id, 9, self.kg.id, "documents_verified_gross_mass", None, "rev", "n4-a"
            )
        self.assertEqual(result["status"], "not_available")
        tag = self.env["plasticos.document.tag"].search([], limit=1)
        unestablished = self.env["plasticos.document"].create(
            {
                "name": "VGM, company not established",
                "res_model": JOURNEY,
                "res_id": journey.id,
                "attachment_id": self._attach(journey, "vgm.pdf").id,
                "tag_id": tag.id,
            }
        )
        self.assertFalse(unestablished.subject_company_id)
        applied = {"status": "applied", "record_id": unestablished.id}
        with patch.object(document_class, "get_scoped_evidence_verdict", lambda *args: applied):
            result = self.env[FACT].action_record_verified_gross_mass(
                journey.id, 9, self.kg.id, "documents_verified_gross_mass", None, "rev", "n4-b"
            )
        self.assertEqual(result["status"], "blocked")

        def hidden(records, operation):
            raise AccessError("hidden by a record rule")

        with (
            patch.object(document_class, "get_scoped_evidence_verdict", lambda *args: applied),
            patch.object(document_class, "check_access", hidden),
        ):
            result = self.env[FACT].action_record_verified_gross_mass(
                journey.id, 9, self.kg.id, "documents_verified_gross_mass", None, "rev", "n4-c"
            )
        self.assertEqual(result["status"], "blocked")
        self.assertFalse(self._fact(journey, "verified_gross_mass"))
