"""Dock-rule sides (ADR-135 §3 and §4). Odoo-free.

The registry tests under the addons exercise the same rules on records.
This module is the pure-python proof of the lookup, the migration predicate,
the sale-order default, and the confirmation activity's source.
"""

from __future__ import annotations

import importlib.util
import inspect
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _dock_rule():
    path = REPO / "plasticos_transaction" / "dock_rule.py"
    spec = importlib.util.spec_from_file_location("plasticos_dock_rule_pure", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_fcfs_supplier_and_appointment_buyer_split_the_sides():
    """The supplier rule is pickup. The ship-to site rule is delivery."""
    rule = _dock_rule().rule_from_site_then_company
    pickup = rule("fcfs", "fcfs", partner_is_site=False)
    delivery = rule("appointment", "fcfs", partner_is_site=True)
    assert pickup == "fcfs"
    assert delivery == "appointment"


def test_sale_order_default_is_appointment():
    rule = _dock_rule().rule_from_site_then_company
    assert rule(None, None, partner_is_site=False) == "appointment"
    source = (REPO / "plasticos_automation" / "models" / "sale_order_automation.py").read_text(encoding="utf-8")
    assert 'default="appointment"' in source
    assert 'default="fcfs"' not in source


def test_site_rule_beats_company_rule():
    rule = _dock_rule().rule_from_site_then_company
    assert rule("fcfs", "appointment", partner_is_site=True) == "fcfs"
    assert rule("appointment", "fcfs", partner_is_site=True) == "appointment"


def test_migration_copies_both_sides_and_is_a_no_op_on_replay():
    plan = _dock_rule().plan_copy
    rows = [("fcfs", None), ("appointment", None), ("appointment", "fcfs"), (None, None)]
    copied, first = plan(rows)
    assert copied == [("fcfs", "fcfs"), ("appointment", "appointment"), ("appointment", "fcfs"), (None, None)]
    assert first == {"seen": 4, "copied": 2, "already_set": 1, "blank": 1}
    again, second = plan(copied)
    assert again == copied
    assert second["copied"] == 0
    assert second["already_set"] == 3
    source = inspect.getsource(_dock_rule().copy_pickup_dock_rule)
    assert "pickup_dock_rule IS NULL" in source
    assert "delivery_term IS NOT NULL" in source
    assert "plasticos_transaction" in _dock_rule().COPY_TABLES
    assert "purchase_order" in _dock_rule().COPY_TABLES
    assert "plasticos_load" in _dock_rule().COPY_TABLES


def test_confirmation_automation_creates_one_activity_and_sends_no_mail():
    xml = (REPO / "plasticos_automation" / "data" / "workflow_automations.xml").read_text(encoding="utf-8")
    start = xml.index('id="action_request_dock_appointment"')
    end = xml.index('id="rule_request_dock_appointment"')
    block = xml[start:end]
    assert "send_mail" not in block
    assert "appointment_requested =" not in block
    assert ".write(" not in block
    assert "_plasticos_request_delivery_appointment_activity" in block
    method_source = (REPO / "plasticos_automation" / "models" / "sale_order_automation.py").read_text(encoding="utf-8")
    method = method_source.split("def _plasticos_request_delivery_appointment_activity", 1)[1]
    method = method.split("def action_request_dock_appointment", 1)[0]
    assert "Request delivery appointment" in method_source
    assert "Expected ready date:" in method
    assert "send_mail" not in method
    assert "appointment_requested =" not in method
    assert "plasticos_security_base.group_logistics" in method_source
