"""Drop stored facility-view nodes that still name the retired equipment fields.

``views/facility_profile_views.xml`` loads before ``views/facility_profile_ux.xml``.
On upgrade the new parent list and form are checked against the child arches
still stored in the database. Those arches still xpath ``process_type`` and the
retired capability booleans, so the upgrade stops with "cannot be located in
parent view" before the UX file is reloaded. A fresh install has no stored child.

This removes only those nodes, in every language of ``arch_db``, and keeps the
view row. The UX file then rewrites the arch. A second run finds nothing.
"""

import json
import logging
import re

_logger = logging.getLogger(__name__)

_MODULE = "plasticos_facility_profile"
_VIEWS = (
    "facility_profile_list_ux",
    "facility_profile_form_ux",
    "view_facility_profile_search",
)
_STALE_FIELDS = (
    "process_type",
    "handles_flake",
    "handles_rollstock",
    "can_remove_metal",
    "can_reduce_moisture",
    "can_filter_fr",
    "can_screen_fines",
)
_QUOTE = r"(?:'|&apos;|&#39;)"


def _patterns():
    compiled = []
    for name in _STALE_FIELDS:
        compiled.append(
            re.compile(
                r"<xpath\b[^>]*?\bexpr=\"[^\"]*?@name="
                + _QUOTE
                + name
                + _QUOTE
                + r"[^\"]*\"[^>]*?(?:/>|>.*?</xpath\s*>)",
                re.DOTALL,
            )
        )
        compiled.append(
            re.compile(
                r"<field\b[^>]*?\bname=(?:\"|')" + name + r"(?:\"|')[^>]*/>",
                re.DOTALL,
            )
        )
    compiled.append(
        re.compile(
            r"<filter\b[^>]*?group_by['\"]:\s*['\"]process_type['\"][^>]*?/>",
            re.DOTALL,
        )
    )
    return compiled


_PATTERNS = _patterns()


def strip_stale_nodes(arch):
    """Return ``arch`` without retired-field nodes, or None when it has none."""
    if not isinstance(arch, str):
        return None
    current = arch
    changed = False
    for pattern in _PATTERNS:
        current, count = pattern.subn("", current)
        changed = changed or bool(count)
    return current if changed else None


def strip_arch_db(arch_db):
    """Return the language map with retired nodes removed, or None when unchanged."""
    if not isinstance(arch_db, dict):
        return None
    changed = False
    result = {}
    for lang, arch in arch_db.items():
        stripped = strip_stale_nodes(arch)
        if stripped is None:
            result[lang] = arch
        else:
            result[lang] = stripped
            changed = True
    return result if changed else None


def migrate(cr, version):
    if not version:
        return
    cr.execute("SELECT to_regclass('public.ir_ui_view'), to_regclass('public.ir_model_data')")
    view_table, data_table = cr.fetchone()
    if view_table is None or data_table is None:
        return
    cr.execute(
        """
        SELECT v.id, d.name, v.arch_db
          FROM ir_ui_view v
          JOIN ir_model_data d
            ON d.model = 'ir.ui.view'
           AND d.res_id = v.id
         WHERE d.module = %s
           AND d.name = ANY(%s)
        """,
        (_MODULE, list(_VIEWS)),
    )
    for view_id, name, arch_db in cr.fetchall():
        if isinstance(arch_db, str):
            arch_db = json.loads(arch_db)
        stripped = strip_arch_db(arch_db)
        if stripped is None:
            _logger.info("%s 19.0.5.7.0 pre-migrate: %s has no retired field node", _MODULE, name)
            continue
        cr.execute(
            "UPDATE ir_ui_view SET arch_db = %s::jsonb WHERE id = %s",
            (json.dumps(stripped), view_id),
        )
        _logger.info("%s 19.0.5.7.0 pre-migrate: stripped retired field nodes from %s", _MODULE, name)
