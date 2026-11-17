"""19.0.5.7.0 strips stored facility views that still name retired equipment fields."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRE_MIGRATE = ROOT / "plasticos_facility_profile/migrations/19.0.5.7.0/pre-migrate.py"

LIST_ARCH = (
    "<data>"
    '<xpath expr="//list/field[@name=\'process_type\']" position="before">'
    '<field name="partner_id" string="Facility"/>'
    "</xpath>"
    "</data>"
)
FORM_ARCH = (
    "<data>"
    '<xpath expr="//notebook[@name=\'facility_profile_pages\']" position="before">'
    '<field name="process_type" readonly="1"/>'
    "</xpath>"
    '<xpath expr="//notebook//field[@name=\'can_remove_metal\']" position="attributes">'
    '<attribute name="widget">boolean_toggle</attribute></xpath>'
    '<xpath expr="//notebook//field[@name=\'iso_certified\']" position="attributes">'
    '<attribute name="widget">boolean_toggle</attribute></xpath>'
    "</data>"
)
SEARCH_ARCH = (
    "<search>"
    '<field name="process_type"/>'
    '<field name="feedstock_type"/>'
    '<filter name="group_process" string="Process Type" context="{\'group_by\': \'process_type\'}"/>'
    '<filter name="group_feedstock" string="Feedstock" context="{\'group_by\': \'feedstock_type\'}"/>'
    "</search>"
)


def _load():
    spec = importlib.util.spec_from_file_location("facility_pre_migrate_5_7_0", PRE_MIGRATE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeCursor:
    def __init__(self, rows):
        self.rows = rows
        self.updates = []
        self._result = []

    def execute(self, sql, params=None):
        if "to_regclass" in sql:
            self._result = [("ir_ui_view", "ir_model_data")]
        elif "SELECT v.id" in sql:
            assert params[0] == "plasticos_facility_profile"
            self._result = [(view_id, name, arch) for view_id, name, arch in self.rows]
        elif sql.startswith("UPDATE ir_ui_view"):
            payload, view_id = params
            self.updates.append((view_id, json.loads(payload)))
            self._result = []
        else:
            raise AssertionError(sql)

    def fetchone(self):
        return self._result[0]

    def fetchall(self):
        return list(self._result)


def test_strips_retired_nodes_and_keeps_the_surviving_anchors():
    mod = _load()
    cr = FakeCursor(
        [
            (1, "facility_profile_list_ux", {"en_US": LIST_ARCH}),
            (2, "facility_profile_form_ux", {"en_US": FORM_ARCH}),
            (3, "view_facility_profile_search", {"en_US": SEARCH_ARCH}),
        ]
    )
    mod.migrate(cr, "19.0.5.6.0")
    updated = {view_id: arch["en_US"] for view_id, arch in cr.updates}
    assert "process_type" not in updated[1]
    assert "partner_id" not in updated[1]
    assert "process_type" not in updated[2]
    assert "can_remove_metal" not in updated[2]
    assert "iso_certified" in updated[2]
    assert "facility_profile_pages" in updated[2]
    assert "process_type" not in updated[3]
    assert "feedstock_type" in updated[3]


def test_second_run_does_not_update():
    mod = _load()
    cr = FakeCursor([(1, "facility_profile_list_ux", {"en_US": LIST_ARCH})])
    mod.migrate(cr, "19.0.5.6.0")
    cleaned = cr.updates[0][1]
    again = FakeCursor([(1, "facility_profile_list_ux", cleaned)])
    mod.migrate(again, "19.0.5.6.0")
    assert again.updates == []


def test_fresh_install_skips():
    mod = _load()
    cr = FakeCursor([(1, "facility_profile_list_ux", {"en_US": LIST_ARCH})])
    mod.migrate(cr, None)
    assert cr.updates == []
