"""Upgrade plasticos_material_profile to 19.0.5.14.0.

Runs from pre-migrate, before the form selection drops REPRO and LOOSE and
before the unique index gains direction. Idempotent: a second run changes no
row. Counts are logged. A collision or a blank direction is reported and the
row is kept.
"""

from __future__ import annotations

import logging

from .direction import blank_direction_ids, collision_groups, direction_for, is_site_shape
from .vocabulary_retirement import confirms_pellets, plan_loose, plan_repro

_logger = logging.getLogger(__name__)

MIGRATION = "19.0.5.14.0"
_LINE_TABLES = ("purchase_order_line", "sale_order_line", "account_move_line")
_RELATION_CANDIDATES = (
    "plasticos_material_attribute_plasticos_material_profile_rel",
    "plasticos_material_profile_plasticos_material_attribute_rel",
)


def migrate_vocabulary(cr) -> dict:
    """Backfill direction and retire the two forms. Return the counts."""
    counts = {
        "direction_set": 0,
        "direction_blank": 0,
        "direction_collisions": 0,
        "repro_pellets": 0,
        "repro_review": 0,
        "loose_cleared": 0,
        "loose_blocked": 0,
        "renamed": 0,
        "template_pellets": 0,
        "template_repro_review": 0,
        "template_loose": 0,
    }
    if not _table_exists(cr, "plasticos_material_profile"):
        _logger.info("material vocabulary %s: profile table absent; nothing to migrate", MIGRATION)
        return counts
    _ensure_direction_column(cr)
    _ensure_review_table(cr)
    partners = _partner_facts(cr)
    profiles = _profiles(cr)
    _assign_direction(cr, profiles, partners, counts)
    _report_direction(cr, profiles, counts)
    forms = _forms_by_code(cr)
    texts = _profile_texts(cr, profiles)
    _retire_repro(cr, profiles, forms, texts, counts)
    _retire_loose(cr, profiles, forms, counts)
    _clear_retired_selection(cr)
    counts["renamed"] = _rename_supersacs(cr)
    _retire_templates(cr, forms, counts)
    _logger.info("material vocabulary %s counts: %s", MIGRATION, counts)
    return counts


def _columns(cr, table: str) -> set[str]:
    cr.execute(
        """
        SELECT column_name
          FROM information_schema.columns
         WHERE table_schema = current_schema()
           AND table_name = %s
        """,
        (table,),
    )
    return {row[0] for row in cr.fetchall()}


def _table_exists(cr, table: str) -> bool:
    cr.execute(
        """
        SELECT 1
          FROM information_schema.tables
         WHERE table_schema = current_schema()
           AND table_name = %s
        """,
        (table,),
    )
    return cr.fetchone() is not None


def _ensure_direction_column(cr) -> None:
    if "direction" in _columns(cr, "plasticos_material_profile"):
        return
    cr.execute("ALTER TABLE plasticos_material_profile ADD COLUMN direction VARCHAR")


def _ensure_review_table(cr) -> None:
    cr.execute(
        """
        CREATE TABLE IF NOT EXISTS plasticos_material_profile_migration_review (
            migration VARCHAR NOT NULL,
            profile_id INTEGER,
            reason VARCHAR NOT NULL,
            detail VARCHAR,
            UNIQUE (migration, reason, detail)
        )
        """
    )


def _review(cr, profile_id, reason: str, detail: str) -> None:
    cr.execute(
        """
        INSERT INTO plasticos_material_profile_migration_review (migration, profile_id, reason, detail)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT DO NOTHING
        """,
        (MIGRATION, profile_id, reason, detail),
    )


