"""Appointments and readiness (ADR-135 §5–§8). Odoo-free.

BRS-02-R005, BRS-03-R018, BRS-03-R019, BRS-03-R021, BRS-03-R022, POS-INV-21.
"""

from __future__ import annotations

import importlib.util
import sys
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _schedule():
    path = REPO / "plasticos_logistics" / "schedule_window.py"
    spec = importlib.util.spec_from_file_location("plasticos_schedule_window_pure", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _facts(module, **overrides):
    settings = module.ScheduleSettings(
        near_window_days=30, miles_per_day=500, lead_days=2, buffer_days=1, far_gap_days=3
    )
    base = {
        "today": date(2026, 11, 16),  # Monday
        "expected_ready_date": date(2026, 11, 16),
        "ready_confirmed": True,
        "ready_net_weight_lbs": 40000,
        "minimum_net_weight": 36000,
        "miles": 500,
        "delivery_rule": "appointment",
        "pickup_rule": "appointment",
        "settings": settings,
    }
    base.update(overrides)
    return module.ScheduleFacts(**base)


def test_brs_earlier_slot_yes_no_and_unanswered():
    """Yes books X. No books Y. Silence waits through the decision date, then books Y."""
    outcome = _schedule().earlier_slot_outcome
    decision = date(2026, 11, 12)
    assert outcome("yes", date(2026, 11, 10), decision) == "book_x"
    assert outcome("no", date(2026, 11, 10), decision) == "book_y_accept"
    assert outcome(None, date(2026, 11, 12), decision) == "wait"
    assert outcome("unanswered", date(2026, 11, 13), decision) == "book_y_accept"
    assert outcome("maybe", date(2026, 11, 20), decision) == "wait"


def test_brs_ready_with_the_slot_far_out():
    window = _schedule()
    facts = _facts(
        window,
        accepted_delivery=date(2026, 12, 15),
        available_slots=(),
    )
    flags = window.evaluate_flags(facts)
    far = [flag for flag in flags if flag.code == "ready_slot_far"]
    assert len(far) == 1
    assert far[0].audience == "buyer"
    assert "Is there any chance of a slot sooner than 2026-12-15?" in far[0].body
    assert "We can deliver as early as" in far[0].body


def test_brs_needs_a_delivery_slot():
    window = _schedule()
    facts = _facts(window, accepted_delivery=None, delivery_rule="appointment")
    flags = window.evaluate_flags(facts)
    needed = [flag for flag in flags if flag.code == "needs_delivery_slot"]
    assert len(needed) == 1
    assert needed[0].audience == "buyer"
    assert needed[0].body.startswith("Ready now. Can we book delivery for ")
    assert needed[0].body.endswith(" or later?")


def test_brs_dock_rule_unverified():
    window = _schedule()
    facts = _facts(window, pickup_site=True, delivery_site=True, pickup_confirmed_on=None, delivery_confirmed_on=None)
    flags = [flag for flag in window.evaluate_flags(facts) if flag.code == "dock_rule_unverified"]
    assert {flag.audience for flag in flags} == {"pickup_site", "delivery_site"}
    assert flags[0].body == "Do you require an appointment, or is it first come, first served?"


def test_brs_site_hours_unknown():
    window = _schedule()
    facts = _facts(
        window,
        pickup_site=True,
        pickup_hours="",
        pickup_tz="",
        delivery_site=True,
        delivery_hours="M-F 8-4",
        delivery_tz="",
    )
    flags = [flag for flag in window.evaluate_flags(facts) if flag.code == "site_hours_unknown"]
    assert {flag.detail for flag in flags} == {"pickup", "delivery"}
    assert flags[0].body == "What are your shipping hours, and what time zone are they in?"


def test_brs_03_r019_fcfs_pickup_with_appointment_delivery_creates_no_pickup():
    window = _schedule()
    opened = window.appointments_to_open("fcfs", "appointment", ready_confirmed=True)
    assert opened == ["delivery"]
    assert window.may_open_pickup_appointment("fcfs", True) is False


def test_pos_inv_21_light_load_is_refused_and_a_human_override_needs_a_reason():
    decide = _schedule().light_load_decision
    assert decide(True, 30000, 36000, "please") == "refuse"
    assert decide(False, 30000, 36000, None) == "need_reason"
    assert decide(False, 30000, 36000, "   ") == "need_reason"
    assert decide(False, 30000, 36000, "shipper confirmed the deduction stands") == "override"
    assert decide(True, None, 36000, None) == "allow"
    assert decide(False, 40000, 36000, None) == "allow"


def test_unknown_weight_asks_before_any_slot_is_proposed():
    window = _schedule()
    facts = _facts(
        window,
        ready_net_weight_lbs=0,
        minimum_net_weight=36000,
        accepted_delivery=None,
        available_slots=(date(2026, 11, 18), date(2026, 11, 30)),
    )
    flags = window.evaluate_flags(facts)
    codes = {flag.code for flag in flags}
    assert "weight_unknown" in codes
    assert codes.isdisjoint(window.PROPOSAL_FLAGS)
    assert "not proposed until that weight is known" in next(
        flag.body for flag in flags if flag.code == "weight_unknown"
    )


def test_no_email_template_contains_a_waiver_offer():
    window = _schedule()
    template = (REPO / "plasticos_logistics" / "data" / "linda_schedule_mail_templates.xml").read_text(encoding="utf-8")
    wording = (REPO / "plasticos_logistics" / "schedule_window.py").read_text(encoding="utf-8")
    blob = (template + "\n" + wording).lower()
    assert "waiv" not in blob
    assert "the buyer has an open delivery slot on" in template.lower()
    assert "do you require an appointment, or is it first come, first served?" in template.lower()
    for flag in window.evaluate_flags(
        _facts(window, pickup_site=True, delivery_site=True, accepted_delivery=date(2026, 12, 15))
    ):
        assert "waiv" not in flag.body.lower()


def test_brs_03_r022_invalidation_cancels_pickup_only_after_the_new_slot_is_accepted():
    effects = _schedule().acceptance_effects
    current = {"delivery": ("old",), "pickup": ("pickup",)}
    assert effects("delivery", ("new",), False, current) == []
    applied = effects("delivery", ("new",), True, current)
    assert applied[0] == ("accept", "delivery", ("new",))
    assert ("cancel", "pickup", ("pickup",), _schedule().R022_CANCEL_REASON) in applied
    assert applied.index(("accept", "delivery", ("new",))) < applied.index(
        ("cancel", "pickup", ("pickup",), _schedule().R022_CANCEL_REASON)
    )
    assert ("rebook", "pickup") in applied
    same = effects("delivery", ("old",), True, current)
    assert same == [("accept", "delivery", ("old",))]
    assert all(effect[0] != "cancel" for effect in same)


def test_brs_03_r018_does_not_overwrite_the_accepted_slot():
    applied = _schedule().acceptance_effects("delivery", ("new",), True, {"delivery": ("old",)})
    assert applied[1][0] == "cancel"
    assert applied[1][3] == _schedule().R018_CANCEL_REASON
    assert "overwrite" not in applied[1][3]


def test_brs_03_r021_acceptance_does_not_consult_another_load():
    source = (REPO / "plasticos_logistics" / "schedule_window.py").read_text(encoding="utf-8")
    plan = source.split("def acceptance_effects", 1)[1].split("def plan_appointment_backfill", 1)[0]
    assert "capacity" not in plan
    assert "other_load" not in plan


def test_export_guard_does_nothing_while_uninstalled_and_never_emits_booking_amend():
    window = _schedule()
    facts = window.ExportWindow(
        cutoff=date(2026, 11, 18),
        staging_deadline=date(2026, 11, 12),
        next_cutoff=date(2026, 11, 25),
        next_vessel="Next Vessel",
        known_gap="The port call is skipped.",
        buyer_provided=True,
        ready_date=date(2026, 11, 20),
    )
    assert window.export_notices(False, facts) == []
    assert window.export_notices(True, None) == []
    sent = window.export_notices(True, facts)
    assert [flag.code for flag in sent] == ["export_cutoff_notice", "booking_roll_request"]
    assert sent[0].audience == "shipper"
    assert "The port call is skipped." in sent[0].body
    assert "Next Vessel" in sent[0].body
    assert sent[1].audience == "buyer"
    withheld = window.export_notices(
        True,
        window.ExportWindow(
            cutoff=facts.cutoff,
            staging_deadline=facts.staging_deadline,
            next_cutoff=facts.next_cutoff,
            next_vessel=facts.next_vessel,
            known_gap=None,
            buyer_provided=None,
            ready_date=facts.ready_date,
        ),
    )
    assert [flag.code for flag in withheld] == ["export_cutoff_notice"]
    assert all(flag.code != "booking_amend" for flag in sent)
    amend = (REPO / "plasticos_logistics" / "data" / "linda_booking_mail_template.xml").read_text(encoding="utf-8")
    assert "Amended booking for a later accepted revision" in amend


def test_archiving_linda_stops_her_schedule_dispatch_and_appointment_commands():
    load = (REPO / "plasticos_logistics" / "models" / "load.py").read_text(encoding="utf-8")
    appointment = (REPO / "plasticos_logistics" / "models" / "load_appointment.py").read_text(encoding="utf-8")
    obligations = (REPO / "plasticos_logistics" / "models" / "schedule_obligations.py").read_text(encoding="utf-8")
    for method in ("def action_schedule", "def action_dispatch"):
        body = load.split(method, 1)[1].split("\n    def ", 1)[0]
        assert "linda_stop" in body
        assert body.index("linda_stop") < body.index("_apply_")
    accept = appointment.split("def action_accept_appointment", 1)[1].split("\n    def ", 1)[0]
    assert "linda_stop" in accept
    assert "linda_stopped" in obligations
    assert "action_accept(" not in obligations
    assert "action_schedule(" not in obligations
    assert "action_dispatch(" not in obligations


def test_schedule_purposes_match_the_request_constraint_and_templates():
    window = _schedule()
    source = (REPO / "plasticos_logistics" / "models" / "linda_request.py").read_text(encoding="utf-8")
    templates = (REPO / "plasticos_logistics" / "data" / "linda_schedule_mail_templates.xml").read_text(
        encoding="utf-8"
    )
    for purpose in window.SCHEDULE_PURPOSES:
        assert f'"{purpose}"' in source
        assert purpose in templates


def test_backfill_is_one_requested_appointment_and_idempotent():
    plan = _schedule().plan_appointment_backfill
    orders = [
        {"sale_order_id": 1, "load_ids": [10, 11], "existing_delivery_load_ids": []},
        {"sale_order_id": 2, "load_ids": [], "existing_delivery_load_ids": []},
        {"sale_order_id": 3, "load_ids": [30], "existing_delivery_load_ids": [30]},
    ]
    plans, first = plan(orders)
    assert plans == [{"sale_order_id": 1, "load_id": 10}]
    assert first == {"rows_seen": 3, "rows_created": 1, "already_present": 1, "skipped_no_load": 1}
    replay = [
        {"sale_order_id": 1, "load_ids": [10, 11], "existing_delivery_load_ids": [10]},
        {"sale_order_id": 2, "load_ids": [], "existing_delivery_load_ids": []},
        {"sale_order_id": 3, "load_ids": [30], "existing_delivery_load_ids": [30]},
    ]
    again, second = plan(replay)
    assert again == []
    assert second["rows_created"] == 0
    assert second["already_present"] == 2


def test_settings_defaults_and_hours_come_from_the_site():
    window = _schedule()
    stored = dict(window.PARAMETER_DEFAULTS)
    assert stored[window.PARAM_MILES_PER_DAY] == "500"
    assert stored[window.PARAM_LEAD_DAYS] == "2"
    assert stored[window.PARAM_BUFFER_DAYS] == "1"
    assert stored[window.PARAM_FAR_GAP_DAYS] == "3"
    assert stored[window.PARAM_NEAR_WINDOW_DAYS] == "7"
    assert window.hours_default("M-F 7-3", "M-F: 9:00 AM - 3:00 PM") == "M-F 7-3"
    assert window.hours_default("  ", "M-F: 9:00 AM - 3:00 PM") == "M-F: 9:00 AM - 3:00 PM"


def test_brs_02_r005_ready_date_and_weight_stay_out_of_the_confirmation_stamp():
    """The reported ready date and weight are inputs, not ready_confirmed_at."""
    source = (REPO / "plasticos_logistics" / "models" / "load.py").read_text(encoding="utf-8")
    assert "expected_ready_date" in source
    assert "ready_net_weight_lbs" in source
    confirm = source.split("def action_confirm_ready", 1)[1].split("def _linda_confirm_ready_gate", 1)[0]
    assert "expected_ready_date" not in confirm
    assert "ready_net_weight_lbs" not in confirm
