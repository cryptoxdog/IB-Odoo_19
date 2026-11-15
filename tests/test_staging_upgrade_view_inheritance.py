"""Upgrade from Staging 7b6c9acd: stale inherited-view arch must not block module load.

1. ``plasticos_facility_profile`` 19.0.5.4.12 pre-migrate strips the stale
   ``//page[@name='facility_profile']`` xpath from the stored
   ``partner_form_plasticos_ux`` arch, in every language, idempotently.
2. ``plasticos_crm_bridge.partner_form_material_bridge_stats`` anchors on a
   column the material-profile partner list still has.
"""

from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRE_MIGRATE = ROOT / "plasticos_facility_profile/migrations/19.0.5.4.12/pre-migrate.py"
FACILITY_MANIFEST = ROOT / "plasticos_facility_profile/__manifest__.py"
PARTNER_UX = ROOT / "plasticos_facility_profile/views/partner_ux.xml"
MATERIAL_PARENT = ROOT / "plasticos_material_profile/views/partner_material_ux.xml"
BRIDGE_CHILD = ROOT / "plasticos_crm_bridge/views/material_profile_views.xml"

STALE = (
    '<xpath expr="//page[@name=\'facility_profile\']" position="attributes">'
    '<attribute name="invisible">not is_facility</attribute></xpath>'
)
CHILD_ARCH = (
    "<data>"
    '<xpath expr="//div[@name=\'button_box\']" position="inside"><field name="facility_profile_count"/></xpath>'
    "<!-- gate -->" + STALE + '<xpath expr="//div[hasclass(\'o_address_format\')]" position="after">'
    '<field name="personal_intel"/></xpath>'
    "</data>"
)


def _load():
    spec = importlib.util.spec_from_file_location("facility_pre_migrate_5_4_12", PRE_MIGRATE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeCursor:
    """Minimal cursor over one ir_ui_view row keyed by the partner UX external id."""

    def __init__(self, arch_db, *, as_text=False):
        self.arch_db = arch_db
        self.as_text = as_text
        self.updates = []
        self._result = []

    def execute(self, sql, params=None):
        if "to_regclass" in sql:
            self._result = [("ir_ui_view", "ir_model_data")]
        elif sql.lstrip().startswith("SELECT v.id"):
            assert params == ("plasticos_facility_profile", "partner_form_plasticos_ux")
            stored = json.dumps(self.arch_db) if self.as_text else self.arch_db
            self._result = [(1706, stored)]
        elif sql.startswith("UPDATE ir_ui_view"):
            payload, view_id = params
            assert view_id == 1706
            self.arch_db = json.loads(payload)
            self.updates.append(view_id)
            self._result = []
        else:  # pragma: no cover - any other statement is a test failure
            raise AssertionError(sql)

    def fetchone(self):
        return self._result[0]

    def fetchall(self):
        return list(self._result)


def test_manifest_version_matches_migration_folder():
    assert '"version": "19.0.5.4.12"' in FACILITY_MANIFEST.read_text()


def test_strips_stale_node_in_every_language_and_keeps_the_rest():
    mod = _load()
    cr = FakeCursor({"en_US": CHILD_ARCH, "fr_FR": CHILD_ARCH})
    mod.migrate(cr, "19.0.5.4.11")
    assert cr.updates == [1706]
    for arch in cr.arch_db.values():
        assert "facility_profile'" not in arch
        assert "button_box" in arch
        assert "o_address_format" in arch
        assert "<!-- gate -->" in arch
        assert arch.count("<xpath") == 2


def test_second_run_is_a_no_op():
    mod = _load()
    cr = FakeCursor({"en_US": CHILD_ARCH})
    mod.migrate(cr, "19.0.5.4.11")
    once = dict(cr.arch_db)
    mod.migrate(cr, "19.0.5.4.11")
    assert cr.updates == [1706]
    assert cr.arch_db == once


def test_arch_without_the_node_is_untouched():
    mod = _load()
    clean = CHILD_ARCH.replace(STALE, "")
    cr = FakeCursor({"en_US": clean})
    mod.migrate(cr, "19.0.5.4.11")
    assert cr.updates == []
    assert cr.arch_db == {"en_US": clean}


def test_text_payload_and_self_closing_and_apos_variants():
    mod = _load()
    variant = (
        '<data><xpath expr="//page[@name=&apos;facility_profile&apos;]" position="attributes"/>'
        '<xpath expr="//div[@name=\'button_box\']" position="inside"/></data>'
    )
    cr = FakeCursor({"en_US": variant}, as_text=True)
    mod.migrate(cr, "19.0.5.4.11")
    assert cr.arch_db == {"en_US": '<data><xpath expr="//div[@name=\'button_box\']" position="inside"/></data>'}


def test_fresh_install_skips():
    mod = _load()
    cr = FakeCursor({"en_US": CHILD_ARCH})
    mod.migrate(cr, None)
    assert cr.updates == []


def test_current_partner_ux_file_has_no_stale_xpath():
    assert "//page[@name='facility_profile']" not in PARTNER_UX.read_text()


def test_crm_bridge_partner_stats_anchor_exists_in_material_parent():
    child = BRIDGE_CHILD.read_text()
    anchor = re.search(r"//field\[@name='material_profile_ids'\]//list/field\[@name='(\w+)'\]", child)
    assert anchor, "partner_form_material_bridge_stats anchor not found"
    parent = MATERIAL_PARENT.read_text()
    block = parent[parent.index('name="material_profile_ids"') :]
    list_block = block[block.index("<list") : block.index("</list>")]
    assert f'<field name="{anchor.group(1)}"' in list_block