def _partner_facts(cr) -> dict:
    available = _columns(cr, "res_partner")
    if "id" not in available:
        return {}
    # Column names cannot be parameters. Each statement is a literal; the
    # facility-profile columns are read only when that module has added them.
    if {"erp_address_label", "company_role"} <= available:
        cr.execute(
            """
            SELECT id, parent_id, type, is_company, supplier_rank, customer_rank,
                   commercial_partner_id, erp_address_label, company_role
              FROM res_partner
            """
        )
    else:
        cr.execute(
            """
            SELECT id, parent_id, type, is_company, supplier_rank, customer_rank,
                   commercial_partner_id
              FROM res_partner
            """
        )
    columns = [desc[0] for desc in cr.description]
    return {row[0]: dict(zip(columns, row, strict=True)) for row in cr.fetchall()}


def _profiles(cr) -> list[dict]:
    cr.execute(
        """
        SELECT id, partner_id, polymer_id, form_id, material_grade_id,
               direction, freeform_notes, packaging_type_id
          FROM plasticos_material_profile
         ORDER BY id
        """
    )
    columns = [desc[0] for desc in cr.description]
    return [dict(zip(columns, row, strict=True)) for row in cr.fetchall()]


def _direction_of(row: dict, partners: dict) -> str | None:
    partner = partners.get(row.get("partner_id"))
    if not partner:
        return None
    site = is_site_shape(
        has_parent=bool(partner.get("parent_id")),
        partner_type=partner.get("type"),
        is_company=bool(partner.get("is_company")),
    )
    if site and partner.get("parent_id"):
        company = partners.get(partner.get("parent_id"), partner)
        company = partners.get(company.get("commercial_partner_id"), company)
    else:
        company = partners.get(partner.get("commercial_partner_id"), partner)
    return direction_for(
        site=site,
        partner_type=partner.get("type"),
        source_label=partner.get("erp_address_label"),
        company_role=partner.get("company_role"),
        supplier_rank=company.get("supplier_rank") or 0,
        customer_rank=company.get("customer_rank") or 0,
    )


def _assign_direction(cr, profiles: list[dict], partners: dict, counts: dict) -> None:
    for row in profiles:
        if row.get("direction"):
            continue
        decided = _direction_of(row, partners)
        row["direction"] = decided
        if not decided:
            continue
        cr.execute(
            """
            UPDATE plasticos_material_profile
               SET direction = %s
             WHERE id = %s
               AND direction IS NULL
            """,
            (decided, row["id"]),
        )
        counts["direction_set"] += cr.rowcount


def _report_direction(cr, profiles: list[dict], counts: dict) -> None:
    blanks = blank_direction_ids(profiles)
    counts["direction_blank"] = len(blanks)
    for profile_id in blanks:
        _review(cr, profile_id, "direction_blank", f"profile {profile_id} was left blank by the direction rule")
        _logger.warning("material profile %s has no direction; listed for review", profile_id)
    collisions = collision_groups(profiles)
    counts["direction_collisions"] = sum(len(ids) for ids in collisions.values())
    for ids in collisions.values():
        listed = ",".join(str(profile_id) for profile_id in ids)
        for profile_id in ids:
            detail = f"profile {profile_id} shares its direction key with {listed}"
            _review(cr, profile_id, "direction_collision", detail)
            _logger.warning("material profile %s collides on the direction key; left in place", profile_id)


def _forms_by_code(cr) -> dict[str, int]:
    if not _table_exists(cr, "plasticos_material_form"):
        return {}
    cr.execute("SELECT id, code FROM plasticos_material_form WHERE code IN ('REPRO', 'LOOSE', 'PELLETS')")
    return {code: form_id for form_id, code in cr.fetchall()}


def _profile_texts(cr, profiles: list[dict]) -> dict:
    texts: dict = {row["id"]: [row.get("freeform_notes") or ""] for row in profiles}
    for table in _LINE_TABLES:
        columns = _columns(cr, table) if _table_exists(cr, table) else set()
        if "material_profile_id" not in columns or "name" not in columns:
            continue
        _append_line_names(cr, table, texts)
    return texts


_LINE_SQL = {
    "purchase_order_line": """
        SELECT material_profile_id, name
          FROM purchase_order_line
         WHERE material_profile_id IS NOT NULL
           AND name IS NOT NULL
    """,
    "sale_order_line": """
        SELECT material_profile_id, name
          FROM sale_order_line
         WHERE material_profile_id IS NOT NULL
           AND name IS NOT NULL
    """,
    "account_move_line": """
        SELECT material_profile_id, name
          FROM account_move_line
         WHERE material_profile_id IS NOT NULL
           AND name IS NOT NULL
    """,
}


