"""Two web leads share one opportunity. Each keeps its own generated block."""

import base64

from odoo.tests import TransactionCase, tagged


def _spec_bundle(text, value):
    seller = {}
    seller["material_description"] = text
    row = {}
    row["property"] = "MFI"
    row["value"] = value
    row["unit"] = "g/10min"
    row["test_conditions"] = "190C/2.16kg"
    row["source_refs"] = ["seller.material_description"]
    row["conflicts"] = []
    bundle = {}
    bundle["seller"] = seller
    bundle["document_specifications"] = [row]
    return bundle


@tagged("post_install", "-at_install", "plasticos", "crm_bridge")
class TestTwoWebLeadsOneMaterial(TransactionCase):
    """One material row, one description block per web lead, one PDF original each."""

    def _lead(self, lead_id, text, value):
        return self.env["plasticos.web.lead"].create(
            {
                "lead_id": lead_id,
                "company_name": "Shared Lot Co",
                "evidence_bundle": _spec_bundle(text, value),
            }
        )

    def _pdf(self, lead, payload, name):
        vals = {}
        vals["name"] = name
        vals["datas"] = base64.b64encode(payload)
        vals["mimetype"] = "application/pdf"
        vals["res_model"] = "plasticos.web.lead"
        vals["res_id"] = lead.id
        return self.env["ir.attachment"].create(vals)

    def _description(self, opportunity):
        opportunity.invalidate_recordset(["description"])
        return str(opportunity.description or "")

    def _block(self, description, lead, kind):
        token = f"plasticos-{kind} plasticos-web-lead-{lead.id}"
        start = description.find(token)
        self.assertGreaterEqual(start, 0, description)
        end = description.find("</div>", start)
        self.assertGreater(end, start, description)
        return description[start:end]

    def test_two_leads_keep_separate_blocks_and_one_material_source(self):
        opportunity_vals = {}
        opportunity_vals["name"] = "Shared opportunity"
        opportunity_vals["type"] = "opportunity"
        opportunity_vals["description"] = "<p>Broker note outside the blocks.</p>"
        opportunity = self.env["crm.lead"].create(opportunity_vals)
        first = self._lead("WL-SHARED-A", "HDPE pellets. MFI 7.5 g/10min.", 7.5)
        second = self._lead("WL-SHARED-B", "HDPE pellets. MFI 4.2 g/10min.", 4.2)
        first.crm_lead_id = opportunity
        second.crm_lead_id = opportunity
        pdf_first = self._pdf(first, b"%PDF-1.4 lead-a", "a.pdf")
        pdf_second = self._pdf(second, b"%PDF-1.4 lead-b", "b.pdf")

        first._propagate_one_pass_spec(opportunity)
        first._propagate_one_pass_spec(opportunity)
        after_replay = self._description(opportunity)
        self.assertEqual(after_replay.count(f"plasticos-spec plasticos-web-lead-{first.id}"), 1)
        self.assertIn("7.5", self._block(after_replay, first, "spec"))
        self.assertIn("Broker note outside the blocks.", after_replay)

        second._propagate_one_pass_spec(opportunity)
        shared = self._description(opportunity)
        self.assertIn("7.5", self._block(shared, first, "spec"))
        self.assertIn("4.2", self._block(shared, second, "spec"))
        self.assertIn(f"[plasticos-pdf:{pdf_first.id}]", self._block(shared, first, "pdf"))
        self.assertIn(f"[plasticos-pdf:{pdf_second.id}]", self._block(shared, second, "pdf"))
        self.assertIn("Broker note outside the blocks.", shared)
        material = opportunity.opportunity_material_ids
        self.assertEqual(len(material), 1)
        self.assertEqual(material.source_web_lead_id, first)
        self.assertAlmostEqual(material.melt_flow_index, 7.5)
        self.assertFalse(material.density)
        self.assertFalse(material.moisture_percent)
        self.assertFalse(material.quantity_per_load_lbs)

        first.evidence_bundle = _spec_bundle("HDPE pellets. MFI 6.1 g/10min.", 6.1)
        first._propagate_one_pass_spec(opportunity)
        opportunity._plasticos_copy_web_lead_pdfs()
        corrected = self._description(opportunity)
        first_block = self._block(corrected, first, "spec")
        second_block = self._block(corrected, second, "spec")
        self.assertIn("6.1", first_block)
        self.assertNotIn("7.5", first_block)
        self.assertIn("4.2", second_block)
        self.assertEqual(corrected.count(f"plasticos-spec plasticos-web-lead-{second.id}"), 1)
        self.assertIn("Broker note outside the blocks.", corrected)
        self.assertAlmostEqual(material.melt_flow_index, 6.1)
        self.assertEqual(material.source_web_lead_id, first)
        self.assertEqual(self.env["ir.attachment"].search_count([("checksum", "=", pdf_first.checksum)]), 1)
        self.assertEqual(self.env["ir.attachment"].search_count([("checksum", "=", pdf_second.checksum)]), 1)
        self.assertFalse(
            self.env["ir.attachment"].search(
                [
                    ("res_model", "=", "crm.lead"),
                    ("res_id", "=", opportunity.id),
                    ("mimetype", "=", "application/pdf"),
                ]
            )
        )
        self.assertEqual(pdf_first.res_model, "plasticos.web.lead")
        self.assertEqual(pdf_second.res_id, second.id)
