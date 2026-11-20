"""Documents owns the evidence Logistics asks about. Logistics never depends on Documents."""

from odoo import api, models
from odoo.exceptions import AccessError

PLASTICOS_ISO_JOURNEY = "plasticos.iso.journey"
VGM_OBLIGATION = "verified_gross_mass"


class PlasticosLogisticsRequestDocuments(models.Model):
    _inherit = "plasticos.logistics.request"

    @api.model
    def _scale_ticket_evidence_status(self, load, checker):
        """A current SCALE tag on the load means the carrier evidence is already in."""
        tag = self.env["plasticos.document.tag"].search([("code", "=", "SCALE")], order="id ASC", limit=1)
        if not tag:
            return "documents_status_not_available"
        if checker(load, tag):
            return "evidence_received"
        return False


class PlasticosIsoJourneyFactDocuments(models.Model):
    _inherit = "plasticos.iso.journey.fact"

    def _documents_vgm_evidence(self, journey, revision_key):
        """The Documents VGM verdict on this journey. Returns ``(document_id, attachment, error)``.

        The error is ``(status, reason)``. The verified row must exist and be about this
        exact journey in its company, so no dangling or foreign document id is ever stored.
        """
        documents = self.env["plasticos.document"]
        if VGM_OBLIGATION not in documents._scoped_obligation_kinds():
            # Documents is installed but no owner (Export) declares the VGM obligation.
            return None, None, ("not_available", "no installed owner declares the verified_gross_mass obligation")
        try:
            verdict = documents.get_scoped_evidence_verdict(
                journey.company_id.id, PLASTICOS_ISO_JOURNEY, journey.id, VGM_OBLIGATION, revision_key
            )
        except AccessError:
            return None, None, ("blocked", "the Documents verdict is not visible to you")
        if verdict.get("status") != "applied" or not verdict.get("record_id"):
            reason = verdict.get("reason") or verdict.get("status")
            return None, None, ("blocked", f"the Documents verified_gross_mass verdict is not applied: {reason}")
        document = documents.browse(int(verdict["record_id"])).exists()
        if not document:
            return None, None, ("blocked", "the verified Documents record does not exist")
        try:
            document.check_access("read")
        except AccessError:
            return None, None, ("blocked", "the verified Documents record is not visible to you")
        if document.res_model != PLASTICOS_ISO_JOURNEY or document.res_id != journey.id:
            return None, None, ("blocked", "the verified Documents record is not about this container journey")
        if document.subject_company_id != journey.company_id:
            return None, None, ("blocked", "the verified Documents record is not established in this company")
        if not document.attachment_id:
            return None, None, ("blocked", "the verified Documents record has no original")
        return document.id, document.attachment_id, None
