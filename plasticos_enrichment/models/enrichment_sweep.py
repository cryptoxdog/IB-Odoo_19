"""Scheduled EIE enrichment sweep — Odoo side (ADR-012 amendment 2026-11-15).

Odoo selects BUYER facility profiles and sends them through Gate as one sweep;
EIE owns the run and enforces the budget (min(daily_budget_usd, EIE ceiling)
per tenant per UTC day). Every result lands on the existing converge v2 review
path: one ``plasticos.enrichment.run`` in state ``review`` per usable result.
Nothing is written to a partner or profile before a human approves the run.

Operator approvals (2026-11-14/15, CTO session): the two crons (seeded
inactive and also gated on ``plasticos.gate.sweep_enabled``), the settings as
system parameters, and this small audit model.
"""

import logging

from psycopg2 import errors as pg_errors

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from ..services import sweep_policy as policy

_logger = logging.getLogger(__name__)

ENRICHMENT_RUN = "plasticos.enrichment.run"
FACILITY_PROFILE = "plasticos.facility.profile"
TARGET_FACILITY_PROFILE = "facility_profile"
OPEN_STATES = ("sent", "running")
# Each results cron pass pages one sweep at most this many times.
MAX_RESULT_PAGES = 200
# One sweep a day; more than this many open at once means something upstream is wrong.
MAX_OPEN_SWEEPS_PER_PASS = 30


def _rejection(entity_id, reason, stage):
    """One rejection/skip row kept on the sweep (stage: send, result or skipped)."""
    return dict(entity_id=entity_id, reason=reason, stage=stage)


