"""Schedule flags inside the existing load-obligation sweep (ADR-135 §7–§8).

The sweep does not run as Linda, does not accept a slot, and does not add a cron.
Each flag opens one activity and one shadow request. The drafted mail stays
shadow until the live cutover. Export notices are skipped while plasticos_export
is not installed.
"""

import hashlib
import json
import logging
from datetime import date
from zoneinfo import ZoneInfo

from odoo import api, fields, models

from ..schedule_window import (
    AUDIENCE_BUYER,
    AUDIENCE_DELIVERY_SITE,
    AUDIENCE_PICKUP_SITE,
    AUDIENCE_SHIPPER,
    PARAMETER_DEFAULTS,
    ExportWindow,
    ScheduleFacts,
    ScheduleSettings,
    compute_window,
    evaluate_flags,
    export_notices,
    staging_deadline,
)
from .linda_approval import LINDA_STOPPED_REASON, linda_stopped, linda_user
from .linda_request import LINDA_MODE_LIVE, LINDA_MODE_OFF, SOURCE_LOAD

_logger = logging.getLogger(__name__)

_FIELD_ABSENT = date(1, 1, 1)
_TEMPLATES = {
    "earlier_option_available": "plasticos_logistics.mail_template_linda_earlier_option_available",
    "ready_slot_far": "plasticos_logistics.mail_template_linda_ready_slot_far",
    "needs_delivery_slot": "plasticos_logistics.mail_template_linda_needs_delivery_slot",
    "dock_rule_unverified": "plasticos_logistics.mail_template_linda_dock_rule_unverified",
    "site_hours_unknown": "plasticos_logistics.mail_template_linda_site_hours_unknown",
    "weight_unknown": "plasticos_logistics.mail_template_linda_weight_unknown",
    "export_cutoff_notice": "plasticos_logistics.mail_template_linda_export_cutoff_notice",
    "booking_roll_request": "plasticos_logistics.mail_template_linda_booking_roll_request",
}
_SUMMARIES = {
    "earlier_option_available": "Earlier delivery slot",
    "ready_slot_far": "Delivery slot is far",
    "needs_delivery_slot": "Delivery slot needed",
    "dock_rule_unverified": "Dock rule unverified",
    "site_hours_unknown": "Site hours unknown",
    "weight_unknown": "Full weight unknown",
    "export_cutoff_notice": "Export cutoff at risk",
    "booking_roll_request": "Booking roll request",
}


