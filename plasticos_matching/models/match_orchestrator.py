"""Gate-only match orchestrator (mothball M2/M3). No local scoring/discovery."""

from __future__ import annotations

import logging

from odoo import _, api, models
from odoo.exceptions import AccessError, UserError, ValidationError

from ..canonical_digest import _canonical_digest
from .match_run import RECEIPT_WRITE_CONTEXT

_logger = logging.getLogger(__name__)

_RETRYABLE = "retryable"
_PERMANENT = "permanent"
_UNKNOWN = "unknown"

# Match-run columns the durable failure record carries when a run that already
# holds a Gate receipt fails later in the same request (result persistence).
# Identity plus receipt evidence; the failure state is merged on top.
_DURABLE_RUN_FIELDS = (
    "intake_id",
    "supplier_partner_id",
    "mode",
    "engine",
    "availability_status",
    "request_attempt",
    "retry_of_id",
    "operation_id",
    "request_fingerprint",
    "gate_packet_id",
    "gate_correlation_id",
    "gate_query_id",
    "gate_contract_version",
    "gate_domain_spec_version",
    "gate_model_version",
    "gate_response_digest",
    "match_count",
)


def _receipt_text(value):
    """Allow only scalar text to cross from an untrusted Gate payload into an Odoo Char field."""
    return value if isinstance(value, str) and value.strip() else False


