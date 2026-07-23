import logging

from odoo import api, fields, models
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
        help="Gate converge proposal (final_fields, writeback, proposed_partner_fields) retained for audit.",
    )
    gate_packet_id = fields.Char(readonly=True, help="Gate response TransportPacket id for audit.")
    gate_correlation_id = fields.Char(readonly=True, help="Gate correlation id for traceability.")

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

        Live path (default): apply the converge proposal to the partner immediately
        (merge-not-overwrite of allowlisted fields, with provenance) and set state to
        'injected'. When plasticos.gate.auto_writeback=0, store the proposal for human
        review (state='review') without writing. Returns True when Gate produced a
        usable result; returns False (non-ok status or no writable fields) so the
        caller falls back to the local pipeline.
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
                "writeback": resp.writeback,
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
        self.message_post(
            body=(f"Gate converge applied {written} partner field(s) live (packet {audit.get('gate_packet_id')})."),
            subtype_xmlid=SUBTYPE_NOTE,
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

    def action_execute(self):
        """Full pipeline: try Gate converge -> fall back to local crawl/extract/evaluate.

        State transitions (direct writes are intentional - pipeline method):
        - draft -> crawling -> extracting -> validated/review/failed
        """
        self.ensure_one()

        if self._should_try_gate_converge():
            try:
                if self._run_gate_converge():
                    return
            except Exception as exc:
                _logger.warning(
                    "Gate converge failed; falling back to local enrichment: %s",
                    exc,
                    exc_info=True,
                )

        svc = self.env["plasticos.enrichment.service"]

        if not self.source_ids:
            raise UserError("Add at least one source URL.")

        # 1. Crawl
        self.write({"state": "crawling", "engine_used": "local"})
        for source in self.source_ids:
            svc.crawl_source(source)

        # 2. Extract
        self.write({"state": "extracting"})
        succeeded = self.source_ids.filtered(
            lambda s: s.crawl_status == "success",
        )
        if not succeeded:
            self.write(
                {
                    "state": "failed",
                    "validation_issues": [
                        "No sources crawled successfully.",
                    ],
                }
            )
            return

        # Collect extraction results for batch create
        extraction_vals_list = []
        extraction_errors = []
        for source in succeeded:
            try:
                parsed = svc.extract_from_source(source)
                extraction_vals_list.append(
                    {
                        "run_id": self.id,
                        "source_id": source.id,
                        "material_json": parsed["materials"],
                        "metadata_json": {
                            "source_url": parsed["source_url"],
                        },
                        "confidence": parsed["overall_confidence"],
                        "governance_passed": parsed["governance_passed"],
                        "governance_flags": parsed["governance_flags"],
                        "extracted_at": fields.Datetime.now(),
                    }
                )
            except Exception as e:
                extraction_errors.append(f"{source.url}: {e}")
                _logger.error(
                    "Extraction failed for source %s: %s",
                    source.url,
                    e,
                )

        # Batch create all extractions
        if extraction_vals_list:
            self.env["plasticos.enrichment.extraction"].create(extraction_vals_list)

        # 3. Evaluate
        if not self.extraction_ids:
            issues = ["All extractions failed."]
            if extraction_errors:
                issues.extend(extraction_errors)
            self.write(
                {
                    "state": "failed",
                    "validation_issues": issues,
                }
            )
            return

        all_flags = []
        for ext in self.extraction_ids:
            all_flags.extend(ext.governance_flags or [])

        injectable = all(ext.is_injectable for ext in self.extraction_ids)
        if injectable and not all_flags:
            if extraction_errors:
                self.write(
                    {
                        "state": "review",
                        "validation_issues": extraction_errors,
                    }
                )
            else:
                self.write({"state": "validated"})
        else:
            issues = all_flags or ["Low confidence or governance failure."]
            if extraction_errors:
                issues = list(issues) + extraction_errors
            self.write(
                {
                    "state": "review",
                    "validation_issues": issues,
                }
            )

    def action_inject(self):
        """Write validated enrichment into plasticos.material.profile.

        Merge-not-overwrite: existing field values are never
        clobbered. Only empty/falsy fields are populated.
        """
        self.ensure_one()
        if self.state not in ("validated", "review"):
            raise UserError(
                "Run must be validated or manually approved from review.",
            )

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
        """
        Run inference engine on all material profiles for this run's partner.
        Called after injection to fill gaps with KB-based inference.
        """
        self.ensure_one()
        if self.state != "injected":
            raise UserError(
                "Inference can only run after enrichment is injected.",
            )

        svc = self.env["plasticos.enrichment.service"]
        MatProf = self.env["plasticos.material.profile"]

        # Get all profiles for this partner
        profiles = MatProf.search(
            [
                ("partner_id", "=", self.partner_id.id),
            ],
            order="id ASC",
        )

        inference_count = 0
        for profile in profiles:
            try:
                updated = svc.run_inference_on_profile(profile)
                if updated:
                    inference_count += 1
                    # Record provenance for inferred fields
                    for field_name, value in updated.items():
                        self._record_provenance(
                            self.partner_id,
                            field_name,
                            str(value),
                            "",
                            "inferred",
                            [],
                        )
            except Exception as e:
                _logger.warning(
                    "Inference failed for profile %s: %s",
                    profile.id,
                    e,
                )

        if inference_count:
            self.message_post(
                body=(f"Inference engine augmented {inference_count} material profile(s) for {self.partner_id.name}."),
                subtype_xmlid=SUBTYPE_NOTE,
            )

        return inference_count

    # ── Cron ───────────────────────────────────────────────────

    @api.model
    def action_cron_enrich_pending(self, run_inference: bool = True):
        """Called by ir.cron. Process partners with enrichment sources that are stale."""
        self.env.cr.execute("SELECT pg_try_advisory_lock(hashtext(%s))", ["plasticos_enrichment.cron_enrichment_daily"])
        if not self.env.cr.fetchone()[0]:
            _logger.info("Skipping enrichment cron: lock is already held.")
            return

        stale_cutoff = fields.Datetime.subtract(fields.Datetime.now(), days=30)
        try:
            try:
                sources = self.env["plasticos.enrichment.source"].search(
                    [
                        ("crawl_status", "in", ("pending", "success")),
                        "|",
                        ("last_crawled_at", "=", False),
                        ("last_crawled_at", "<", stale_cutoff),
                    ],
                    order="last_crawled_at ASC, id ASC",
                    limit=50,
                )
            except Exception as search_exc:
                _logger.error("Enrichment cron source search failed: %s", search_exc)
                return

            for pid in sorted(set(sources.mapped("partner_id").ids)):
                partner_sources = sources.filtered(lambda src, partner_id=pid: src.partner_id.id == partner_id)
                run = self.create({"partner_id": pid, "source_ids": [(6, 0, partner_sources.ids)]})
                try:
                    run.action_execute()
                    if run.state == "validated":
                        run.action_inject()
                        if run_inference and run.state == "injected":
                            try:
                                run.action_run_inference()
                            except Exception as ie:
                                _logger.warning("Inference step failed for partner %s: %s", pid, ie)
                except Exception as exc:
                    run.write({"state": "failed", "validation_issues": [str(exc)]})
                    _logger.error("Enrichment cron failed for partner %s: %s", pid, exc)
        except Exception as exc:
            _logger.error("Enrichment cron crashed unexpectedly but was contained: %s", exc)
            return
        finally:
            self.env.cr.execute(
                "SELECT pg_advisory_unlock(hashtext(%s))", ["plasticos_enrichment.cron_enrichment_daily"]
            )

    @api.model
    def action_cron_inference_only(self):
        """Standalone cron to inference stale profiles."""
        self.env.cr.execute(
            "SELECT pg_try_advisory_lock(hashtext(%s))", ["plasticos_enrichment.cron_inference_standalone"]
        )
        locked = self.env.cr.fetchone()[0]
        if not locked:
            _logger.info("Skipping inference-only cron: lock is already held.")
            return 0

        svc = self.env["plasticos.enrichment.service"]
        mat_prof = self.env["plasticos.material.profile"]
        try:
            try:
                profiles = mat_prof.search(
                    [("quality_tier", "=", False), ("polymer_id", "!=", False)],
                    order="write_date ASC, id ASC",
                    limit=100,
                )
            except Exception as search_exc:
                _logger.error("Inference cron profile search failed: %s", search_exc)
                return 0
            count = 0
            for profile in profiles:
                try:
                    updated = svc.run_inference_on_profile(profile)
                    if updated:
                        count += 1
                except Exception as exc:
                    _logger.warning("Inference cron failed for profile %s: %s", profile.id, exc)
            _logger.info("Inference cron completed: %d profiles augmented", count)
            return count
        except Exception as exc:
            _logger.error("Inference cron crashed unexpectedly but was contained: %s", exc)
            return 0
        finally:
            self.env.cr.execute(
                "SELECT pg_advisory_unlock(hashtext(%s))", ["plasticos_enrichment.cron_inference_standalone"]
            )
