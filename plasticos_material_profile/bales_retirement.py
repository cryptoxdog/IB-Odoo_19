"""Retire Bales as a form: every Bales-form material profile ends with packaging Bales and no form.

Bales are packaging (``plasticos.packaging.type`` code ``bales``), not a form. Clearing
the form changes a profile's identity key, which is unique twice (NULLS NOT DISTINCT):

* ``(partner_id, polymer_id, form_id, material_grade_id) WHERE partner_id IS NOT NULL``
  (``plasticos_material_profile``), and
* ``(facility_profile_id, polymer_id, form_id, material_grade_id)
  WHERE partner_id IS NULL AND facility_profile_id IS NOT NULL`` (``plasticos_crm_bridge``).

The archived-row trap: both indexes count inactive rows, so archiving a duplicate cannot
clear its form. A Bales profile is therefore either *moved* (no other profile holds its
form-less key: the form is cleared and an empty packaging becomes Bales) or *merged*:

1. The survivor is the existing form-less profile with the same key; when only Bales
   profiles share the key, the lowest id is moved and becomes the survivor.
2. Empty survivor fields are filled from the Bales profile (stored, non-computed scalar
   and Many2one fields; booleans and numbers are skipped because the ORM cannot tell an
   unset value from ``False``/``0``). A set value is never overwritten. Packaging follows
   the same rule, with the Bales profile's packaging taken as Bales when empty; a different
   non-empty survivor packaging leaves the pair unresolved.
3. Every reference to the Bales profile is repointed to the survivor, in parameterized
   SQL: each stored Many2one column and Many2many relation column for
   ``plasticos.material.profile`` in the registry (a One2many is the inverse of one of
   those), plus chatter, attachments, activities and external ids. SQL reaches closed
   records whose ``write`` is frozen; database constraints still fail the pair.
4. With no reference left, the Bales profile is deleted (it duplicates the survivor).

Each move and merge runs in its own savepoint; a failure rolls that pair back, is logged
as unresolved with both ids, and the upgrade continues. Nothing here raises.
"""

import logging
from dataclasses import dataclass

_logger = logging.getLogger(__name__)

PROFILE_MODEL = "plasticos.material.profile"
MOVE = "move"
MERGE = "merge"
UNRESOLVED = "unresolved"
FORM_BALE = "plasticos_material_profile.form_bale"
PACKAGING_BALES = "plasticos_material_profile.packaging_bales"

# Never filled from the Bales profile: identity, owner, bookkeeping and the form itself.
FILL_SKIP = frozenset(
    {
        "id",
        "active",
        "create_uid",
        "create_date",
        "write_uid",
        "write_date",
        "display_name",
        "form_id",
        "form",
        "partner_id",
        "facility_profile_id",
        "polymer_id",
        "material_grade_id",
        "company_id",
    }
)
FILL_TYPES = frozenset({"char", "text", "html", "selection", "date", "datetime", "many2one"})
# Records that point at a profile through ``(model column, id column)`` rather than a Many2one.
GENERIC_REFERENCES = (
    ("mail_message", "model", "res_id"),
    ("ir_attachment", "res_model", "res_id"),
    ("mail_activity", "res_model", "res_id"),
    ("ir_model_data", "model", "res_id"),
)


def identity_owner(row):
    """The owner part of the unique key, or None when no index covers the row."""
    if row.get("partner_id"):
        return ("partner", row["partner_id"])
    if row.get("facility_profile_id"):
        return ("facility", row["facility_profile_id"])
    return None


def identity_key(row):
    owner = identity_owner(row)
    if owner is None:
        return None
    return (owner, row["polymer_id"], row.get("material_grade_id") or None)


def plan(bales_rows, formless_rows, packaging_id):
    """Return ordered actions for the Bales profiles.

    Rows are dicts with ``id``, ``partner_id``, ``facility_profile_id``, ``polymer_id``,
    ``material_grade_id`` and ``packaging_type_id``. Actions:

    * ``(MOVE, bales_id)``
    * ``(MERGE, bales_id, survivor_id)``
    * ``(UNRESOLVED, bales_id, survivor_id, reason)``

    A merge into a Bales survivor follows that survivor's move.
    """
    occupied = {}
    for row in sorted(formless_rows, key=lambda r: r["id"]):
        key = identity_key(row)
        if key is not None:
            occupied.setdefault(key, row)

    groups = {}
    actions = []
    for row in sorted(bales_rows, key=lambda r: r["id"]):
        key = identity_key(row)
        if key is None:
            actions.append((MOVE, row["id"]))  # no unique index covers an ownerless row
        else:
            groups.setdefault(key, []).append(row)

    for key in sorted(groups, key=lambda k: groups[k][0]["id"]):
        members = groups[key]
        survivor = occupied.get(key)
        if survivor is None:
            survivor, members = members[0], members[1:]
            actions.append((MOVE, survivor["id"]))
            survivor_packaging = survivor.get("packaging_type_id") or packaging_id
        else:
            survivor_packaging = survivor.get("packaging_type_id")
        for row in members:
            packaging = row.get("packaging_type_id") or packaging_id
            if survivor_packaging and survivor_packaging != packaging:
                actions.append(
                    (
                        UNRESOLVED,
                        row["id"],
                        survivor["id"],
                        f"packaging {packaging} differs from the survivor's packaging {survivor_packaging}",
                    )
                )
                continue
            survivor_packaging = survivor_packaging or packaging
            actions.append((MERGE, row["id"], survivor["id"]))
    return actions


