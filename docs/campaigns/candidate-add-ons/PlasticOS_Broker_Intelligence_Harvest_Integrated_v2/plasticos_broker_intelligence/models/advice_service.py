"""Permission-preserving, read-only fact adapter for broker-advice/v2."""

from odoo import api, models
from odoo.exceptions import AccessError, UserError

from ..services.evidence import fact, mfi_basis
from ..services.reasoning import ALLOWED, build_response


class BrokerAdviceService(models.AbstractModel):
    _name = "plasticos.broker.advice.service"
    _description = "Read-only Broker Advice Service"

    @api.model
    def _authorized_target(self, model, record_id):
        if model not in ALLOWED:
            raise UserError("Advice is limited to approved Odoo record types.")
        if isinstance(record_id, bool) or isinstance(record_id, float):
            raise UserError("A positive integer source record ID is required.")
        if isinstance(record_id, str) and not record_id.isdecimal():
            raise UserError("A positive integer source record ID is required.")
        try:
            source_id = int(record_id)
        except (TypeError, ValueError) as exc:
            raise UserError("A valid existing source record ID is required.") from exc
        if source_id <= 0:
            raise UserError("A positive existing source record ID is required.")
        try:
            source = self.env[model].browse(source_id).exists()
        except KeyError as exc:
            raise UserError("Requested Odoo module is not installed.") from exc
        if not source:
            raise UserError("Source record was not found.")
        source.check_access("read")
        if "company_id" in source._fields and source.company_id and source.company_id not in self.env.companies:
            raise AccessError("Source is outside the user's permitted companies.")
        return source

    @api.model
    def _field(self, record, name, *, relational=False):
        if name not in record._fields:
            return None
        try:
            value = record[name]
        except AccessError:
            return None
        if relational:
            return value.display_name if value else None
        return value

    @api.model
    def _facts(self, record):
        model = record._name
        result = {}
        if model == "plasticos.intake":
            for name, key in (("polymer_id", "polymer"), ("form_id", "form"), ("material_grade_id", "material_grade")):
                result[key] = fact(self._field(record, name, relational=True), "reported")
            # Odoo's quantity has a default (36,000 lbs on this Staging revision): it is NOT verified weight.
            result["quantity_lbs"] = fact(
                self._field(record, "quantity_per_load_lbs"), "recorded_default_possible", zero_ambiguous=True
            )
            result["moisture_pct"] = fact(
                self._field(record, "moisture_pct"), "recorded_unverified", zero_ambiguous=True
            )
            result["contamination_pct"] = fact(
                self._field(record, "contamination_pct"), "recorded_unverified", zero_ambiguous=True
            )
            result["mfi_value"], result["mfi_conditions"] = mfi_basis(self._field(record, "mfi_value"), None)
            result["notes"] = fact(self._field(record, "intake_notes"), "reported")
        elif model == "plasticos.web.lead":
            seller = self._field(record, "canonical_payload") or {}
            seller = seller if isinstance(seller, dict) else {}
            result["polymer"] = fact(seller.get("polymer"), "seller_reported")
            result["form"] = fact(seller.get("form"), "seller_reported")
            result["quantity_lbs"] = fact(seller.get("estimated_lbs_per_load"), "seller_reported", zero_ambiguous=True)
            result["review_state"] = fact(self._field(record, "review_status"), "workflow_state")
        elif model in ("plasticos.offer", "plasticos.match.result"):
            result["rejection_reason"] = fact(
                self._field(record, "rejection_reason"), "counterparty_statement_unverified"
            )
            result["state"] = fact(self._field(record, "state"), "workflow_state")
            buyer_field = "buyer_id" if model == "plasticos.offer" else "buyer_partner_id"
            result["buyer"] = fact(self._field(record, buyer_field, relational=True), "recorded_identity")
            result["buyer_spec"] = fact(None, "unknown")
            if model == "plasticos.offer":
                result["material_summary"] = fact(self._field(record, "material_summary"), "recorded_summary")
            else:
                result["match_reasoning"] = fact(self._field(record, "match_reasoning"), "external_proposal")
        return result

    @api.model
    def _knowledge_company_domain(self, target):
        """A record's legal-company context, not every company the broker can access.

        Owners without an explicit company remain tied to the active operator
        company. The global knowledge pool is available in either case.
        """
        company = target.company_id if "company_id" in target._fields and target.company_id else self.env.company
        if company.id not in self.env.companies.ids:
            raise AccessError("Knowledge context is outside the user's permitted companies.")
        return ["|", ("company_id", "=", False), ("company_id", "=", company.id)]

    @api.model
    def advise_v2(self, source_model, source_id, question=""):
        target = self._authorized_target(source_model, source_id)
        facts = self._facts(target)
        scope = ALLOWED[source_model]
        clauses = [
            ("state", "=", "approved"),
            ("applies_to", "in", ["all", scope]),
            *self._knowledge_company_domain(target),
        ]
        # Fetch one sentinel row: a bounded lookup must never silently claim
        # that the 150 examined candidates are the complete knowledge universe.
        knowledge = self.env["plasticos.broker.knowledge"].search(clauses, limit=151)
        truncated = len(knowledge) > 150
        knowledge = knowledge[:150]
        rows = [
            {
                "state": x.state,
                "stable_key": x.stable_key,
                "version": x.version,
                "name": x.name,
                "reviewed_meaning": x.reviewed_meaning,
                "topic_tags": x.topic_tags,
                "applies_to": x.applies_to,
                "prerequisite_keys": x.prerequisite_keys,
                "evidence_requirements": x.evidence_requirements,
                "source_file": x.source_file,
                "source_sha256": x.source_sha256,
                "source_selector": x.source_selector,
                "source_candidate_id": x.source_candidate_id,
                "workflow_scope": x.workflow_scope,
            }
            for x in knowledge
        ]
        return build_response(
            source_model,
            target.id,
            target.write_date or target.create_date,
            str(question or "")[:1500],
            facts,
            rows,
            retrieval_complete=not truncated,
            candidates_examined=len(rows),
        )

    @api.model
    def advise_v1(self, source_model, source_id, question=""):
        """Compatibility entrypoint. Exact absent standalone-v1 call signature remains unverified."""
        v2 = self.advise_v2(source_model, source_id, question)
        return {
            "schema": "broker-advice/v1",
            "advice": v2["next_human_actions"],
            "citations": [r["citation"] for r in v2["approved_knowledge"]],
            "known_facts": v2["facts"],
            "unknowns": v2["unknowns"],
            "abstain": v2["uncertainty"] == "unresolved",
        }