class PlasticosLogisticsRequestSchedule(models.Model):
    _inherit = "plasticos.logistics.request"

    def _run_load_obligations(self, loads=None):
        results = super()._run_load_obligations(loads=loads)
        if isinstance(results, list) and len(results) == 1 and results[0].get("reason") == LINDA_STOPPED_REASON:
            return results
        # Off records nothing: the same gate the acknowledgement writer uses.
        if self._linda_mode() == LINDA_MODE_OFF:
            return results
        target = loads
        if target is None:
            target = self._load_sweep_page([("state", "not in", ["closed", "exception"])], "schedule")
        self._evaluate_schedule_flags(target)
        return results

    def _schedule_settings(self):
        params = self.env["ir.config_parameter"].sudo()  # sudo: system parameters are settings-admin only
        parsed = []
        for _key, default in PARAMETER_DEFAULTS:
            raw = params.get_param(_key, default)
            try:
                parsed.append(int(raw))
            except (TypeError, ValueError):
                parsed.append(int(default))
        return ScheduleSettings(*parsed)

    def _export_installed(self):
        if "plasticos.export.booking" not in self.env:
            return False
        module = (
            self.env["ir.module.module"]
            .sudo()  # sudo: module install state is not a logistics right
            .search([("name", "=", "plasticos_export")], limit=1)
        )
        return bool(module) and module.state == "installed"

    @api.model
    def _evaluate_schedule_flags(self, loads):
        if linda_stopped(self.env):
            return
        for load in loads:
            try:
                with self.env.cr.savepoint():
                    self._evaluate_one_load(load)
            except Exception:
                _logger.exception("schedule flags skipped for load %s", load.id)

    def _evaluate_one_load(self, load):
        facts = self._facts_for(load)
        flags = [*evaluate_flags(facts), *export_notices(self._export_installed(), self._export_window(load, facts))]
        for flag in flags:
            self._open_flag(load, flag)

    def _facts_for(self, load):
        pickup = load.pickup_partner_id
        delivery = load.delivery_partner_id
        accepted = load.appointment_ids.filtered(
            lambda appointment: appointment.side == "delivery" and appointment.state == "accepted"
        )[:1]
        delivery_tz = _partner_tz(delivery)
        available = []
        for appointment in load.appointment_ids:
            if appointment.side != "delivery" or appointment.state not in ("requested", "proposed"):
                continue
            slot = _local_date(appointment.slot_start, delivery_tz)
            if slot:
                available.append(slot)
        sale = load.sale_order_id
        minimum = load.transaction_id.minimum_net_weight if load.transaction_id else 0.0
        return ScheduleFacts(
            today=fields.Date.context_today(load),
            expected_ready_date=load.expected_ready_date or None,
            ready_confirmed=bool(load.ready_confirmed_at),
            ready_net_weight_lbs=load.ready_net_weight_lbs or None,
            minimum_net_weight=minimum or None,
            miles=self._miles(load),
            delivery_rule=load.delivery_term or None,
            pickup_rule=load.pickup_dock_rule or None,
            accepted_delivery=_local_date(accepted.slot_start, delivery_tz) if accepted else None,
            available_slots=tuple(available),
            pickup_site=bool(pickup),
            delivery_site=bool(delivery),
            pickup_confirmed_on=_confirmed_on(pickup),
            delivery_confirmed_on=_confirmed_on(delivery),
            pickup_hours=_shipping_hours(pickup),
            delivery_hours=_shipping_hours(delivery),
            pickup_tz=_partner_tz(pickup),
            delivery_tz=delivery_tz,
            buyer_po_ref=(sale.client_order_ref or sale.name or "") if sale else "",
            settings=self._schedule_settings(),
        )

    def _miles(self, load):
        estimate = self.env["plasticos.freight.estimate"].search(
            [
                ("source_model", "=", "plasticos.load"),
                ("source_record_id", "=", load.id),
                ("geometry_status", "=", "available"),
            ],
            order="id desc",
            limit=1,
        )
        if not estimate or not estimate.haversine_miles:
            return None
        return estimate.haversine_miles

    def _export_link(self, load):
        if "plasticos.export.booking.cargo.link" not in self.env:
            return False
        link_model = self.env["plasticos.export.booking.cargo.link"]
        link = link_model.search(
            [("source_load_id", "=", load.id), ("state", "!=", "released")],
            order="id desc",
            limit=1,
        )
        if not link and load.sale_order_id:
            link = link_model.search(
                [("sale_order_id", "=", load.sale_order_id.id), ("state", "!=", "released")],
                order="id desc",
                limit=1,
            )
        return link

    def _export_window(self, load, facts):
        if not self._export_installed():
            return None
        link = self._export_link(load)
        booking = link.booking_id if link else False
        revision = booking.current_revision_id if booking else False
        if not revision:
            return None
        terms = revision.additional_terms or {}
        cutoff = booking.current_cargo_cutoff_date or None
        computed = compute_window(facts)
        deadline = None
        if cutoff and computed.transit_days is not None:
            deadline = staging_deadline(cutoff, computed.transit_days, facts.settings)
        provider = terms.get("booking_provider")
        if provider == "buyer":
            buyer_provided = True
        elif provider in (None, ""):
            buyer_provided = None
        else:
            buyer_provided = False
        return ExportWindow(
            cutoff=cutoff,
            staging_deadline=deadline,
            next_cutoff=_iso_date(terms.get("next_cutoff")),
            next_vessel=terms.get("next_vessel") if isinstance(terms.get("next_vessel"), str) else None,
            known_gap=terms.get("known_gap") if isinstance(terms.get("known_gap"), str) else None,
            buyer_provided=buyer_provided,
            ready_date=load.expected_ready_date or None,
        )

    def _open_flag(self, load, flag):
        summary = f"{_SUMMARIES[flag.code]} ({flag.detail})"
        self._open_activity(load, summary, flag.body)
        partner = _audience_partner(load, flag.audience)
        if not load.company_id or not partner:
            return None
        return self._draft_schedule_shadow(load, flag, partner)

    def _open_activity(self, load, summary, body):
        existing = (
            self.env["mail.activity"]
            .sudo()  # sudo: the sweep deduplicates activities the cron user may not own
            .search([("res_model", "=", load._name), ("res_id", "=", load.id), ("summary", "=", summary)], limit=1)
        )
        if existing:
            return existing
        user = self._schedule_activity_user(load)
        if not user:
            return self.env["mail.activity"]
        return load.activity_schedule("mail.mail_activity_data_todo", user_id=user.id, summary=summary, note=body)

    def _schedule_activity_user(self, load):
        """Linda once her mode is live; Logistics before that."""
        if self._linda_mode() == LINDA_MODE_LIVE:
            linda = linda_user(self.env)
            if linda and linda.sudo().active:  # sudo: any caller may learn whether Linda is stopped
                return linda
        group = self.env.ref("plasticos_security_base.group_logistics", raise_if_not_found=False)
        users = self.env["res.users"]
        if group:
            users = users.search(
                [("group_ids", "in", group.id), ("share", "=", False), ("active", "=", True)],
                order="id",
            )
            if load.company_id:
                scoped = users.filtered(lambda user: load.company_id in user.company_ids)
                if scoped:
                    users = scoped
        return users[:1] or self.env.user

    def _draft_schedule_shadow(self, load, flag, partner):
        """One shadow request per purpose, source and detail. Never queued and never sent."""
        revision_key = f"{flag.code}:{flag.detail}"
        existing = self.search(
            [
                ("company_id", "=", load.company_id.id),
                ("source_kind", "=", SOURCE_LOAD),
                ("source_res_id", "=", load.id),
                ("purpose", "=", flag.code),
                ("source_revision_key", "=", revision_key),
                ("partner_id", "=", partner.id),
            ],
            limit=1,
        )
        if existing:
            return existing
        snapshot = {}
        snapshot["reference"] = load.name or ""
        snapshot["paragraphs"] = [flag.body]
        snapshot["subject"] = _SUMMARIES[flag.code]
        return self.sudo().create(  # sudo: the sweep files shadow evidence and holds no request ACL
            {
                "company_id": load.company_id.id,
                "purpose": flag.code,
                "source_kind": SOURCE_LOAD,
                "source_model": load._name,
                "source_res_id": load.id,
                "source_revision_key": revision_key,
                "operation_key": revision_key,
                "source_payload_snapshot": json.dumps(snapshot, sort_keys=True),
                "template_xmlid": _TEMPLATES[flag.code],
                "partner_id": partner.id,
                "recipient_email": partner.email or "",
                "revision": 1,
                "payload_fingerprint": hashlib.sha256(flag.body.encode("utf-8")).hexdigest(),
                "subject": _SUMMARIES[flag.code],
                "state": "shadow",
                "state_reason": "shadow_until_live_cutover",
            }
        )


