import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

PROVENANCE_MODEL = "plasticos.enrichment.provenance"
FACILITY_PROFILE_MODEL = "plasticos.facility.profile"
GATE_OUTBOX_MODEL = "plasticos.gate.outbox"
SUBTYPE_NOTE = "mail.mt_note"

SCHEDULER_LOCK = "enrichment.run.scheduler"

# Machine outcomes returned by _execute_gate_machine(). These describe what the
# machine did; they are not UI concerns and never carry a UserError.
OUTCOME_OK = "ok"
OUTCOME_REVIEW = "review"
OUTCOME_RETRYABLE = "retryable"
OUTCOME_PERMANENT = "permanent"
OUTCOME_DEGRADED = "degraded"

#: States the autonomous scheduler is allowed to claim.
SCHEDULABLE_STATES = ("draft", "retryable")


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

    # ── Scheduling + idempotency metadata ─────────────────────────
    # Operational only: this is not a second state machine. The durable states
    # above (draft/retryable/injected/degraded/failed) still own the lifecycle.
    input_fingerprint = fields.Char(
        readonly=True,
        index=True,
        help=(
            "SHA-256 over the semantic converge inputs only (partner snapshot, source URLs, "
            "object type, objective, max variations, pipeline contract version). Excludes run id, "
            "packet id, attempt number, and timestamps so a retry reuses the same computation."
        ),
    )
    idempotency_key = fields.Char(
        readonly=True,
        index=True,
        help="Durable converge idempotency key sent to EIE: odoo:<db>:<entity_ref>:converge:<version>:<fingerprint>.",
    )
    attempt_count = fields.Integer(default=0, readonly=True, help="Gate converge attempts already made.")
    next_attempt_at = fields.Datetime(
        index=True,
        readonly=True,
        help="Earliest time the scheduler may claim this run again. Empty means immediately.",
    )
    last_attempt_at = fields.Datetime(readonly=True)
    error_category = fields.Char(
        readonly=True,
        help="Machine-readable failure category from the last attempt (transport/config/contract).",
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
        # Record the semantic identity of this attempt before the call, so a crash
        # mid-flight still leaves the operator (and the next retry) the key EIE
        # was asked to deduplicate on.
        self._record_request_identity(request)
        result = send_converge_action(
            self.env,
            payload=request.to_dict(),
            correlation_id=request.odoo.get("correlation_id") if request.odoo else None,
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

        base_vals = {
            "engine_used": "gate",
            "gate_proposal": {
                "final_fields": resp.final_fields,
                "proposed_partner_fields": proposed,
            },
            "gate_packet_id": audit.get("gate_packet_id"),
            "gate_correlation_id": audit.get("gate_correlation_id"),
        }

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

        if not proposed:
            _logger.info(
                "Gate converge returned no writable allowlisted fields (packet %s); falling back to local.",
                audit.get("gate_packet_id"),
            )
            return False

        written = self._apply_converge_writeback(proposed, audit)
        self.write(
            {
                **base_vals,
                "state": "injected",
                "injected_at": fields.Datetime.now(),
                "fields_written": written,
                "validation_issues": False,
            }
        )
        # Same transaction as the partner write above: if Odoo commits, the
        # projection is queued; if Odoo rolls back, it never existed. No
        # distributed transaction, no dual-write race.
        if written:
            self._enqueue_graph_projection()
        self.message_post(
            body=(f"Gate converge applied {written} partner field(s) live (packet {audit.get('gate_packet_id')})."),
            subtype_xmlid=SUBTYPE_NOTE,
        )
        return True

    def _record_request_identity(self, request):
        """Persist the fingerprint and idempotency key for this converge attempt."""
        from odoo.addons.plasticos_gate.services.gate_builders import CONVERGE_PIPELINE_CONTRACT_VERSION

        self.ensure_one()
        key = request.idempotency_key or ""
        # The fingerprint is the final segment of the key; storing it separately
        # keeps "did the input change?" answerable without re-deriving the key.
        fingerprint = key.rsplit(":", 1)[-1] if key else False
        vals = {
            "idempotency_key": key or False,
            "input_fingerprint": fingerprint,
            "last_attempt_at": fields.Datetime.now(),
            "attempt_count": (self.attempt_count or 0) + 1,
        }
        _logger.debug(
            "Converge attempt %s for run %s (pipeline %s)",
            vals["attempt_count"],
            self.id,
            CONVERGE_PIPELINE_CONTRACT_VERSION,
        )
        self.write(vals)

    def _enqueue_graph_projection(self):
        """Queue the authoritative Graph projection for this partner's committed state.

        Runs only after Odoo has accepted and written the enrichment, so Graph
        receives Odoo truth rather than an unaccepted EIE proposal. A projection
        problem is logged and swallowed: Graph is a derived read model and must
        never roll back a valid Odoo write.
        """
        from odoo.addons.plasticos_gate.services.gate_config import (
            get_graph_sync_action,
            graph_projection_enabled,
        )
        from odoo.addons.plasticos_gate.services.gate_projection import (
            ProjectionContractError,
            build_facility_projection_row,
            build_facility_sync_payload,
            projection_semantic_key,
        )

        self.ensure_one()
        if not graph_projection_enabled(self.env):
            return False
        partner = self.partner_id
        profile = self.env[FACILITY_PROFILE_MODEL].search([("partner_id", "=", partner.id)], limit=1)
        try:
            row = build_facility_projection_row(partner, profile)
        except ProjectionContractError:
            _logger.exception("Facility projection rejected for partner %s; Odoo write stands.", partner.id)
            return False
        if row is None:
            # Not a facility. Never declare an arbitrary partner a Graph Facility.
            return False
        payload = build_facility_sync_payload([row])
        self.env[GATE_OUTBOX_MODEL].enqueue_projection(
            semantic_key=projection_semantic_key(payload),
            action=get_graph_sync_action(self.env),
            payload=payload,
        )
        return True

    def _apply_converge_writeback(self, proposed, audit):
        """Backfill allowlisted partner fields (merge-not-overwrite) with provenance."""
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
                    "confidence": 1.0,
                    "inference_type": "explicit",
                    "status": "written",
                }
            )
        return len(to_write)

    def _persist_operator_state(self, vals):
        """Write operator-visible run state in a separate cursor.

        ``UserError`` in an HTTP/RPC request rolls back the request transaction.
        Failure classification (degraded/failed/retryable) must survive that
        rollback so operators can see why Gate failed and use Retry.
        """
        self.ensure_one()
        self.flush_recordset()
        with self.pool.cursor() as cr:
            env = api.Environment(cr, self.env.uid, dict(self.env.context))
            env[self._name].browse(self.ids).write(vals)

    def _execute_gate_machine(self):
        """Execute one Gate converge attempt and return a structured result.

        This is the machine entry point: it never raises ``UserError`` and never
        requires human approval to reach a terminal disposition. The result is a
        dict with ``outcome`` (ok/review/retryable/permanent/degraded),
        ``state`` (the durable state written), and ``message``.

        A low-confidence or empty-allowlist result is a safe machine no-op
        (``degraded``), not a request for a human.
        """
        from odoo.addons.plasticos_gate.services.gate_client import classify_transport_failure
        from odoo.addons.plasticos_gate.services.gate_config import (
            GateCapability,
            GateIntegrationError,
            classify_gate_availability,
            gate_auto_writeback_enabled,
            gate_enrichment_enabled,
        )

        self.ensure_one()
        availability = classify_gate_availability(self.env, capability=GateCapability.ENRICHMENT)
        self.write(
            {
                "engine_used": "gate",
                "availability_status": availability.status,
                "failure_class": False,
                "error_category": False,
            }
        )

        if not gate_enrichment_enabled(self.env):
            reasons = "; ".join(availability.reasons) or "Gate enrichment unavailable"
            self._persist_operator_state(
                {
                    "engine_used": "gate",
                    "state": "failed",
                    "failure_class": "permanent",
                    "error_category": "config",
                    "validation_issues": [reasons],
                    "availability_status": availability.status,
                }
            )
            return {"outcome": OUTCOME_PERMANENT, "state": "failed", "message": reasons}

        try:
            if self._run_gate_converge():
                # _run_gate_converge writes 'review' or 'injected' itself.
                outcome = OUTCOME_OK if gate_auto_writeback_enabled(self.env) else OUTCOME_REVIEW
                return {"outcome": outcome, "state": self.state, "message": ""}
            message = "Gate converge produced no injectable allowlisted fields."
            self._persist_operator_state(
                {
                    "engine_used": "gate",
                    "state": "degraded",
                    "failure_class": "unknown",
                    "error_category": "contract",
                    "validation_issues": [message],
                }
            )
            return {"outcome": OUTCOME_DEGRADED, "state": "degraded", "message": message}
        except GateIntegrationError as exc:
            failure = getattr(exc, "failure_class", None) or classify_transport_failure(exc).value
            return self._record_machine_failure(failure, str(exc), category="transport")
        except Exception as exc:  # noqa: BLE001 — boundary: classify then fail closed
            _logger.exception("Gate enrichment unexpected error for run %s", self.id)
            failure = classify_transport_failure(exc).value
            return self._record_machine_failure(failure, str(exc), category="transport")

    def _record_machine_failure(self, failure_class, message, *, category):
        """Persist a classified failure and return the machine result for it."""
        self.ensure_one()
        state = (
            "retryable" if failure_class == "retryable" else ("failed" if failure_class == "permanent" else "degraded")
        )
        self._persist_operator_state(
            {
                "engine_used": "gate",
                "state": state,
                "failure_class": failure_class,
                "error_category": category,
                "validation_issues": [message],
            }
        )
        outcome = {
            "retryable": OUTCOME_RETRYABLE,
            "permanent": OUTCOME_PERMANENT,
        }.get(failure_class, OUTCOME_DEGRADED)
        return {"outcome": outcome, "state": state, "message": message}

    def action_execute(self):
        """Operator entry point: run the machine, then surface failures as UserError.

        UI concerns live here only. The machine method above stays raise-free so
        the scheduler can drive it record-by-record without one failure aborting
        a batch.
        """
        self.ensure_one()
        result = self._execute_gate_machine()
        if result["outcome"] in (OUTCOME_OK, OUTCOME_REVIEW):
            return True
        if result["outcome"] == OUTCOME_DEGRADED and result["state"] == "degraded":
            raise UserError(_("Gate enrichment degraded: %s") % result["message"])
        raise UserError(
            _("Gate enrichment failed (%(cls)s): %(msg)s")
            % {"cls": self.failure_class or result["outcome"], "msg": result["message"]}
        )

    def action_retry_enrichment(self):
        """Operator retry — Gate-only; never local crawl/inference."""
        self.ensure_one()
        if self.state not in ("retryable", "failed", "degraded"):
            raise UserError(_("Run %s is not in a retryable/failed/degraded state.") % self.name)
        # Reset to draft for a clean Gate attempt while preserving audit via chatter
        self.write({"state": "draft", "validation_issues": False, "failure_class": False})
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
                # Operator approval is the moment Odoo accepts the proposal, so
                # this is where the Graph projection becomes authoritative.
                if gate_written:
                    self._enqueue_graph_projection()
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

    # ── Autonomous scheduler ───────────────────────────────────

    def _schedule_next_attempt(self, outcome):
        """Set the retry clock after a machine attempt, or fail terminally.

        Only ``retryable`` earns another attempt. ``permanent`` and ``degraded``
        are already terminal states written by the machine; re-driving them would
        burn provider budget on a result that cannot improve by waiting.
        """
        from odoo.addons.plasticos_gate.services.gate_retry import attempts_exhausted, next_attempt_at

        self.ensure_one()
        if outcome != OUTCOME_RETRYABLE:
            return False
        attempts = self.attempt_count or 0
        if attempts_exhausted(attempts):
            self._persist_operator_state(
                {
                    "state": "failed",
                    "error_category": "transport",
                    "next_attempt_at": False,
                    "validation_issues": [f"Retry budget exhausted after {attempts} attempt(s)."],
                }
            )
            return False
        self._persist_operator_state(
            {
                "state": "retryable",
                "next_attempt_at": next_attempt_at(attempts, now=fields.Datetime.now()),
            }
        )
        return True

    @api.model
    def _claim_scheduler_batch(self, limit):
        """Claim due runs for this scheduler pass."""
        now = fields.Datetime.now()
        return self.search(
            [
                ("state", "in", list(SCHEDULABLE_STATES)),
                "|",
                ("next_attempt_at", "=", False),
                ("next_attempt_at", "<=", now),
            ],
            order="id",
            limit=limit,
        )

    @api.model
    def action_cron_gate_enrichment_scheduler(self, limit=50):
        """Drive due enrichment runs through Gate converge, one record at a time.

        Serialised by a PostgreSQL advisory lock so two cron workers cannot claim
        the same runs. One record's exception never terminates the batch, and one
        record's outcome is committed before the next is attempted.
        """
        from odoo.addons.plasticos_gate.services.gate_config import enrichment_scheduler_enabled
        from odoo.addons.plasticos_gate.services.gate_locks import worker_lock

        if not enrichment_scheduler_enabled(self.env):
            _logger.info(
                "Enrichment scheduler disabled (plasticos.gate.enrichment_scheduler_enabled=0); no runs claimed."
            )
            return 0

        processed = 0
        with worker_lock(self.env.cr, SCHEDULER_LOCK) as acquired:
            if not acquired:
                return 0
            batch = self._claim_scheduler_batch(limit)
            for run in batch:
                try:
                    result = run._execute_gate_machine()
                    run._schedule_next_attempt(result["outcome"])
                except Exception:  # noqa: BLE001 — one bad record must not kill the batch
                    _logger.exception("Enrichment scheduler failed on run %s; continuing batch.", run.id)
                    self.env.cr.rollback()
                    continue
                processed += 1
                self.env.cr.commit()
        _logger.info("Enrichment scheduler processed %s run(s).", processed)
        return processed

    def action_cron_enrich_pending(self, run_inference: bool = True):
        """Retired local batch entry point (M4).

        Kept so existing cron records and callers resolve. The autonomous path is
        ``action_cron_gate_enrichment_scheduler``.
        """
        _logger.info(
            "action_cron_enrich_pending skipped (M4 Gate-only; local cron retired). run_inference=%s",
            run_inference,
        )
        return True

    def action_cron_inference_only(self):
        """Retired in M4 — standalone local inference cron is a no-op."""
        _logger.info("action_cron_inference_only skipped (M4 local inference retired).")
        return True
