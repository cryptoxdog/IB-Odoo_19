"""Operator-only rejection inspection and explicit candidate feedback, never commerce writes."""

import json

from odoo import fields, models
from odoo.addons.plasticos_broker_intelligence.services.reasoning import build_response
from odoo.exceptions import UserError

from ..services.rejection import CODES, candidate_code, response, select_unique_reference


class BrokerRejectionWizard(models.TransientModel):
    _name = "plasticos.broker.rejection.wizard"
    _description = "Explain Recorded Buyer Rejection"

    source_model = fields.Selection(
        [("plasticos.offer", "Offer"), ("plasticos.match.result", "Match Result")], required=True
    )
    source_id = fields.Integer(required=True)
    suggested_code = fields.Selection([(x, x.replace("_", " ")) for x in CODES])
    buyer_statement = fields.Text(readonly=True)
    explanation = fields.Text(readonly=True)
    observation = fields.Text(
        help="Optional broker correction or clarification; create a separate candidate feedback receipt."
    )
    evidence_ref = fields.Char(help="Exact evidence document or conversation reference required for feedback.")

    def _source(self):
        self.ensure_one()
        target = self.env["plasticos.broker.advice.service"]._authorized_target(self.source_model, self.source_id)
        if self.source_model not in ("plasticos.offer", "plasticos.match.result"):
            raise UserError("Only offer and match rejections are supported.")
        return target

    def action_explain(self):
        self.ensure_one()
        src = self._source()
        raw = src.rejection_reason or ""
        self.buyer_statement = raw
        code, _ = candidate_code(raw, self.suggested_code)
        approved = None
        deferred = []
        if code:
            service = self.env["plasticos.broker.advice.service"]
            found = self.env["plasticos.broker.knowledge"].search(
                [
                    ("category", "=", "rejection"),
                    ("name", "=", code),
                    ("state", "=", "approved"),
                    (
                        "applies_to",
                        "in",
                        ["all", "offer" if self.source_model == "plasticos.offer" else "match_result"],
                    ),
                    *service._knowledge_company_domain(src),
                ],
                limit=2,
            )
            found, ambiguity = select_unique_reference(found)
            deferred.extend(ambiguity)
            if found:
                # A human-approved reference is not necessarily applicable to this
                # source. Apply the same structured prerequisite and citation gates
                # as ordinary broker-advice/v2 before surfacing any guidance.
                advice = build_response(
                    self.source_model,
                    src.id,
                    src.write_date or src.create_date,
                    code,
                    service._facts(src),
                    [
                        {
                            "state": found.state,
                            "stable_key": found.stable_key,
                            "version": found.version,
                            "name": found.name,
                            "reviewed_meaning": found.reviewed_meaning,
                            "topic_tags": found.topic_tags,
                            "applies_to": found.applies_to,
                            "prerequisite_keys": found.prerequisite_keys,
                            "evidence_requirements": found.evidence_requirements,
                            "source_file": found.source_file,
                            "source_sha256": found.source_sha256,
                            "source_selector": found.source_selector,
                            "source_candidate_id": found.source_candidate_id,
                            "workflow_scope": found.workflow_scope,
                        }
                    ],
                )
                active = advice["approved_knowledge"]
                approved = active[0] if active else None
                deferred = advice["deferred_knowledge"]
        self.explanation = json.dumps(
            response(raw, self.suggested_code, approved, deferred_guidance=deferred),
            ensure_ascii=False,
            indent=2,
        )
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    def action_record_feedback(self):
        self.ensure_one()
        src = self._source()
        if not self.observation or not self.evidence_ref:
            raise UserError("Enter the broker observation and an exact source evidence reference.")
        self.env["plasticos.broker.feedback"].create(
            {
                "source_model": self.source_model,
                "source_id": src.id,
                "observation_type": "rejection",
                "observation": self.observation,
                "evidence_ref": self.evidence_ref,
            }
        )
        return {"type": "ir.actions.act_window_close"}