def _partner_tz(partner):
    if not partner:
        return None
    return (partner.tz or "").strip() or None


def _shipping_hours(partner):
    if not partner or "shipping_hours" not in partner._fields:
        return None
    return partner.shipping_hours or ""


def _confirmed_on(partner):
    """Blank means unverified. A missing column is not judged (the sentinel is not None)."""
    if not partner or "dock_rule_confirmed_on" not in partner._fields:
        return _FIELD_ABSENT
    return partner.dock_rule_confirmed_on or None


def _local_date(moment, tz_name):
    if not moment:
        return None
    stamp = fields.Datetime.to_datetime(moment)
    if not tz_name:
        return stamp.date()
    try:
        zone = ZoneInfo(tz_name)
    except (KeyError, ValueError):
        return None
    return stamp.replace(tzinfo=ZoneInfo("UTC")).astimezone(zone).date()


def _audience_partner(load, audience):
    supplier = load.transaction_id.supplier_id if load.transaction_id else False
    buyer = load.transaction_id.buyer_id if load.transaction_id else False
    if audience in (AUDIENCE_SHIPPER, AUDIENCE_PICKUP_SITE):
        return load.pickup_partner_id or supplier
    if audience == AUDIENCE_DELIVERY_SITE:
        return load.delivery_partner_id or buyer
    if audience == AUDIENCE_BUYER:
        if load.sale_order_id and load.sale_order_id.partner_id:
            return load.sale_order_id.partner_id
        return buyer or load.delivery_partner_id
    return load.env["res.partner"]


def _iso_date(value):
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None