def fill_values(field_names, survivor_vals, bales_vals):
    """Fields empty on the survivor and set on the Bales profile, with the Bales value."""
    filled = {}
    for name in field_names:
        if survivor_vals.get(name) in (None, False, "") and bales_vals.get(name) not in (None, False, ""):
            filled[name] = bales_vals[name]
    return filled


@dataclass
class Counts:
    moved: int = 0
    merged: int = 0
    unresolved: int = 0


def retire(ops, packaging_id):
    """Move or merge every Bales-form profile through ``ops``; return the counts. Never raises."""
    bales_rows, formless_rows = ops.rows()
    counts = Counts()
    failed_moves = set()
    for action in plan(bales_rows, formless_rows, packaging_id):
        kind, bales_id = action[0], action[1]
        if kind == UNRESOLVED:
            survivor_id, reason = action[2], action[3]
            counts.unresolved += 1
            _logger.warning(
                "Bales retirement: left material profile %s on the Bales form; it duplicates profile %s but %s.",
                bales_id,
                survivor_id,
                reason,
            )
            continue
        if kind == MOVE:
            try:
                with ops.savepoint():
                    ops.move(bales_id, packaging_id)
            except Exception as error:  # noqa: BLE001 - one row never aborts the upgrade
                ops.after_rollback()
                failed_moves.add(bales_id)
                counts.unresolved += 1
                _logger.warning(
                    "Bales retirement: could not clear the Bales form on material profile %s (%s); left unchanged.",
                    bales_id,
                    error,
                )
                continue
            counts.moved += 1
            continue
        survivor_id = action[2]
        if survivor_id in failed_moves:
            counts.unresolved += 1
            _logger.warning(
                "Bales retirement: left material profile %s on the Bales form; its survivor %s could not be moved.",
                bales_id,
                survivor_id,
            )
            continue
        try:
            with ops.savepoint():
                filled, repointed = ops.merge(bales_id, survivor_id, packaging_id)
        except Exception as error:  # noqa: BLE001 - one pair never aborts the upgrade
            ops.after_rollback()
            counts.unresolved += 1
            _logger.warning(
                "Bales retirement: rolled back the merge of material profile %s into %s (%s); both left unchanged.",
                bales_id,
                survivor_id,
                error,
            )
            continue
        counts.merged += 1
        for name, value in sorted(filled.items()):
            _logger.info("Bales retirement: profile %s took %s=%r from profile %s.", survivor_id, name, value, bales_id)
        _logger.info(
            "Bales retirement: merged material profile %s into %s (%s references repointed) and deleted %s.",
            bales_id,
            survivor_id,
            repointed,
            bales_id,
        )
    _logger.info(
        "Bales retirement: %s moved, %s merged, %s unresolved.", counts.moved, counts.merged, counts.unresolved
    )
    return counts


class RepointError(RuntimeError):
    """A reference to the Bales profile is still present after the repoint."""


