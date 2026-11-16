"""Source-bound observations that never become knowledge without separate review."""

from psycopg2 import IntegrityError

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

from ..services.evidence import is_source_rejection_evidence, legacy_observation_identity, observation_identity

_SOURCES = ("plasticos.offer", "plasticos.match.result", "plasticos.intake")


class BrokerFeedback(models.Model):
    _name = "plasticos.broker.feedback"
    _description = "Broker Outcome Observation (Candidate Only)"
    _order = "id desc"

    _unique_observation_identity = models.UniqueIndex("(provenance_digest)")

    company_id = fields.Many2one(
        "res.company", required=True, readonly=True, index=True, default=lambda self: self.env.company
    )
    actor_id = fields.Many2one("res.users", required=True, readonly=True, default=lambda self: self.env.user)
    company_scope_basis = fields.Selection(
        [
            ("source_company", "Explicit Source Company"),
            ("operator_company", "Operator Company (Source Company Not Recorded)"),
        ],
        readonly=True,
        required=True,
        default="operator_company",
        help="An operator-context company is not proof of the source's legal-company ownership.",
    )
    source_model = fields.Selection([(x, x) for x in _SOURCES], required=True, readonly=True)
    source_id = fields.Integer(required=True, readonly=True)
    source_revision = fields.Char(required=True, readonly=True)
    observed_source_state = fields.Char(readonly=True)
    observed_reason = fields.Text(readonly=True)
    observation_type = fields.Selection(
        [
            ("rejection", "Rejection"),
            ("correction", "Broker Correction"),
            ("quality", "Quality Concern"),
            ("clarification", "Clarification"),
            ("intake_outcome", "Intake Outcome (Not Settlement)"),
        ],
        required=True,
        readonly=True,
    )
    observation = fields.Text(required=True, readonly=True)
    evidence_ref = fields.Char(required=True, readonly=True)
    provenance_digest = fields.Char(required=True, readonly=True)
    verified_against_source = fields.Boolean(
        readonly=True,
        default=False,
        help="True only for an exact verbatim rejected Offer/Match statement; never a measurement or buyer-spec verification.",
    )

    @api.model
    def _authorized_source(self, model, res_id):
        if model not in _SOURCES:
            raise UserError("Unsupported observation owner.")
        # Do not maintain a second interpretation of company and source-read rights.
        return self.env["plasticos.broker.advice.service"]._authorized_target(model, res_id)

    @api.model
    def _find_replay(self, vals, legacy_digest):
        """Replay within the same permitted company; reject legacy hash collisions."""
        candidates = self.search(
            [
                (
                    "provenance_digest",
                    "in",
                    [
                        vals["provenance_digest"],
                        legacy_digest,
                    ],
                )
            ]
        )
        for row in candidates:
            if (
                row.source_model == vals["source_model"]
                and row.source_id == vals["source_id"]
                and row.source_revision == vals["source_revision"]
                and row.actor_id.id == vals["actor_id"]
                and row.company_id.id == vals["company_id"]
                and row.company_scope_basis == vals["company_scope_basis"]
                and row.observation_type == vals["observation_type"]
                and row.evidence_ref == vals["evidence_ref"]
                and row.observation == vals["observation"]
            ):
                return row
        return self.browse()

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not str(vals.get("evidence_ref") or "").strip() or not str(vals.get("observation") or "").strip():
                raise ValidationError("An attributable evidence reference and observation are required.")
            source = self._authorized_source(vals.get("source_model"), vals.get("source_id"))
            for forbidden in (
                "company_id",
                "actor_id",
                "company_scope_basis",
                "source_revision",
                "provenance_digest",
                "verified_against_source",
                "observed_source_state",
                "observed_reason",
            ):
                if forbidden in vals:
                    raise UserError("Observation provenance is derived from the real source, not from user payloads.")
            source_state = (
                source["state"] if "state" in source._fields else source["status"] if "status" in source._fields else ""
            ) or ""
            rejection = (source.rejection_reason or "") if "rejection_reason" in source._fields else ""
            actual = is_source_rejection_evidence(
                source._name,
                source_state,
                rejection,
                vals["observation_type"],
                vals["observation"],
            )
            explicit_company = source.company_id if "company_id" in source._fields else False
            company = explicit_company or self.env.company
            scope_basis = "source_company" if explicit_company else "operator_company"
            revision = str(source.write_date or source.create_date or "unknown")
            digest = observation_identity(
                source_model=source._name,
                source_id=source.id,
                source_revision=revision,
                scope_basis=scope_basis,
                company_id=company.id,
                observation_type=vals["observation_type"],
                actor_id=self.env.user.id,
                evidence_ref=vals["evidence_ref"],
                observation=vals["observation"],
            )
            vals.update(
                {
                    "company_id": company.id,
                    "actor_id": self.env.user.id,
                    "company_scope_basis": scope_basis,
                    "source_revision": revision,
                    "observed_source_state": source_state,
                    "observed_reason": rejection,
                    "verified_against_source": actual,
                    "provenance_digest": digest,
                }
            )
        legacy_digests = [
            legacy_observation_identity(
                source_model=vals["source_model"],
                source_id=vals["source_id"],
                source_revision=vals["source_revision"],
                observation_type=vals["observation_type"],
                actor_id=vals["actor_id"],
                evidence_ref=vals["evidence_ref"],
                observation=vals["observation"],
            )
            for vals in vals_list
        ]
        identities = [vals["provenance_digest"] for vals in vals_list]
        if len(identities) != len(set(identities)):
            raise UserError("A single request cannot submit a duplicate observation twice.")
        if len(vals_list) == 1:
            earlier = self._find_replay(vals_list[0], legacy_digests[0])
            if earlier:
                return earlier
        try:
            with self.env.cr.savepoint():
                return super().create(vals_list)
        except IntegrityError as exc:
            if len(vals_list) == 1:
                earlier = self._find_replay(vals_list[0], legacy_digests[0])
                if earlier:
                    return earlier
            raise UserError("An observation with this exact source revision and evidence already exists.") from exc

    def write(self, vals):
        raise UserError("Outcome observations are append-only; create a correction instead.")

    def unlink(self):
        raise UserError("Outcome observations cannot be deleted.")
