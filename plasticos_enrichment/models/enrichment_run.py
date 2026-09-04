import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

PROVENANCE_MODEL = "plasticos.enrichment.provenance"
SUBTYPE_NOTE = "mail.mt_note"


class EnrichmentRun(models.Model):
    _name = "plasticos.enrichment.run"
    _inherit = ["mail.thread"]
    _description = "Buyer Enrichment Run"
    _order = "id desc"

    name = fields.Char(
        required=True,
        readonly=True,
        copy=False,
        default=lambda self: self.env["ir.sequence"].next_by_code(
            "plasticos.enrichment.run",
        ),
    )
    partner_id = fields.Many2one(
        "res.partner",
        required=True,
        index=True,
        tracking=True,
        ondelete="restrict",
    )
    source_ids = fields.Many2many("plasticos.enrichment.source")
    extraction_ids = fields.One2many(
        "plasticos.enrichment.extraction",
        "run_id",
    )
    provenance_ids = fields.One2many(
        PROVENANCE_MODEL,
        "run_id",
    )

    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("crawling", "Crawling"),
            ("extracting", "Extracting"),
            ("validated", "Validated"),
            ("review", "Needs Review"),
            ("injected", "Injected"),
            ("retryable", "Retryable"),
            ("degraded", "Degraded"),
            ("failed", "Failed"),
        ],
        default="draft",
        tracking=True,
        readonly=True,
    )

    confidence_score = fields.Float(
        compute="_compute_confidence",
        store=True,
        digits=(3, 2),
    )
    validation_issues = fields.Json(readonly=True)
    injected_at = fields.Datetime(readonly=True)

    profiles_created = fields.Integer(readonly=True, default=0)
    profiles_updated = fields.Integer(readonly=True, default=0)
    fields_written = fields.Integer(readonly=True, default=0)

    engine_used = fields.Selection(
        [("local", "Local"), ("gate", "Gate")],
        readonly=True,
        help="Which engine produced this run: local pipeline or Gate converge.",
    )
    gate_proposal = fields.Json(
        readonly=True,
        help="Gate converge proposal (final_fields, proposed_partner_fields) retained for audit.",
    )
    gate_packet_id = fields.Char(readonly=True, help="Gate response TransportPacket id for audit.")
    gate_correlation_id = fields.Char(readonly=True, help="Gate correlation id for traceability.")
    failure_class = fields.Char(
        readonly=True,
        help="Classified Gate failure (retryable/permanent/unknown) for degraded mode.",
    )
    availability_status = fields.Char(
        readonly=True,
        help="Structured Gate availability status at execute time.",
    )
    gate_attempt = fields.Integer(
        readonly=True,
        default=1,
        help=(
            "Gate converge attempt counter. Each operator retry increments it, so a retry is a "
            "new logical operation identity (ADR-006) and can never be served Gate's cached "
            "response to the failed attempt."
        ),
    )

    @api.depends(
        "extraction_ids.confidence",
        "extraction_ids.is_injectable",
    )
    def _compute_confidence(self):
        for run in self:
            confs = run.extraction_ids.filtered(
                "is_injectable",
            ).mapped("confidence")
            run.confidence_score = min(confs) if confs else 0.0

    # ── CRUD Guards ───────────────────────────────────────────

    def write(self, vals):
        """Guard against modifying injected/failed runs (except state changes)."""
        if "state" not in vals:
            for rec in self:
                if rec.state in ("injected", "failed"):
                    raise UserError(
                        f"Cannot modify enrichment run '{rec.name}' in state '{rec.state}'. Create a new run instead."
                    )
        return super().write(vals)

    def unlink(self):
        """Prevent deletion of injected runs (audit trail)."""
        for rec in self:
            if rec.state == "injected":
                raise UserError(
                    f"Cannot delete enrichment run '{rec.name}' after injection. "
                    "Injected runs must be preserved for audit."
                )
        return super().unlink()

    # ── Pipeline Actions ───────────────────────────────────────

    @api.model
    def _should_try_gate_converge(self):
        """Return True when Gate enrichment (converge) is enabled and SDK is available."""
        from odoo.addons.plasticos_gate.services.gate_config import gate_enrichment_enabled

        return gate_enrichment_enabled(self.env)

    def _run_gate_converge(self):
        """Route enrichment through Gate converge (EIE worker).

        Review-only by default (``plasticos.gate.auto_writeback=0``): store the
        proposal for human approval (state='review') without partner writes.
        When auto_writeback is explicitly enabled, apply allowlisted fields
        (merge-not-overwrite, with provenance) and set state to 'injected'.
        Returns True when Gate produced a usable result; False on non-ok status
        or empty allowlist (caller fails closed / no local fallback on M4).
        """
        self.ensure_one()
        from odoo.addons.plasticos_gate.services.gate_builders import build_converge_request
        from odoo.addons.plasticos_gate.services.gate_client import send_converge_action
        from odoo.addons.plasticos_gate.services.gate_config import gate_auto_writeback_enabled
        from odoo.addons.plasticos_gate.services.gate_mappers import (
            extract_audit_metadata,
            map_converge_response,
            partner_writeback_from_converge,
        )

        request = build_converge_request(self.env, self)
        payload = request.to_dict()
        result = send_converge_action(
            self.env,
            payload=payload,
            correlation_id=request.odoo.get("correlation_id") if request.odoo else None,
            # ADR-006 — ONE logical operation identity. It is generated once by
            # build_converge_request and already rides in the EnrichRequest
            # payload; the same value is handed to the transport header here.
            # Domain persistence idempotency (EIE) and transport replay
            # prevention (Gate_SDK) stay separate mechanisms that now agree on
            # which operation they are talking about.
            idempotency_key=request.idempotency_key,
        )
        resp = map_converge_response(result["payload"])
        audit = extract_audit_metadata(result["packet"])

        # EIE contract: only status == "ok" is a usable result. Anything else is a
        # worker/hub failure signal -> fall back to local (never mark injected on junk).
        if str(resp.status or "").strip().lower() != "ok":
            _logger.warning(
                "Gate converge returned non-ok status %r (packet %s); falling back to local.",
                resp.status,
                audit.get("gate_packet_id"),
            )
            return False

        proposed = partner_writeback_from_converge(resp)
        # EIE provenance travels with the proposal so the audit trail on the run
        # records what EIE actually reported (confidence, tokens, KB hash,
        # inference version), not a value Odoo made up at writeback time.
        eie_provenance = {
            "confidence": resp.confidence,
            "tokens_used": resp.tokens_used,
            "kb_content_hash": resp.kb_content_hash,
            "inference_version": resp.inference_version,
            "pass_count": resp.pass_count,
            "variation_count": resp.variation_count,
            "processing_time_ms": resp.processing_time_ms,
            "quality_tier": resp.quality_tier,
            "uncertainty_score": resp.uncertainty_score,
            "kb_fragment_ids": list(resp.kb_fragment_ids or []),
        }

        base_vals = {
            "engine_used": "gate",
            "gate_proposal": {
                "final_fields": resp.final_fields,
                "proposed_partner_fields": proposed,
                "eie_provenance": eie_provenance,
            },
            "gate_packet_id": audit.get("gate_packet_id"),
            "gate_correlation_id": audit.get("gate_correlation_id"),
        }

        if not proposed:
            # Nothing allowlisted came back. In review mode this used to
            # produce a `review` run with nothing to approve; the caller now
            # records it as degraded in both modes.
            _logger.info(
                "Gate converge returned no writable allowlisted fields (packet %s).",
                audit.get("gate_packet_id"),
            )
            return False

        if not gate_auto_writeback_enabled(self.env):
            self.write(
                {
                    **base_vals,
                    "state": "review",
                    "validation_issues": [
                        "Gate converge proposal awaiting human review (auto-writeback disabled).",
                    ],
                }
            )
            self.message_post(
                body=(
                    f"Gate converge proposed {len(proposed)} partner field(s) for review "
                    f"(packet {audit.get('gate_packet_id')})."
                ),
                subtype_xmlid=SUBTYPE_NOTE,
            )
            return True

        written = self._apply_converge_writeback(proposed, audit, confidence=resp.confidence)
        self.write(
            {
                **base_vals,
                "state": "injected",
                "injected_at": fields.Datetime.now(),
                "fields_written": written,
                "validation_issues": False,
            }
        )
        self.message_post(
            body=(f"Gate converge applied {written} partner field(s) live (packet {audit.get('gate_packet_id')})."),
            subtype_xmlid=SUBTYPE_NOTE,
        )
        return True

    def _apply_converge_writeback(self, proposed, audit, confidence=None):
        """Backfill allowlisted partner fields (merge-not-overwrite) with provenance.

        ``confidence`` is EIE's reported aggregate confidence for the result the
        proposal came from. When the caller has none (an approval of a stored
        proposal), it is read back from ``gate_proposal.eie_provenance``; only
        if neither exists does the provenance row fall back to 1.0.
        """
        partner = self.partner_id
        to_write = {}
        for field_name, value in (proposed or {}).items():
            if field_name not in partner._fields:
                continue
            if partner[field_name]:  # merge-not-overwrite: never clobber existing values
                continue
            to_write[field_name] = value
        if not to_write:
            return 0
        partner.write(to_write)
        packet_id = audit.get("gate_packet_id") or ""
        if confidence is None:
            proposal = self.gate_proposal if isinstance(self.gate_proposal, dict) else {}
            confidence = (proposal.get("eie_provenance") or {}).get("confidence")
        try:
            row_confidence = float(confidence) if confidence is not None else 1.0
        except (TypeError, ValueError):
            row_confidence = 1.0
        for field_name, value in to_write.items():
            self.env[PROVENANCE_MODEL].create(
                {
                    "run_id": self.id,
                    "partner_id": partner.id,
                    "target_model": "res.partner",
                    "target_field": field_name,
                    "value_written": str(value),
                    "previous_value": "",
                    "source_sentence": f"gate_converge:{packet_id}",
                    "confidence": row_confidence,
                    "inference_type": "explicit",
                    "status": "written",
                }
            )
        return len(to_write)

    def _rollback_then_persist_operator_state(self, run_id, vals):
        """Roll the failed transaction back, then persist run state durably.

        ``UserError`` in an HTTP/RPC request rolls back the request transaction,
        so failure classification (degraded/failed/retryable) must be written on
        an independently committed cursor to survive it (I2).

        Ordering is the whole point (I3). ``action_execute`` writes to this run
        before calling Gate, so at the moment of failure transaction A still
        holds an uncommitted row lock on it. Flushing here — as this method used
        to — guarantees that lock, and the second cursor's ``UPDATE`` on the same
        row then waits on transaction A until the request times out. Rolling
        back first releases the row, so the durable write always proceeds.

        ``run_id`` is a primitive on purpose: recordset state captured before the
        rollback is not trustworthy afterwards.
        """
        self.env.cr.rollback()
        self._persist_operator_state_durable(run_id, vals)

    def _persist_operator_state_durable(self, run_id, vals):
        """Write operator-visible run state on a clean owned cursor and commit.

        Only safe once the transaction that failed has been rolled back.
        """
        with self.pool.cursor() as cr:
            env = api.Environment(cr, self.env.uid, dict(self.env.context))
            run = env[self._name].browse(run_id).exists()
            if run:
                run.write(vals)
            cr.commit()

    def action_execute(self):
        """Gate-only converge (M4). Never falls back to local crawl/extract/inference.

        On Gate unavailable/failure: classify, audit on this run, raise UserError.
        """
        self.ensure_one()
        from odoo.addons.plasticos_gate.services.gate_client import classify_transport_failure
        from odoo.addons.plasticos_gate.services.gate_config import (
            GateCapability,
            GateIntegrationError,
            classify_gate_availability,
            gate_enrichment_enabled,
        )

        run_id = self.id
        availability = classify_gate_availability(self.env, capability=GateCapability.ENRICHMENT)
        self.write(
            {
                "engine_used": "gate",
                "availability_status": availability.status,
                "failure_class": False,
            }
        )

        if not gate_enrichment_enabled(self.env):
            reasons = "; ".join(availability.reasons) or "Gate enrichment unavailable"
            self._rollback_then_persist_operator_state(
                run_id,
                {
                    "engine_used": "gate",
                    "state": "failed",
                    "failure_class": "permanent",
                    "validation_issues": [reasons],
                    "availability_status": availability.status,
                },
            )
            raise UserError(
                _("Gate enrichment is not enabled (%(status)s): %(reasons)s")
                % {"status": availability.status, "reasons": reasons}
            )

        try:
            if self._run_gate_converge():
                return
            # Gate returned non-applicable result (non-ok / empty allowlist) — fail closed
            self._rollback_then_persist_operator_state(
                run_id,
                {
                    "engine_used": "gate",
                    "state": "degraded",
                    "failure_class": "unknown",
                    "validation_issues": [
                        "Gate converge produced no injectable allowlisted fields.",
                    ],
                    "availability_status": availability.status,
                },
            )
            raise UserError(_("Gate enrichment degraded: no injectable fields from converge response."))
        except UserError:
            raise
        except GateIntegrationError as exc:
            failure = getattr(exc, "failure_class", None) or classify_transport_failure(exc).value
            state = "retryable" if failure == "retryable" else ("failed" if failure == "permanent" else "degraded")
            message = str(exc)
            self._rollback_then_persist_operator_state(
                run_id,
                {
                    "engine_used": "gate",
                    "state": state,
                    "failure_class": failure,
                    "validation_issues": [message],
                    "availability_status": availability.status,
                },
            )
            raise UserError(_("Gate enrichment failed (%s): %s") % (failure, message)) from exc
        except Exception as exc:  # noqa: BLE001 — boundary: classify then fail closed
            failure = classify_transport_failure(exc).value
            state = "retryable" if failure == "retryable" else ("failed" if failure == "permanent" else "degraded")
            message = str(exc)
            self._rollback_then_persist_operator_state(
                run_id,
                {
                    "engine_used": "gate",
                    "state": state,
                    "failure_class": failure,
                    "validation_issues": [message],
                    "availability_status": availability.status,
                },
            )
            _logger.exception("Gate enrichment unexpected error for run %s", run_id)
            raise UserError(_("Gate enrichment failed (%s): %s") % (failure, message)) from exc

    def action_retry_enrichment(self):
        """Operator retry — Gate-only; never local crawl/inference."""
        self.ensure_one()
        if self.state not in ("retryable", "failed", "degraded"):
            raise UserError(_("Run %s is not in a retryable/failed/degraded state.") % self.name)
        # Reset to draft for a clean Gate attempt while preserving audit via chatter.
        # The attempt counter advances so the retry carries a NEW logical
        # operation identity: Gate caches responses per identity — including an
        # EIE domain failure — and a retry under the failed attempt's identity
        # would be answered from that cache without ever reaching EIE (ADR-006).
        self.write(
            {
                "state": "draft",
                "validation_issues": False,
                "failure_class": False,
                "gate_attempt": (self.gate_attempt or 1) + 1,
            }
        )
        return self.action_execute()

    def action_inject(self):
        """Write validated enrichment into plasticos.material.profile.

        Merge-not-overwrite: existing field values are never
        clobbered. Only empty/falsy fields are populated.

        Gate review-only runs store ``gate_proposal.proposed_partner_fields``.
        Approving those applies the allowlisted partner writeback before any
        material-profile inject from ``extraction_ids``.
        """
        self.ensure_one()
        if self.state not in ("validated", "review"):
            raise UserError(
                "Run must be validated or manually approved from review.",
            )

        gate_written = 0
        proposal = self.gate_proposal if isinstance(self.gate_proposal, dict) else {}
        proposed = proposal.get("proposed_partner_fields") or {}
        if proposed:
            audit = {
                "gate_packet_id": self.gate_packet_id,
                "gate_correlation_id": self.gate_correlation_id,
            }
            gate_written = self._apply_converge_writeback(proposed, audit)
            if not self.extraction_ids.filtered("is_injectable"):
                self.write(
                    {
                        "state": "injected",
                        "injected_at": fields.Datetime.now(),
                        "fields_written": gate_written,
                        "validation_issues": False,
                    }
                )
                self.message_post(
                    body=(
                        f"Gate converge proposal approved: {gate_written} partner "
                        f"field(s) applied (packet {self.gate_packet_id})."
                    ),
                    subtype_xmlid=SUBTYPE_NOTE,
                )
                return

        svc = self.env["plasticos.enrichment.service"]
        partner = self.partner_id
        MatProf = self.env["plasticos.material.profile"]

        created = 0
        updated = 0
        written = 0

        for ext in self.extraction_ids.filtered("is_injectable"):
            for raw_mat in ext.material_json or []:
                profile_vals, prov_items, unmapped = svc.normalize_material(raw_mat)

                polymer = profile_vals.pop("polymer", None)
                if not polymer:
                    continue

                polymer_id = svc._resolve_polymer_id(polymer)
                if not polymer_id:
                    _logger.warning(
                        "No plasticos.polymer for code %s — skip",
                        polymer,
                    )
                    continue

                form = profile_vals.pop("form", False)
                form_id = svc._resolve_form_id(form) if form else None
                if not form_id:
                    form_id = svc._resolve_form_id("other")
                if not form_id:
                    _logger.warning(
                        "No plasticos.material.form for form %s — skip",
                        form,
                    )
                    continue

                source_type = profile_vals.pop("source_type", None)
                source_type_id = (
                    svc._resolve_source_type_id(source_type) if source_type else self.env["plasticos.source.type"]
                )

                # Search by partner + polymer_id + form_id (canonical unique)
                domain = [
                    ("partner_id", "=", partner.id),
                    ("polymer_id", "=", polymer_id.id),
                    ("form_id", "=", form_id.id),
                ]
                existing = MatProf.search(domain, limit=1)

                if existing:
                    merge_vals = {}
                    for field, value in profile_vals.items():
                        if field in ("polymer", "form", "source_type"):
                            continue
                        current = existing[field]
                        if not current:
                            merge_vals[field] = value
                            self._record_provenance(
                                partner,
                                field,
                                str(value),
                                str(current),
                                "written",
                                prov_items,
                            )
                            written += 1
                        elif current != value:
                            self._record_provenance(
                                partner,
                                field,
                                str(value),
                                str(current),
                                "skipped_immutable",
                                prov_items,
                            )
                    if source_type_id:
                        merge_vals["source_type_id"] = source_type_id.id
                    if merge_vals:
                        existing.write(merge_vals)
                        existing.message_post(
                            body=(f"Enrichment {self.name} merged fields: {', '.join(merge_vals.keys())}"),
                            subtype_xmlid=SUBTYPE_NOTE,
                        )
                        updated += 1
                else:
                    create_vals = {
                        "partner_id": partner.id,
                        "polymer_id": polymer_id.id,
                        "form_id": form_id.id,
                    }
                    if source_type_id:
                        create_vals["source_type_id"] = source_type_id.id
                    create_vals.update(profile_vals)
                    MatProf.create(create_vals)
                    for field, value in profile_vals.items():
                        self._record_provenance(
                            partner,
                            field,
                            str(value),
                            "",
                            "written",
                            prov_items,
                        )
                        written += 1
                    self._record_provenance(
                        partner,
                        "polymer_id",
                        str(polymer_id.id),
                        "",
                        "written",
                        prov_items,
                    )
                    self._record_provenance(
                        partner,
                        "form_id",
                        str(form_id.id),
                        "",
                        "written",
                        prov_items,
                    )
                    written += 2
                    created += 1

                for ufield, uval in unmapped:
                    self._record_provenance(
                        partner,
                        ufield,
                        str(uval),
                        "",
                        "unmapped",
                        prov_items,
                    )

        self.write(
            {
                "state": "injected",
                "injected_at": fields.Datetime.now(),
                "profiles_created": created,
                "profiles_updated": updated,
                "fields_written": written,
            }
        )
        self.message_post(
            body=(f"Enrichment injected: {created} profiles created, {updated} updated, {written} fields written."),
        )

    def _record_provenance(
        self,
        partner,
        field,
        new_val,
        old_val,
        status,
        prov_items,
    ):
        """Create a provenance record for a single field write."""
        prov_match = next(
            (p for p in prov_items if p["target_field"] == field),
            {},
        )
        self.env[PROVENANCE_MODEL].create(
            {
                "run_id": self.id,
                "partner_id": partner.id,
                "target_model": "plasticos.material.profile",
                "target_field": field,
                "value_written": new_val,
                "previous_value": old_val,
                "source_sentence": prov_match.get(
                    "source_sentence",
                    "",
                ),
                "confidence": prov_match.get("confidence", 0),
                "inference_type": prov_match.get(
                    "inference_type",
                    "implicit",
                ),
                "status": status,
            }
        )

    # ── Inference Step ──────────────────────────────────────────

    def action_run_inference(self):
        """Retired in M4 — local inference execution removed."""
        raise UserError(_("Local inference execution was removed (mothball M4). Enrichment is Gate-only."))

    def action_cron_enrich_pending(self, run_inference: bool = True):
        """M4: cron disabled; no local enrichment batch execution."""
        _logger.info(
            "action_cron_enrich_pending skipped (M4 Gate-only; local cron retired). run_inference=%s",
            run_inference,
        )
        return True

    def action_cron_inference_only(self):
        """Retired in M4 — standalone local inference cron is a no-op."""
        _logger.info("action_cron_inference_only skipped (M4 local inference retired).")
        return True