class OdooOps:
    """``retire`` operations on a live Odoo environment."""

    def __init__(self, env, form):
        self.env = env
        self.form = form
        self.Profile = env[PROFILE_MODEL].with_context(active_test=False, tracking_disable=True, mail_notrack=True)

    def savepoint(self):
        return self.env.cr.savepoint()

    def after_rollback(self):
        self.env.invalidate_all(flush=False)

    def rows(self):
        has_facility = "facility_profile_id" in self.Profile._fields
        fields = ["partner_id", "polymer_id", "material_grade_id", "packaging_type_id", "form_id"]
        if has_facility:
            fields.append("facility_profile_id")
        bales_records = self.Profile.search_read([("form_id", "=", self.form.id)], fields)
        polymer_ids = sorted({values["polymer_id"][0] for values in bales_records if values["polymer_id"]})
        formless_records = (
            self.Profile.search_read([("form_id", "=", False), ("polymer_id", "in", polymer_ids)], fields)
            if polymer_ids
            else []
        )
        bales, formless = [], []
        for values in bales_records + formless_records:
            row = {"id": values["id"]}
            for name in fields:
                value = values.get(name)
                row[name] = value[0] if isinstance(value, (list, tuple)) else (value or None)
            (bales if row["form_id"] == self.form.id else formless).append(row)
        return bales, formless

    def move(self, profile_id, packaging_id):
        profile = self.Profile.browse(profile_id)
        vals = {"form_id": False}
        if not profile.packaging_type_id:
            vals["packaging_type_id"] = packaging_id
        profile.write(vals)

    def _fill_fields(self):
        return sorted(
            name
            for name, field in self.Profile._fields.items()
            if field.store
            and not field.compute
            and not field.related
            and field.type in FILL_TYPES
            and name not in FILL_SKIP
            and not name.startswith("message_")
        )

    def _references(self):
        """Stored Many2one columns and Many2many relation columns that hold a profile id.

        Yields ``(label, table, column, partner_column)``: ``partner_column`` is the other
        side of a Many2many relation (for de-duplication), None for a Many2one column.
        """
        seen = set()
        for model_name in self.env.registry:
            Model = self.env.registry[model_name]
            if Model._abstract or not Model._auto:
                continue
            for name, field in Model._fields.items():
                if not field.store or field.comodel_name != PROFILE_MODEL:
                    continue
                if field.type == "many2one":
                    target = (Model._table, name, None)
                elif field.type == "many2many":
                    target = (field.relation, field.column2, field.column1)
                else:
                    continue
                if target not in seen:
                    seen.add(target)
                    yield (f"{model_name}.{name}", *target)

    def _values(self, profile, names):
        return {
            name: (profile[name].id if profile._fields[name].type == "many2one" else profile[name]) for name in names
        }

    def merge(self, bales_id, survivor_id, packaging_id):
        """Fill, repoint and delete. Raises on any failure; ``retire`` rolls the savepoint back.

        References are repointed in SQL, not through ``write``: a merge corrects the
        identity of the referenced profile, so it must also reach closed offers and
        transactions whose ``write`` is frozen. Database constraints (unique indexes,
        foreign keys) still apply and fail the pair.
        """
        from odoo.tools import SQL  # noqa: PLC0415 - imported only inside Odoo

        bales = self.Profile.browse(bales_id)
        survivor = self.Profile.browse(survivor_id)
        names = self._fill_fields()
        bales_vals = self._values(bales, names)
        bales_vals["packaging_type_id"] = bales.packaging_type_id.id or packaging_id
        filled = fill_values(names, self._values(survivor, names), bales_vals)
        if filled:
            survivor.write(filled)
        self.env.flush_all()

        cr = self.env.cr
        repointed = 0
        references = list(self._references())
        for _label, table, column, partner_column in references:
            if partner_column:
                # A row that already links the survivor would become a duplicate pair.
                cr.execute(
                    SQL(
                        "DELETE FROM %(t)s AS b WHERE b.%(c)s = %(old)s AND EXISTS "
                        "(SELECT 1 FROM %(t)s AS s WHERE s.%(c)s = %(new)s AND s.%(p)s = b.%(p)s)",
                        t=SQL.identifier(table),
                        c=SQL.identifier(column),
                        p=SQL.identifier(partner_column),
                        old=bales_id,
                        new=survivor_id,
                    )
                )
                repointed += cr.rowcount
            cr.execute(
                SQL(
                    "UPDATE %s SET %s = %s WHERE %s = %s",
                    SQL.identifier(table),
                    SQL.identifier(column),
                    survivor_id,
                    SQL.identifier(column),
                    bales_id,
                )
            )
            repointed += cr.rowcount
        for table, model_column, id_column in GENERIC_REFERENCES:
            cr.execute(SQL("SELECT to_regclass(%s)", table))
            if not cr.fetchone()[0]:
                continue
            cr.execute(
                SQL(
                    "UPDATE %s SET %s = %s WHERE %s = %s AND %s = %s",
                    SQL.identifier(table),
                    SQL.identifier(id_column),
                    survivor_id,
                    SQL.identifier(model_column),
                    PROFILE_MODEL,
                    SQL.identifier(id_column),
                    bales_id,
                )
            )
            repointed += cr.rowcount
        self.env.invalidate_all()

        for label, table, column, _partner_column in references:
            cr.execute(
                SQL(
                    "SELECT 1 FROM %s WHERE %s = %s LIMIT 1",
                    SQL.identifier(table),
                    SQL.identifier(column),
                    bales_id,
                )
            )
            if cr.fetchone():
                raise RepointError(f"{label} still references profile {bales_id}")
        bales.unlink()
        return filled, repointed


def retire_bales_form(env):
    """Archive the Bales form and retire every Bales-form profile. Returns the counts, or None."""
    form = env.ref(FORM_BALE, raise_if_not_found=False)
    packaging = env.ref(PACKAGING_BALES, raise_if_not_found=False)
    if not form or not packaging:
        _logger.warning("Bales retirement skipped: the Bales form or the Bales packaging is missing.")
        return None
    form = form.with_context(active_test=False)
    counts = retire(OdooOps(env, form), packaging.id)
    if form.active:
        form.write({"active": False})
    env.flush_all()
    return counts
