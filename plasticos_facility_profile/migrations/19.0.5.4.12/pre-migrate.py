"""Remove the stale Facility Profile tab gate from the stored partner UX view.

Version 19.0.5.4.11 removed ``<page name="facility_profile">`` from
``view_partner_form_profile_tab`` and, in the same change, removed the child
xpath ``//page[@name='facility_profile']`` from ``partner_form_plasticos_ux``.

The manifest loads ``views/facility_profile_views.xml`` before
``views/partner_ux.xml``. On upgrade, the new parent arch is validated together
with the child arch still stored in the database. That stored child still
targets the removed page, so the upgrade stops with "cannot be located in
parent view" before ``partner_ux.xml`` is reloaded. A fresh install never has
the stale child.

This pre-migrate removes only that xpath node from the stored child arch, in
every language value of ``arch_db``. It keeps the view row, its id and its
external id; ``partner_ux.xml`` then rewrites the arch from the file. A stored
arch without the node is left unchanged, so a second run changes nothing.
"""

import json
import logging
import re

_logger = logging.getLogger(__name__)

VIEW_MODULE = "plasticos_facility_profile"
VIEW_NAME = "partner_form_plasticos_ux"

# The stored arch is lxml output: double-quoted attributes, ``>`` escaped inside
# attribute values. The node has no nested xpath, so the first closing tag ends it.
_QUOTE = r"(?:'|&apos;|&#39;)"
_STALE_NODE = re.compile(
    r"<xpath\b[^>]*?\bexpr=\"//page\[@name=" + _QUOTE + r"facility_profile" + _QUOTE + r"\]\"[^>]*?"
    r"(?:/>|>.*?</xpath\s*>)",
    re.DOTALL,
)


def strip_stale_node(arch):
    """Return ``arch`` without the stale facility_profile xpath, or None when it has none."""
    if not isinstance(arch, str):
        return None
    stripped, count = _STALE_NODE.subn("", arch)
    return stripped if count else None


def strip_arch_db(arch_db):
    """Return the ``arch_db`` language map with the stale node removed, or None when unchanged.

    ``ir.ui.view.arch_db`` is ``fields.Text(translate=xml_translate)``; in
    Odoo 19 it is stored as JSONB keyed by language code.
    """
    if not isinstance(arch_db, dict):
        return None
    changed = False
    result = {}
    for lang, arch in arch_db.items():
        stripped = strip_stale_node(arch)
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
    # Parameterised read of the one view this upgrade breaks, by its external id.
    cr.execute(
        """
        SELECT v.id, v.arch_db
          FROM ir_ui_view v
          JOIN ir_model_data d
            ON d.model = 'ir.ui.view'
           AND d.res_id = v.id
         WHERE d.module = %s
           AND d.name = %s
        """,
        (VIEW_MODULE, VIEW_NAME),
    )
    for view_id, arch_db in cr.fetchall():
        if isinstance(arch_db, str):
            arch_db = json.loads(arch_db)
        stripped = strip_arch_db(arch_db)
        if stripped is None:
            _logger.info("%s pre-migrate: view %s has no stale facility_profile xpath", VIEW_MODULE, view_id)
            continue
        # Raw SQL is required: the ORM would validate the arch against the parent,
        # which is the failure this migration exists to prevent.
        cr.execute(
            "UPDATE ir_ui_view SET arch_db = %s::jsonb WHERE id = %s",
            (json.dumps(stripped), view_id),
        )
        _logger.info(
            "%s pre-migrate: removed stale //page[@name='facility_profile'] xpath from view %s (%s languages)",
            VIEW_MODULE,
            view_id,
            len(stripped),
        )