class PlasticosMatchOrchestrator(models.AbstractModel):
    """Orchestrates buyer matching exclusively through Constellation Gate.

    Hard rules (ADR-003-single / M2 / M3 / ADR-013):
    - No Neo4j / local Stage-1 candidate discovery in this addon
    - No silent fallback to plasticos.buyer.matcher local path
    - Gate failures are classified, audited on plasticos.match.run, and fail closed
    - The failure receipt is persisted on an owned committed cursor AFTER the
      request transaction is rolled back, so it survives the RPC rollback that
      the raised UserError triggers (same I2/I3 pattern as enrichment runs)
    - Retryable failures expose operator retry; never substitute empty success
    """

    _name = "plasticos.match.orchestrator"
    _description = "Gate-Only Match Orchestrator"

    @api.model
    def _state_for_failure(self, failure_class: str) -> str:
        if failure_class == _RETRYABLE:
            return "retryable"
        if failure_class == _PERMANENT:
            return "failed"
        return "degraded"

    @api.model
    def _rollback_then_persist_failed_run_durable(self, run_id, vals):
        """Roll the failed request transaction back, then persist the failure receipt durably.

        Mirrors ``plasticos.enrichment.run._rollback_then_persist_operator_state``
        (I2/I3). A ``UserError`` makes the RPC layer roll the request transaction
        back, so a run written inside that transaction vanishes together with its
        classified failure. Rolling back FIRST releases every row lock the ambient
        transaction holds, so the owned cursor below never waits on it.

        Matching differs from enrichment in one respect: the run is created inside
        the request that fails, so the rollback discards the row itself. The
        durable write therefore re-creates the run when ``run_id`` no longer
        exists and updates it when a caller that owns its transaction committed
        it beforehand. The re-created run carries the exact ``operation_id`` and
        ``request_fingerprint`` Gate received; that identity names the ambient run
        id the rollback discarded, which is the evidence, not a defect.

        ``run_id`` and ``vals`` are primitives on purpose: recordset state captured
        before the rollback is not trustworthy afterwards.
        """
        self.env.cr.rollback()
        return self._persist_failed_run_durable(run_id, vals)

    @api.model
    def _persist_failed_run_durable(self, run_id, vals):
        """Create or update the failure receipt on an owned cursor and commit it.

        Only safe once the transaction that failed has been rolled back. The
        operator note on the intake rides the same committed cursor, so the
        reason and the retry entry point stay visible after the RPC rollback.
        """
        with self.pool.cursor() as cr:
            env = api.Environment(cr, self.env.uid, dict(self.env.context))
            MatchRun = env["plasticos.match.run"].with_context(**{RECEIPT_WRITE_CONTEXT: True})
            run = MatchRun.browse(run_id).exists() if run_id else MatchRun.browse()
            if run:
                run.write(vals)
            else:
                run = MatchRun.create(vals)
            # The operator note lands on the intake when the run has one, else on
            # the run itself (a lot run from a native opportunity has no intake).
            note_target = env["plasticos.intake"].browse(vals["intake_id"]) if vals.get("intake_id") else run
            note_target.message_post(
                body=_(
                    "Gate match %(state)s (%(failure)s): %(error)s — match run %(run)s. "
                    "Fix the cause, then use Retry Gate Match; no local matching runs on failure.",
                    state=vals.get("state"),
                    failure=vals.get("failure_class") or _UNKNOWN,
                    error=vals.get("error_message") or "",
                    run=run.id,
                ),
                message_type="notification",
                subtype_xmlid="mail.mt_note",
            )
            cr.commit()
            return run.id

    @api.model
    def _durable_run_vals(self, run):
        """Snapshot a run's identity and receipt as primitives before the ambient transaction is rolled back."""
        names = list(_DURABLE_RUN_FIELDS) + [
            name for name in run._plasticos_durable_lineage_fields() if name in run._fields
        ]
        data = run.read(names, load=None)[0]
        return {name: data[name] for name in names}

    @api.model
    def run_match_for_intake(self, intake, max_results=20, mode="strict", *, retry_of=None):
        """Execute Gate match for one intake; return (run, matches).

        Every classified failure is recorded on a ``plasticos.match.run`` that
        survives the request transaction, then ``UserError`` is raised. No local
        matcher scoring runs under any failure class.
        """
        intake.ensure_one()
        intake._plasticos_require_match_material()
        if not intake.partner_id:
            raise UserError(_("Intake has no supplier partner."))
        if not intake.material_profile_id:
            raise UserError(
                _("Intake '%s' has no material profile. Link a material profile before matching.")
                % (intake.display_name,)
            )

        from odoo.addons.plasticos_gate.services.gate_builders import build_match_request

        base_vals = {
            "intake_id": intake.id,
            "supplier_partner_id": intake.partner_id.id,
        }

        def build_request(run):
            return build_match_request(
                self.env,
                intake=intake,
                match_run=run,
                top_n=max_results,
                mode=mode or "strict",
            )

        return self._run_gate_match(base_vals, build_request, max_results=max_results, mode=mode, retry_of=retry_of)

    @api.model
    def run_match_for_lot(
        self,
        *,
        supplier_partner_id,
        snapshot,
        run_vals=None,
        intake=None,
        max_results=20,
        mode="strict",
        retry_of=None,
    ):
        """Execute Gate match for one frozen lot; return (run, matches).

        The request is built from ``snapshot`` (the approved lot), never from a
        live profile. ``run_vals`` carries lineage columns owned by the caller
        (opportunity, approved lot). ``intake`` is optional source evidence; a
        lot with none creates no synthetic intake and sends no facility
        evidence unless the snapshot carries it. Same Gate-only failure
        contract as ``run_match_for_intake``.
        """
        if not supplier_partner_id:
            raise UserError(_("Lot has no supplier partner."))
        if not isinstance(snapshot, dict) or not snapshot:
            raise UserError(_("Lot has no frozen snapshot to build the Gate request from."))

        from odoo.addons.plasticos_intake.match_material import missing_match_material

        missing = missing_match_material(snapshot)
        if missing:
            raise UserError(
                _(
                    "The approved lot cannot be matched: %(missing)s not set in its frozen material. "
                    "Fill it on the opportunity material, then match again.",
                    missing=" and ".join(missing),
                )
            )

        from odoo.addons.plasticos_gate.services.gate_builders import build_match_request

        base_vals = {
            "intake_id": intake.id if intake else False,
            "supplier_partner_id": supplier_partner_id,
            **dict(run_vals or {}),
        }
        frozen = dict(snapshot)

        def build_request(run):
            return build_match_request(
                self.env,
                snapshot=frozen,
                match_run=run,
                top_n=max_results,
                mode=mode or "strict",
            )

        return self._run_gate_match(base_vals, build_request, max_results=max_results, mode=mode, retry_of=retry_of)

    @api.model
    def _run_gate_match(self, base_vals, build_request, *, max_results=20, mode="strict", retry_of=None):
        """One Gate execution shared by the intake and lot paths.

        ``base_vals`` names the run (intake or lot lineage, supplier);
        ``build_request(run)`` returns the typed MatchRequest for that run.
        """
        from odoo.addons.plasticos_gate.services.gate_builders import build_operation_id
        from odoo.addons.plasticos_gate.services.gate_client import send_match_action
        from odoo.addons.plasticos_gate.services.gate_config import (
            GateCapability,
            GateIntegrationError,
            classify_gate_availability,
            gate_matching_enabled,
        )
        from odoo.addons.plasticos_gate.services.gate_mappers import (
            extract_audit_metadata,
            map_match_response,
            map_match_response_to_matcher_dicts,
        )

        availability = classify_gate_availability(self.env, capability=GateCapability.MATCHING)
        # Primitives only: the failure path rolls the ambient transaction back,
        # after which recordset caches are not trustworthy.
        base_vals = {
            **base_vals,
            "mode": mode or "strict",
            "engine": "gate",
            "availability_status": availability.status,
            "request_attempt": (retry_of.request_attempt + 1) if retry_of else 1,
            "retry_of_id": retry_of.id if retry_of else False,
        }
        subject = base_vals.get("intake_id") or base_vals.get("supplier_partner_id")

        if not gate_matching_enabled(self.env):
            reasons = "; ".join(availability.reasons) or "Gate matching unavailable"
            run_id = self._rollback_then_persist_failed_run_durable(
                None,
                {
                    **base_vals,
                    "state": "failed",
                    "failure_class": _PERMANENT,
                    "error_message": reasons,
                },
            )
            raise UserError(
                _(
                    "Gate matching is not enabled (%(status)s): %(reasons)s (match run %(run)s)",
                    status=availability.status,
                    reasons=reasons,
                    run=run_id,
                )
            )

        MatchRun = self.env["plasticos.match.run"].with_context(**{RECEIPT_WRITE_CONTEXT: True})
        run = MatchRun.create({**base_vals, "state": "pending"})
        run_id = run.id
        # Receipt material captured as primitives so the durable failure record
        # carries exactly what Gate received, even after the rollback.
        receipt = {}
        try:
            request = build_request(run)
            correlation_id = request.odoo.get("correlation_id") if request.odoo else None
            operation_id = build_operation_id(
                request.odoo,
                family="matching",
                attempt=base_vals["request_attempt"],
            )
            if not operation_id:
                raise ValidationError(_("Gate match request has no durable Odoo operation identity."))
            request_payload = request.to_dict()
            receipt.update(
                {
                    "operation_id": operation_id,
                    "request_fingerprint": _canonical_digest(request_payload),
                }
            )
            # Persist the exact Odoo request identity and material fingerprint before Gate dispatch.
            run.write(dict(receipt))
            gate_result = send_match_action(
                self.env,
                payload=request_payload,
                correlation_id=correlation_id,
                idempotency_key=operation_id,
            )
            audit = extract_audit_metadata(gate_result["packet"])
            response_payload = gate_result["payload"]
            response_receipt = {
                "gate_packet_id": audit["gate_packet_id"],
                "gate_correlation_id": audit["gate_correlation_id"],
                "gate_response_digest": _canonical_digest(response_payload),
            }
            receipt.update(response_receipt)
            # Preserve Gate provenance before payload mapping. A zero-candidate response is still a receipt.
            run.write(response_receipt)
            mapped = map_match_response(response_payload)
            matches = map_match_response_to_matcher_dicts(mapped, audit_metadata=audit)
        except GateIntegrationError as exc:
            # The Gate bridge delivers the Odoo-facing category (the SDK's
            # retryability verdict projected onto retryable/permanent); this
            # shell persists it and never reclassifies Gate transport itself.
            failure = exc.failure_class or _UNKNOWN
            durable_id = self._rollback_then_persist_failed_run_durable(
                run_id,
                {
                    **base_vals,
                    **receipt,
                    "state": self._state_for_failure(failure),
                    "failure_class": failure,
                    "error_message": str(exc),
                },
            )
            _logger.warning("Gate-only match failed for %s (run %s): %s", subject, durable_id, exc)
            raise UserError(
                _(
                    "Gate match failed (%(failure)s): %(error)s (match run %(run)s)",
                    failure=failure,
                    error=exc,
                    run=durable_id,
                )
            ) from exc
        except (UserError, ValidationError) as exc:
            durable_id = self._rollback_then_persist_failed_run_durable(
                run_id,
                {
                    **base_vals,
                    **receipt,
                    "state": "failed",
                    "failure_class": _PERMANENT,
                    "error_message": str(exc),
                },
            )
            raise UserError(
                _(
                    "Gate match failed (%(failure)s): %(error)s (match run %(run)s)",
                    failure=_PERMANENT,
                    error=exc,
                    run=durable_id,
                )
            ) from exc
        except Exception as exc:  # noqa: BLE001 — boundary: not a Gate transport outcome; fail closed as degraded
            failure = _UNKNOWN
            durable_id = self._rollback_then_persist_failed_run_durable(
                run_id,
                {
                    **base_vals,
                    **receipt,
                    "state": self._state_for_failure(failure),
                    "failure_class": failure,
                    "error_message": str(exc) or type(exc).__name__,
                },
            )
            _logger.exception("Gate-only match unexpected error for %s (run %s)", subject, durable_id)
            raise UserError(
                _(
                    "Gate match failed (%(failure)s): %(error)s (match run %(run)s)",
                    failure=failure,
                    error=str(exc) or type(exc).__name__,
                    run=durable_id,
                )
            ) from exc

        # Apply exclusion policy (identity: plasticos.match.exclusion)
        excluded = set(self.env["plasticos.match.exclusion"].get_excluded_buyer_ids(base_vals["supplier_partner_id"]))
        if excluded:
            matches = [m for m in matches if m.get("buyer_id") not in excluded]

        matches = matches[:max_results]
        run.write(
            {
                "state": "ok",
                "match_count": len(matches),
                "gate_query_id": _receipt_text(mapped.query_id),
                "gate_contract_version": _receipt_text(mapped.contract_version),
                "gate_domain_spec_version": _receipt_text(mapped.domain_spec_version),
                "gate_model_version": _receipt_text(mapped.model_version),
                "failure_class": False,
                "error_message": False,
            }
        )
        return run, matches

    @api.model
    def retry_match_run(self, prior_run):
        """Retry a prior non-ok run. Suppresses duplicate retries while pending."""
        prior_run.ensure_one()
        if prior_run.state == "ok":
            raise UserError(_("Match run %s already succeeded.") % prior_run.id)
        pending = self.env["plasticos.match.run"].search(
            [
                ("state", "=", "pending"),
                ("retry_of_id", "=", prior_run.id),
            ],
            limit=1,
        )
        if pending:
            raise UserError(_("A retry is already pending for run %s (pending run %s).") % (prior_run.id, pending.id))
        if prior_run.intake_id and not prior_run._plasticos_lot_retry_subject():
            run, matches = self.run_match_for_intake(
                prior_run.intake_id,
                max_results=20,
                mode=prior_run.mode or "strict",
                retry_of=prior_run,
            )
        else:
            subject = prior_run._plasticos_lot_retry_subject()
            if not subject:
                raise UserError(
                    _("Match run %s has neither an intake nor an approved lot to retry from.") % prior_run.id
                )
            run, matches = self.run_match_for_lot(
                supplier_partner_id=subject["supplier_partner_id"],
                snapshot=subject["snapshot"],
                run_vals=subject.get("run_vals"),
                intake=subject.get("intake"),
                max_results=20,
                mode=prior_run.mode or "strict",
                retry_of=prior_run,
            )
        self.persist_review_results(run.intake_id, matches, run)
        return {
            "type": "ir.actions.act_window",
            "name": _("Match Run"),
            "res_model": "plasticos.match.run",
            "res_id": run.id,
            "view_mode": "form",
            "target": "current",
        }

    @api.model
    def _build_intake_match_line_vals(self, intake, matches):
        """Build vals for plasticos.intake.match rows (no ORM writes)."""
        vals = []
        for m in matches:
            buyer_id = m.get("buyer_id")
            if not buyer_id:
                continue
            vals.append(
                {
                    "intake_id": intake.id,
                    "buyer_id": buyer_id,
                    "match_score": (m.get("total_score") or 0.0) * 100,
                    "match_reason": ", ".join(m.get("gates_failed") or []) or "All gates passed",
                    "typical_price": m.get("typical_price") or 0.0,
                }
            )
        return vals

    @api.model
    def _create_intake_match_lines(self, vals_list):
        """Batch-create UI match lines (kept loop-free for audit scanner)."""
        if not vals_list:
            return self.env["plasticos.intake.match"]
        return self.env["plasticos.intake.match"].create(vals_list)

    @api.model
    def persist_review_results(self, intake, matches, run):
        """Persist canonical match.result rows linked to the run, plus intake UI lines when there is an intake.

        ``intake`` may be empty for a lot run matched from a native opportunity;
        the canonical results are then the only projection.
        """
        run.ensure_one()
        intake = intake if intake else None
        # Canonical review rows are durable receipt projections. Persist them before
        # transient intake display lines so a UI-only update cannot masquerade as a result.
        try:
            self.env["plasticos.match.result.writer"].persist_match_lines(
                intake,
                matches,
                match_run=run,
            )
        except (AccessError, ValidationError) as exc:
            # Gate answered; Odoo could not persist. The receipt still happened,
            # so the durable failure record keeps it and only the state changes.
            snapshot = self._durable_run_vals(run)
            self._rollback_then_persist_failed_run_durable(
                run.id,
                {
                    **snapshot,
                    "state": "failed",
                    "failure_class": _PERMANENT,
                    "error_message": str(exc),
                },
            )
            raise
        if intake is not None:
            intake.match_line_ids.unlink()
            self._create_intake_match_lines(self._build_intake_match_line_vals(intake, matches))
        return run.operation_id