def _append_line_names(cr, table: str, texts: dict) -> None:
    """Read product-line names. The statement is a literal chosen from a fixed map."""
    statement = _LINE_SQL.get(table)
    if not statement:
        return
    cr.execute(statement)
    for profile_id, name in cr.fetchall():
        texts.setdefault(profile_id, []).append(name or "")


def _attribute_link(cr) -> tuple[str, str, str] | None:
    for table in _RELATION_CANDIDATES:
        if _table_exists(cr, table):
            columns = _columns(cr, table)
            profile_column = "plasticos_material_profile_id"
            attribute_column = "plasticos_material_attribute_id"
            if profile_column in columns and attribute_column in columns:
                return table, profile_column, attribute_column
    return None


_ATTRIBUTE_LINK_SQL = {
    "plasticos_material_attribute_plasticos_material_profile_rel": """
        INSERT INTO plasticos_material_attribute_plasticos_material_profile_rel (
            plasticos_material_profile_id, plasticos_material_attribute_id
        )
        SELECT %s, %s
         WHERE NOT EXISTS (
            SELECT 1
              FROM plasticos_material_attribute_plasticos_material_profile_rel
             WHERE plasticos_material_profile_id = %s
               AND plasticos_material_attribute_id = %s
         )
    """,
    "plasticos_material_profile_plasticos_material_attribute_rel": """
        INSERT INTO plasticos_material_profile_plasticos_material_attribute_rel (
            plasticos_material_profile_id, plasticos_material_attribute_id
        )
        SELECT %s, %s
         WHERE NOT EXISTS (
            SELECT 1
              FROM plasticos_material_profile_plasticos_material_attribute_rel
             WHERE plasticos_material_profile_id = %s
               AND plasticos_material_attribute_id = %s
         )
    """,
}


def _link_repro_attribute(cr, table: str, profile_id: int, attribute_id: int) -> None:
    """Attach attr_repro once. The statement is a literal chosen from a fixed map."""
    statement = _ATTRIBUTE_LINK_SQL.get(table)
    if not statement:
        return
    cr.execute(statement, (profile_id, attribute_id, profile_id, attribute_id))


def _attribute_id(cr, xml_name: str):
    if not _table_exists(cr, "ir_model_data"):
        return None
    cr.execute(
        """
        SELECT res_id
          FROM ir_model_data
         WHERE module = 'plasticos_material_profile'
           AND name = %s
        """,
        (xml_name,),
    )
    row = cr.fetchone()
    return row[0] if row else None


def _retire_repro(cr, profiles, forms, texts, counts) -> None:
    repro_id = forms.get("REPRO")
    pellets_id = forms.get("PELLETS")
    pellets, review = plan_repro(profiles, repro_id, texts)
    counts["repro_review"] = len(review)
    for profile_id in review:
        _review(cr, profile_id, "repro_review", f"profile {profile_id} stays on REPRO until pellets are confirmed")
        _logger.warning("material profile %s stays on REPRO for review", profile_id)
    if not pellets or not pellets_id:
        counts["repro_pellets"] = 0
        return
    attribute_id = _attribute_id(cr, "attr_repro")
    link = _attribute_link(cr)
    for profile_id in pellets:
        cr.execute(
            """
            UPDATE plasticos_material_profile
               SET form_id = %s,
                   form = 'PELLETS'
             WHERE id = %s
               AND form_id = %s
            """,
            (pellets_id, profile_id, repro_id),
        )
        updated = cr.rowcount
        counts["repro_pellets"] += updated
        if updated and attribute_id and link:
            _link_repro_attribute(cr, link[0], profile_id, attribute_id)
        if updated:
            for row in profiles:
                if row["id"] == profile_id:
                    row["form_id"] = pellets_id