class PlasticosEnrichmentSweep(models.Model):
    _name = "plasticos.enrichment.sweep"
    _description = "Scheduled Enrichment Sweep"
    _inherit = ["mail.thread"]
    _order = "id desc"

    name = fields.Char(required=True, readonly=True, copy=False)
    sweep_date = fields.Date(
        string="UTC Date", required=True, readonly=True, index=True, help="UTC day the sweep was sent for."
    )
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("sent", "Sent"),
            ("running", "Running"),
            ("done", "Done"),
            ("failed", "Failed"),
        ],
        default="draft",
        required=True,
        readonly=True,
        tracking=True,
        index=True,
    )
    sweep_id = fields.Char(string="EIE Sweep ID", readonly=True, index=True, copy=False)
    idempotency_key = fields.Char(readonly=True, copy=False)
    daily_budget_usd = fields.Float(string="Daily Budget (USD)", readonly=True, help="Budget Odoo asked for.")
    candidate_count = fields.Integer(readonly=True)
    accepted_count = fields.Integer(readonly=True)
    rejected_count = fields.Integer(readonly=True)
    ingested_count = fields.Integer(readonly=True, help="Results turned into enrichment runs.")
    skipped_count = fields.Integer(readonly=True, help="Candidates EIE skipped (budget or other reason).")
    eie_state = fields.Char(string="EIE Run State", readonly=True)
    candidate_requests = fields.Json(
        readonly=True, help="entity_id -> the converge v2 request each candidate stands for (parsed against)."
    )
    facility_map = fields.Json(readonly=True, help="entity_id -> facility profile id.")
    ingested = fields.Json(readonly=True, help="entity_id -> enrichment run id (idempotent ingestion).")
    rejections = fields.Json(readonly=True, help="Send-time rejections and result-time skips with reasons.")
    budget = fields.Json(readonly=True, help="Last budget object EIE reported (audit only).")
    error = fields.Text(readonly=True)
    gate_packet_id = fields.Char(readonly=True, help="Last Gate response TransportPacket id.")
    gate_correlation_id = fields.Char(readonly=True)

    _unique_idempotency_key = models.Constraint(
        "unique(idempotency_key)",
        "An enrichment sweep idempotency key is used once.",
    )

    # ── Settings ────────────────────────────────────────────────────────

    @api.model
    def _sweep_selection_keys(self):
        profile = self.env[FACILITY_PROFILE]

        def keys(name):
            return frozenset(str(k) for k, _label in profile._fields[name]._description_selection(self.env))

        return policy.SelectionKeys(
            process_types=keys("process_type"),
            application_classes=keys("application_class"),
            feedstock_types=keys("feedstock_type"),
        )

    @api.model
    def _sweep_settings(self):
        icp = self.env["ir.config_parameter"].sudo()  # sudo: system parameters are admin-only; read-only here
        return policy.read_settings(icp.get_param, self._sweep_selection_keys())

    # ── Selection ───────────────────────────────────────────────────────

    @api.model
    def _select_facilities(self, settings, now=None):
        """Eligible buyer facility profiles, cooldown and open work excluded, oldest enrichment first."""
        now = now or fields.Datetime.now()
        profiles = self.env[FACILITY_PROFILE].search(policy.facility_domain(settings), order="id")
        if not profiles:
            return profiles
        Run = self.env[ENRICHMENT_RUN]
        last = dict(
            Run._read_group(
                [("facility_profile_id", "in", profiles.ids), ("state", "!=", "draft")],
                groupby=["facility_profile_id"],
                aggregates=["create_date:max"],
            )
        )
        in_review = set(
            Run.search([("facility_profile_id", "in", profiles.ids), ("state", "=", "review")]).facility_profile_id.ids
        )
        pending = set()
        for sweep in self.search([("state", "in", OPEN_STATES)], limit=MAX_OPEN_SWEEPS_PER_PASS):
            pending.update(int(v) for k, v in (sweep.facility_map or {}).items() if k not in (sweep.ingested or {}))
        history = [
            policy.FacilityHistory(
                facility_id=p.id,
                last_enriched_at=last.get(p) or None,
                in_review=p.id in in_review,
                pending_in_sweep=p.id in pending,
            )
            for p in profiles
        ]
        ordered = policy.order_candidates(history, now=now, cooldown_days=settings.cooldown_days, cap=len(history))
        # gate-integration ADR-005: the entity is res.partner:<id>, so one partner is one candidate.
        chosen, partners = [], set()
        for profile in self.env[FACILITY_PROFILE].browse(ordered):
            if profile.partner_id.id in partners:
                continue
            partners.add(profile.partner_id.id)
            chosen.append(profile.id)
        return self.env[FACILITY_PROFILE].browse(chosen)

    @api.model
    def _v2_selection(self):
        """The converge contract; the sweep refuses to run unless it is v2 with a pin."""
        from odoo.addons.plasticos_gate.services.gate_config import resolve_converge_contract

        selection = resolve_converge_contract(self.env)
        if not selection.is_v2 or not selection.cartridge_id or not selection.cartridge_version:
            return None
        return selection

    # ── Send (cron 1) ───────────────────────────────────────────────────

    @api.model
    def _cron_send_sweep(self):
        """Nightly: build candidates and send one ``enrichment-sweep`` through Gate."""
        # sudo: system job run as the group-less service user (plasticos_base.user_system_cron);
        # it creates only this audit record and reads facility profiles. No business write.
        self = self.sudo()  # noqa: PLW0642  # cron-sudo-justification: group-less service user
        from odoo.addons.plasticos_gate.services.gate_config import (
            GateIntegrationError,
            gate_enrichment_enabled,
        )

        try:
            settings = self._sweep_settings()
        except policy.SweepSettingsError as exc:
            _logger.error("Enrichment sweep not sent: %s", exc)
            return False
        if not settings.enabled:
            _logger.info("Enrichment sweep disabled (plasticos.gate.sweep_enabled is off).")
            return False
        try:
            selection = self._v2_selection()
        except GateIntegrationError as exc:
            _logger.error("Enrichment sweep not sent: %s", exc)
            return False
        if selection is None:
            _logger.warning("Enrichment sweep not sent: converge contract is not v2 with a cartridge pin.")
            return False
        if not gate_enrichment_enabled(self.env):
            _logger.warning("Enrichment sweep not sent: Gate enrichment is unavailable.")
            return False
        today = fields.Datetime.now().date()
        if self.search_count([("sweep_date", "=", today), ("state", "!=", "failed")]):
            _logger.info("Enrichment sweep already sent for %s (UTC).", today)
            return False
        facilities = self._select_facilities(settings)
        # A same-day retry after a failed send reuses that record: the same candidates give the same
        # idempotency key, so Gate sees a replay of one operation, never a second sweep.
        sweep = self.search([("sweep_date", "=", today), ("state", "=", "failed")], order="id desc", limit=1)
        if sweep:
            sweep.write({"state": "draft", "error": False})
        else:
            sweep = self.create({"name": f"Enrichment sweep {today.isoformat()}", "sweep_date": today})
        sweep._send(facilities, settings, selection)
        return sweep

    def _send(self, facilities, settings, selection):
        self.ensure_one()
        from odoo.addons.plasticos_gate.services.gate_builders import (
            ConvergeV2NothingToRequest,
            build_facility_sweep_request_v2,
            build_sweep_candidate,
        )
        from odoo.addons.plasticos_gate.services.gate_client import send_sweep_action
        from odoo.addons.plasticos_gate.services.gate_config import GateIntegrationError, resolve_tenant
        from odoo.addons.plasticos_gate.services.gate_contracts import CartridgePin
        from odoo.addons.plasticos_gate.services.gate_mappers import extract_audit_metadata
        from odoo.addons.plasticos_gate.services.gate_sweep import (
            SWEEP_ACTION,
            SweepContractError,
            SweepRequest,
            build_sweep_idempotency_key,
            parse_sweep_send_reply,
        )

        pin = CartridgePin(selection.cartridge_id, selection.cartridge_version, selection.cartridge_sha256)
        Run = self.env[ENRICHMENT_RUN]
        candidates, requests, facility_map = [], {}, {}
        for facility in facilities:
            if len(candidates) >= settings.max_candidates:
                break
            try:
                request = build_facility_sweep_request_v2(
                    self.env,
                    self,
                    record=facility,
                    cartridge=pin,
                    field_defs=Run._v2_field_defs(TARGET_FACILITY_PROFILE, facility),
                )
                candidate = build_sweep_candidate(request)
            except ConvergeV2NothingToRequest:
                continue
            except (ValueError, SweepContractError) as exc:
                _logger.warning("Facility profile %s left out of the sweep: %s", facility.id, exc)
                continue
            candidates.append(candidate)
            requests[candidate.entity_id] = request.to_dict()
            facility_map[candidate.entity_id] = facility.id
        if not candidates:
            self.write({"state": "done", "error": _("No eligible buyer facility had an empty mapped field.")})
            return
        key = build_sweep_idempotency_key(resolve_tenant(self.env), self.sweep_date.isoformat(), list(requests))
        vals = {
            "idempotency_key": key,
            "daily_budget_usd": settings.daily_budget_usd,
            "candidate_count": len(candidates),
            "candidate_requests": requests,
            "facility_map": facility_map,
            "ingested": {},
        }
        try:
            sweep_request = SweepRequest(tuple(candidates), settings.daily_budget_usd, key)
            result = send_sweep_action(
                self.env, action=SWEEP_ACTION, payload=sweep_request.to_dict(), idempotency_key=key
            )
            audit = extract_audit_metadata(result["packet"])
            reply = parse_sweep_send_reply(result["payload"], request=sweep_request)
        except (GateIntegrationError, SweepContractError) as exc:
            failure = getattr(exc, "failure_class", None) or "contract"
            self.write({**vals, "state": "failed", "error": f"{failure}: {exc}"})
            _logger.error("Enrichment sweep %s failed to send (%s): %s", self.name, failure, exc)
            return
        self.write(
            {
                **vals,
                "state": "sent",
                "sweep_id": reply.sweep_id,
                "accepted_count": reply.accepted_count,
                "rejected_count": reply.rejected_count,
                "rejections": [_rejection(r.entity_id, r.reason, "send") for r in reply.rejected],
                "gate_packet_id": audit.get("gate_packet_id"),
                "gate_correlation_id": audit.get("gate_correlation_id"),
            }
        )
        self.message_post(
            body=_("Sent %(n)s candidate(s) to EIE as sweep %(id)s (accepted %(a)s, rejected %(r)s).")
            % {"n": len(candidates), "id": reply.sweep_id, "a": reply.accepted_count, "r": reply.rejected_count},
            subtype_xmlid="mail.mt_note",
        )

    # ── Results (cron 2) ────────────────────────────────────────────────

    @api.model
    def _cron_collect_results(self):
        """Follow-up: page results of every open sweep into review-state runs."""
        # sudo: system job as the group-less service user; it creates review-state runs only,
        # which write nothing to a partner or profile before a human approves them.
        self = self.sudo()  # noqa: PLW0642  # cron-sudo-justification: group-less service user
        try:
            settings = self._sweep_settings()
        except policy.SweepSettingsError as exc:
            _logger.error("Enrichment sweep results not collected: %s", exc)
            return False
        if not settings.enabled:
            return False
        for sweep in self.search([("state", "in", OPEN_STATES)], order="id", limit=MAX_OPEN_SWEEPS_PER_PASS):
            if sweep._try_lock():
                sweep._collect()
        return True

    def _try_lock(self):
        """Row lock so two collectors never ingest the same sweep at once."""
        self.ensure_one()
        try:
            with self.env.cr.savepoint(flush=False):
                self.env.cr.execute(
                    "SELECT id FROM plasticos_enrichment_sweep WHERE id = %s FOR UPDATE NOWAIT", (self.id,)
                )
        except pg_errors.LockNotAvailable:
            _logger.info("Enrichment sweep %s is being collected elsewhere.", self.id)
            return False
        return True

    def action_collect_results(self):
        """Manual: collect results for the selected open sweeps now."""
        if not self.env.user.has_group("plasticos_enrichment.group_enrichment_manager"):
            raise UserError(_("Only enrichment managers may collect sweep results."))
        for sweep in self.filtered(lambda s: s.state in OPEN_STATES):
            if sweep._try_lock():
                sweep._collect()
        return True

    def _collect(self):
        self.ensure_one()
        from odoo.addons.plasticos_gate.services.gate_client import send_sweep_action
        from odoo.addons.plasticos_gate.services.gate_config import GateIntegrationError
        from odoo.addons.plasticos_gate.services.gate_mappers import extract_audit_metadata
        from odoo.addons.plasticos_gate.services.gate_sweep import (
            SWEEP_RESULTS_ACTION,
            SWEEP_STATE_FAILED,
            SweepContractError,
            SweepResultsRequest,
            parse_sweep_results_page,
        )

        cursor = None
        ingested = dict(self.ingested or {})
        rejections = list(self.rejections or [])
        seen_skips = {(r.get("entity_id"), r.get("stage")) for r in rejections}
        page = None
        audit = {}
        for _page_no in range(MAX_RESULT_PAGES):
            try:
                result = send_sweep_action(
                    self.env,
                    action=SWEEP_RESULTS_ACTION,
                    payload=SweepResultsRequest(self.sweep_id, cursor).to_dict(),
                    correlation_id=self.gate_correlation_id or None,
                )
                audit = extract_audit_metadata(result["packet"])
                page = parse_sweep_results_page(result["payload"])
            except (GateIntegrationError, SweepContractError) as exc:
                failure = getattr(exc, "failure_class", None) or "contract"
                # A retryable transport failure keeps the sweep open for the next pass.
                vals = dict(error=f"{failure}: {exc}", ingested=ingested, rejections=rejections)
                if failure != "retryable":
                    vals["state"] = "failed"
                self.write(vals)
                _logger.error("Enrichment sweep %s results failed (%s): %s", self.name, failure, exc)
                return
            for item in page.results:
                if item.entity_id in ingested:
                    continue
                run_id, problem = self._ingest_result(item.entity_id, item.response_dict(), audit)
                if run_id:
                    ingested[item.entity_id] = run_id
                elif (item.entity_id, "result") not in seen_skips:
                    rejections.append(_rejection(item.entity_id, problem, "result"))
                    seen_skips.add((item.entity_id, "result"))
            for skip in page.skipped:
                if (skip.entity_id, "skipped") not in seen_skips:
                    rejections.append(_rejection(skip.entity_id, skip.reason, "skipped"))
                    seen_skips.add((skip.entity_id, "skipped"))
            cursor = page.next_cursor
            if cursor is None:
                break
        finished = page is not None and page.finished
        state = self.state
        if finished:
            state = "failed" if page.state == SWEEP_STATE_FAILED else "done"
        elif page is not None:
            state = "running"
        # Keyword form: these are field names, not enum values (phantom-enum scan).
        self.write(
            dict(
                state=state,
                eie_state=page.state if page else self.eie_state,
                ingested=ingested,
                ingested_count=len(ingested),
                rejections=rejections,
                skipped_count=len([r for r in rejections if r.get("stage") == "skipped"]),
                budget=page.budget_dict() if page else self.budget,
                gate_packet_id=audit.get("gate_packet_id") or self.gate_packet_id,
                error=False,
            )
        )

    def _ingest_result(self, entity_id, response, audit):
        """One result -> one enrichment run in ``review`` (or ``degraded`` with the reason).

        Returns (run_id, None) or (None, reason) when no run could be tied to
        what Odoo sent (an entity it never sent, a vanished or re-parented profile).
        """
        self.ensure_one()
        body = (self.candidate_requests or {}).get(entity_id)
        facility_id = (self.facility_map or {}).get(entity_id)
        if not body or not facility_id:
            return None, "result for an entity this sweep never sent"
        facility = self.env[FACILITY_PROFILE].browse(int(facility_id)).exists()
        if not facility or not facility.partner_id or f"res.partner:{facility.partner_id.id}" != entity_id:
            return None, "facility profile no longer exists or no longer belongs to this partner"
        Run = self.env[ENRICHMENT_RUN]
        try:
            with self.env.cr.savepoint():
                run = Run.create(
                    {
                        "partner_id": facility.partner_id.id,
                        "facility_profile_id": facility.id,
                        "engine_used": "gate",
                    }
                )
                try:
                    request = Run._v2_request_from_body(body)
                    field_defs = run._v2_field_defs(TARGET_FACILITY_PROFILE, facility)
                    reason = run._v2_review_from_reply(
                        TARGET_FACILITY_PROFILE, facility, field_defs, request, response, audit
                    )
                except (KeyError, TypeError, ValueError) as exc:
                    reason = f"Gate converge v2 sweep result unusable: {exc}"
                if reason is not None:
                    run.write(
                        {
                            "state": "degraded",
                            "failure_class": "unknown",
                            "validation_issues": [str(reason)],
                            **getattr(reason, "audit_vals", {}),
                        }
                    )
                run.message_post(
                    body=_("Created from enrichment sweep %(sweep)s (EIE sweep %(id)s).")
                    % {"sweep": self.name, "id": self.sweep_id},
                    subtype_xmlid="mail.mt_note",
                )
        except Exception as exc:  # noqa: BLE001 — one bad result must not stop the sweep; recorded, never written
            _logger.exception("Enrichment sweep %s: result for %s could not be ingested", self.name, entity_id)
            return None, f"ingestion failed: {exc}"
        return run.id, None