def _packaging_loose_id(cr):
    if not _table_exists(cr, "plasticos_packaging_type"):
        return None
    cr.execute("SELECT id FROM plasticos_packaging_type WHERE code = 'loose' ORDER BY id LIMIT 1")
    row = cr.fetchone()
    return row[0] if row else None


def _retire_loose(cr, profiles, forms, counts) -> None:
    loose_id = forms.get("LOOSE")
    packaging_id = _packaging_loose_id(cr)
    clear, blocked = plan_loose(profiles, loose_id)
    counts["loose_blocked"] = len(blocked)
    for profile_id in blocked:
        _review(cr, profile_id, "loose_blocked", f"profile {profile_id} stays on LOOSE; clearing it would collide")
        _logger.warning("material profile %s stays on LOOSE; clearing the form would collide", profile_id)
    if packaging_id:
        for profile_id in clear + blocked:
            cr.execute(
                """
                UPDATE plasticos_material_profile
                   SET packaging_type_id = %s
                 WHERE id = %s
                   AND packaging_type_id IS NULL
                """,
                (packaging_id, profile_id),
            )
    for profile_id in clear:
        cr.execute(
            """
            UPDATE plasticos_material_profile
               SET form_id = NULL
             WHERE id = %s
               AND form_id = %s
            """,
            (profile_id, loose_id),
        )
        counts["loose_cleared"] += cr.rowcount


def _clear_retired_selection(cr) -> None:
    if "form" not in _columns(cr, "plasticos_material_profile"):
        return
    cr.execute("UPDATE plasticos_material_profile SET form = NULL WHERE form IN ('REPRO', 'LOOSE')")


def _rename_supersacs(cr) -> int:
    renamed = 0
    if _table_exists(cr, "plasticos_material_grade"):
        cr.execute(
            """
            UPDATE plasticos_material_grade
               SET name = 'Supersacs'
             WHERE code = 'SUPERACS'
               AND name IS DISTINCT FROM 'Supersacs'
            """
        )
        renamed += cr.rowcount
    if _table_exists(cr, "plasticos_packaging_type"):
        cr.execute(
            """
            UPDATE plasticos_packaging_type
               SET name = 'Supersacs'
             WHERE code = 'supersacks'
               AND name IS DISTINCT FROM 'Supersacs'
            """
        )
        renamed += cr.rowcount
    return renamed


def _retire_templates(cr, forms, counts) -> None:
    if not _table_exists(cr, "plasticos_grade_template"):
        return
    repro_id = forms.get("REPRO")
    pellets_id = forms.get("PELLETS")
    loose_id = forms.get("LOOSE")
    packaging_id = _packaging_loose_id(cr)
    if repro_id:
        cr.execute(
            """
            SELECT id, name, description
              FROM plasticos_grade_template
             WHERE form_id = %s
             ORDER BY id
            """,
            (repro_id,),
        )
        for template_id, name, description in cr.fetchall():
            if pellets_id and confirms_pellets(name, description):
                cr.execute(
                    """
                    UPDATE plasticos_grade_template
                       SET form_id = %s
                     WHERE id = %s
                       AND form_id = %s
                    """,
                    (pellets_id, template_id, repro_id),
                )
                counts["template_pellets"] += cr.rowcount
            else:
                counts["template_repro_review"] += 1
                _review(
                    cr,
                    None,
                    "template_repro_review",
                    f"grade template {template_id} stays on REPRO until pellets are confirmed",
                )
                _logger.warning("grade template %s stays on REPRO for review", template_id)
    if loose_id:
        if packaging_id:
            cr.execute(
                """
                UPDATE plasticos_grade_template
                   SET packaging_type_id = %s
                 WHERE form_id = %s
                   AND packaging_type_id IS NULL
                """,
                (packaging_id, loose_id),
            )
        cr.execute(
            """
            UPDATE plasticos_grade_template
               SET form_id = NULL
             WHERE form_id = %s
            """,
            (loose_id,),
        )
        counts["template_loose"] += cr.rowcount
