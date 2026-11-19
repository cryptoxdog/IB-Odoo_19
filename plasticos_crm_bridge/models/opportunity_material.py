"""Opportunity-owned material copy.

Copied once from the linked material profile. Later edits stay on this row.
They never write ``plasticos.material.profile`` or its image attachments.
This copy is the broker's working sheet and the material authority of the
pursuit: Gate matching freezes it into an approved lot when matching starts,
and manual offers and the release read it. A frozen lot never changes after
a later edit here; the next match freezes the edited sheet as a new lot.
"""

from __future__ import annotations

import math
import re

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

SUPPLIER_OFFER_OPTIONAL = "plasticos_supplier_offer_optional"

PROFILE_MODEL = "plasticos.material.profile"
RELATION_FIELDS = (
    "polymer_id",
    "material_grade_id",
    "form_id",
    "packaging_type_id",
    "source_type_id",
    "filler_type_id",
)
SCALAR_FIELDS = (
    "melt_flow_index",
    "density",
    "moisture_percent",
    "contamination_percent",
    "filler_pct",
    "quantity_per_load_lbs",
    "loads_per_month",
    "lat",
    "lon",
    "origin_process_type",
)
LINE_SPEC_FIELDS = (
    "material_grade_id",
    "form_id",
    "packaging_type_id",
    "source_type_id",
    "filler_type_id",
)
_SPEC_NOTE_HEADING = "Web-lead specification"
_SPEC_NOTE_END = "End web-lead specification"
_SPEC_NUMBER = re.compile(r"\d+(?:\.\d+)?|\.\d+")
_GENERATED_SPEC_LINE = re.compile(r"^(?:Representation|[A-Za-z][^:\n]{0,40}):\s+\S")
_FINDING_SKIPPED = frozenset({"source_id", "source_ref", "content", "content_type", "content_sha256"})
_FIELD_ALIASES = {
    "melt_flow_index": ("melt flow index", "melt flow rate", "melt flow", "melt index", "mfi", "mfr"),
    "density": ("specific gravity", "density"),
    "moisture_percent": ("moisture content", "moisture"),
}
_PROPERTY_FIELDS = {}
for _name, _field in (
    ("mfi", "melt_flow_index"),
    ("melt flow", "melt_flow_index"),
    ("melt flow index", "melt_flow_index"),
    ("melt index", "melt_flow_index"),
    ("melt flow rate", "melt_flow_index"),
    ("mfr", "melt_flow_index"),
    ("density", "density"),
    ("specific gravity", "density"),
    ("moisture", "moisture_percent"),
    ("moisture content", "moisture_percent"),
    ("moisture percent", "moisture_percent"),
):
    _PROPERTY_FIELDS[_name] = _field
_COLUMN_UNITS = {
    "melt_flow_index": frozenset({"g/10min", "dg/min"}),
    "density": frozenset({"g/cm3", "g/cm³", "g/cm^3", "g/cc", "g/ml"}),
    "moisture_percent": frozenset({"%", "percent", "pct", "wt%", "wt.%"}),
}


def _unit_key(unit):
    return re.sub(r"\s+", "", str(unit or "").strip().lower()).rstrip(".")


def _property_field(name):
    key = re.sub(r"[^a-z0-9]+", " ", str(name or "").lower()).strip()
    return _PROPERTY_FIELDS.get(key)


def _spec_number(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        number = float(value)
    else:
        text = str(value or "").strip().replace(",", "")
        if not _SPEC_NUMBER.fullmatch(text):
            return None
        number = float(text)
    if not math.isfinite(number) or number <= 0:
        return None
    return number


def _condition_key(value):
    return " ".join(str(value or "").casefold().split())


def _number_in_text(text, value):
    forms = {f"{value:g}", str(value)}
    if value == int(value):
        forms.add(str(int(value)))
    for form in forms:
        if re.search(rf"(?<![\d.]){re.escape(form)}(?![\d.])", text):
            return True
    return False


def _text_substantiates(text, row):
    """The cited text states this property, this number, and this unit."""
    haystack = str(text or "").casefold()
    field = _property_field(row.get("property"))
    aliases = _FIELD_ALIASES.get(field, ())
    if not any(alias and alias in haystack for alias in aliases):
        return False
    number = _spec_number(row.get("value"))
    if number is None or not _number_in_text(haystack, number):
        return False
    unit = _unit_key(row.get("unit"))
    return bool(unit) and unit in re.sub(r"\s+", "", haystack)


def _finding_text(photo):
    return "\n".join(
        str(value) for key, value in photo.items() if key not in _FINDING_SKIPPED and isinstance(value, str)
    )


def _citation_text(ref, bundle):
    text = str(ref or "").strip()
    evidence = bundle if isinstance(bundle, dict) else {}
    if not text:
        return ""
    if text.startswith("seller."):
        seller = evidence.get("seller") if isinstance(evidence.get("seller"), dict) else {}
        value = seller.get(text.split(".", 1)[1])
        return value.strip() if isinstance(value, str) else ""
    photos = evidence.get("photo_findings") if isinstance(evidence.get("photo_findings"), list) else []
    if text.startswith("vision."):
        suffix = text.split(".", 1)[1]
        if suffix.isdigit() and 0 <= int(suffix) < len(photos) and isinstance(photos[int(suffix)], dict):
            return _finding_text(photos[int(suffix)])
        return ""
    pdf_doc_page = re.fullmatch(r"pdf\.(\d+)\.page\.(\d+)", text)
    if pdf_doc_page:
        # Document-scoped citations resolve through the stored coordinates:
        # exactly one admitted page of the named document and page number.
        pages = evidence.get("pdf_page_text") if isinstance(evidence.get("pdf_page_text"), list) else []
        sources = evidence.get("pdf_page_sources") if isinstance(evidence.get("pdf_page_sources"), list) else []
        document = f"pdf.{int(pdf_doc_page.group(1))}"
        page_number = int(pdf_doc_page.group(2))
        for index, source in enumerate(sources):
            if not isinstance(source, dict):
                continue
            if str(source.get("source_ref") or "") == document and source.get("page_number") == page_number:
                if 0 <= index < len(pages):
                    return str(pages[index] or "").strip()
                return ""
        return ""
    if text.startswith("pdf.page."):
        # Legacy flat citations keep their original meaning: a position in the
        # admitted page list of the bundle that minted them.
        pages = evidence.get("pdf_page_text") if isinstance(evidence.get("pdf_page_text"), list) else []
        suffix = text.rsplit(".", 1)[-1]
        if suffix.isdigit() and 0 <= int(suffix) < len(pages):
            return str(pages[int(suffix)] or "").strip()
        return ""
    for photo in photos:
        if isinstance(photo, dict) and text in {photo.get("source_id"), photo.get("source_ref")}:
            return _finding_text(photo)
    return ""


def _ref_resolves(ref, bundle, row):
    """The cited seller text, photo finding, or PDF page states this spec."""
    return _text_substantiates(_citation_text(ref, bundle), row)


def _row_is_cited(row, bundle):
    refs = row.get("source_refs")
    if isinstance(refs, str):
        refs = [refs]
    if not isinstance(refs, (list, tuple)):
        return False
    return any(_ref_resolves(ref, bundle, row) for ref in refs)


def _column_updates(rows, bundle=None):
    """One substantiated number per column. Two values promote neither."""
    grouped = {name: [] for name in _COLUMN_UNITS}
    seen = {name: set() for name in _COLUMN_UNITS}
    for row in rows:
        if not isinstance(row, dict):
            continue
        field = _property_field(row.get("property"))
        number = _spec_number(row.get("value"))
        if field is None or number is None:
            continue
        seen[field].add(number)
        if not _row_is_cited(row, bundle) or _unit_key(row.get("unit")) not in _COLUMN_UNITS[field]:
            continue
        grouped[field].append((number, _condition_key(row.get("test_conditions"))))
    updates = {}
    for field, samples in grouped.items():
        if len(seen[field]) != 1 or not samples:
            continue
        numbers = {number for number, _condition in samples}
        conditions = {condition for _number, condition in samples}
        if numbers == seen[field] and len(conditions) == 1:
            updates[field] = samples[0][0]
    return updates


def _note_refs(value):
    if isinstance(value, str):
        refs = [value]
    elif isinstance(value, (list, tuple)):
        refs = value
    else:
        return ""
    return ", ".join(str(ref).strip() for ref in refs if str(ref).strip())


def _note_value(value):
    if value is None or isinstance(value, bool):
        return ""
    if isinstance(value, (int, float, str)):
        return " ".join(str(value).split())
    return ""


def _specification_note(rows, representation):
    lines = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        label = str(row.get("property") or "Specification").strip() or "Specification"
        detail = " ".join(
            part
            for part in (
                _note_value(row.get("value")),
                str(row.get("unit") or "").strip(),
                str(row.get("test_conditions") or "").strip(),
                _note_refs(row.get("source_refs")),
                _note_refs(row.get("conflicts")),
            )
            if part
        )
        if detail:
            lines.append(f"{label}: {detail}")
    if representation:
        lines.append(f"Representation: {representation}")
    if not lines:
        return ""
    return "\n".join([_SPEC_NOTE_HEADING, *lines, _SPEC_NOTE_END])


def _generated_block_end(text, start):
    marker = text.find(_SPEC_NOTE_END, start)
    if marker >= 0:
        return marker + len(_SPEC_NOTE_END)
    pos = start + len(_SPEC_NOTE_HEADING)
    if pos < len(text) and text[pos] == "\n":
        pos += 1
    while pos < len(text):
        newline = text.find("\n", pos)
        line_end = len(text) if newline < 0 else newline
        if not _GENERATED_SPEC_LINE.match(text[pos:line_end].strip()):
            break
        pos = len(text) if newline < 0 else newline + 1
    return pos


def _specification_block(text):
    start = text.find(_SPEC_NOTE_HEADING)
    if start < 0:
        return ""
    end = text.find(_SPEC_NOTE_END, start)
    if end >= 0:
        return text[start:end]
    return text[start : _generated_block_end(text, start)]


def _owned_column_numbers(notes):
    """Numbers the previous generated block recorded for this web lead."""
    owned = {}
    for line in _specification_block(notes or "").splitlines():
        if ":" not in line:
            continue
        label, rest = line.split(":", 1)
        field = _property_field(label)
        token = rest.strip().split(" ", 1)[0] if rest.strip() else ""
        number = _spec_number(token)
        if field and number is not None and field not in owned:
            owned[field] = number
    return owned


def _replace_specification_note(existing, note):
    """Replace only the bounded web-lead specification block. Text after it stays."""
    text = existing or ""
    start = text.find(_SPEC_NOTE_HEADING)
    if start < 0:
        if not note:
            return text
        return f"{text.rstrip()}\n{note}".strip() if text.strip() else note
    prefix = text[:start].rstrip()
    suffix = text[_generated_block_end(text, start) :].strip()
    parts = [part for part in (prefix, (note or "").strip(), suffix) if part]
    return "\n".join(parts)


_CLAIMED_COLUMNS = frozenset({"melt_flow_index", "density", "moisture_percent", "quantity_per_load_lbs"})


def _claimed_specification(vals):
    return bool(_CLAIMED_COLUMNS & set(vals))


def _finite_positive(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        return None
    return number


ORIGIN_PROCESS_SELECTION = [
    ("blow_mold", "Blow Molding"),
    ("compounding", "Compounding"),
    ("compression_mold", "Compression Molding"),
    ("extrusion", "Extrusion"),
    ("film_blown", "Film Blown"),
    ("film_cast", "Film Cast"),
    ("injection", "Injection Molding"),
    ("other", "Other"),
    ("rotomold", "Rotational Molding"),
    ("thermoform", "Thermoforming"),
]


class PlasticosOpportunityMaterial(models.Model):
    _name = "plasticos.opportunity.material"
    _description = "Opportunity Material Copy"
    _order = "id desc"
    _rec_name = "display_name"

    _unique_opportunity_material = models.UniqueIndex("(opportunity_id)")
    _check_buy_price_non_negative = models.Constraint(
        "check(buy_price_per_lb >= 0)",
        "Offer price cannot be negative.",
    )

    display_name = fields.Char(compute="_compute_display_name", store=True)
    opportunity_id = fields.Many2one(
        "crm.lead",
        string="Opportunity",
        required=True,
        index=True,
        ondelete="cascade",
        help="Native opportunity that owns this material copy.",
    )
    source_profile_id = fields.Many2one(
        PROFILE_MODEL,
        string="Source Profile",
        readonly=True,
        ondelete="set null",
        help="Profile this copy was taken from. Edits here do not write that profile.",
    )
    source_web_lead_id = fields.Many2one(
        "plasticos.web.lead",
        string="Source Web Lead",
        index=True,
        ondelete="set null",
        help="This row's numerical specifications belong to that lead.",
    )
    polymer_id = fields.Many2one(
        "plasticos.polymer",
        string="Polymer",
        index=True,
        ondelete="restrict",
        help="Polymer on this opportunity's own material copy.",
    )
    material_grade_id = fields.Many2one(
        "plasticos.material.grade",
        string="Material Type",
        index=True,
        ondelete="restrict",
        help="Material type on this opportunity's own material copy.",
    )
    form_id = fields.Many2one(
        "plasticos.material.form",
        string="Form",
        index=True,
        ondelete="restrict",
        help="Form on this opportunity's own material copy.",
    )
    color_ids = fields.Many2many(
        "plasticos.material.color",
        "plasticos_opportunity_material_color_rel",
        "material_id",
        "color_id",
        string="Color",
        help="Every color on this opportunity's own material copy.",
    )
    packaging_type_id = fields.Many2one(
        "plasticos.packaging.type",
        string="Packaging",
        ondelete="restrict",
        help="Packaging on this opportunity's own material copy.",
    )
    source_type_id = fields.Many2one(
        "plasticos.source.type",
        string="Source",
        ondelete="restrict",
        help="Source on this opportunity's own material copy.",
    )
    filler_type_id = fields.Many2one(
        "plasticos.filler.type",
        string="Filler",
        ondelete="restrict",
        help="Filler on this opportunity's own material copy.",
    )
    material_attribute_ids = fields.Many2many(
        "plasticos.material.attribute",
        "plasticos_opportunity_material_attribute_rel",
        "material_id",
        "attribute_id",
        string="Attributes",
        help="Attributes on this opportunity's own material copy.",
    )
    melt_flow_index = fields.Float(string="MFI", help="Melt flow index copied onto the opportunity.")
    density = fields.Float(help="Density copied onto the opportunity.")
    moisture_percent = fields.Float(help="Moisture percent copied onto the opportunity.")
    contamination_percent = fields.Float(help="Contamination percent copied onto the opportunity.")
    filler_pct = fields.Float(string="Filler %", help="Filler percent copied onto the opportunity.")
    quantity_per_load_lbs = fields.Float(
        string="Quantity per Load (lbs)", help="Supply quantity copied onto the opportunity."
    )
    buy_price_per_lb = fields.Float(
        string="Offer Price",
        digits=(10, 4),
        help="Supplier price per pound for this pursuit. The material profile does not store it.",
    )
    loads_per_month = fields.Integer(string="Loads per Month", help="Monthly loads copied onto the opportunity.")
    lat = fields.Float(string="Latitude", digits=(10, 7), help="Latitude copied onto the opportunity.")
    lon = fields.Float(string="Longitude", digits=(10, 7), help="Longitude copied onto the opportunity.")
    origin_process_type = fields.Selection(
        ORIGIN_PROCESS_SELECTION,
        string="Origin Process",
        help="Origin process copied onto the opportunity.",
    )
    freeform_notes = fields.Text(help="Notes copied onto the opportunity. Edits stay on this copy.")
    image_attachment_ids = fields.Many2many(
        "ir.attachment",
        "plasticos_opportunity_material_image_rel",
        "material_id",
        "attachment_id",
        string="Pictures",
        help="Pictures owned by this opportunity. They are copies, not the profile's attachments.",
    )

    @api.depends("polymer_id", "material_grade_id", "form_id")
    def _compute_display_name(self):
        for rec in self:
            parts = [rec.polymer_id.name, rec.material_grade_id.name, rec.form_id.name]
            name = " ".join(part for part in parts if part)
            rec.display_name = name or _("Opportunity material")

    @api.model
    def _vals_from_profile(self, profile, opportunity):
        """Specification and weight for one new line. The profile has no price to copy."""
        profile.ensure_one()
        vals = {
            "source_profile_id": profile.id,
            "freeform_notes": profile.freeform_notes or False,
            "material_attribute_ids": [(6, 0, profile.material_attribute_ids.ids)],
            "color_ids": [(6, 0, profile.color_ids.ids)],
        }
        for name in RELATION_FIELDS:
            related = profile[name]
            vals[name] = related.id if related else False
        for name in SCALAR_FIELDS:
            vals[name] = profile[name]
        intake = opportunity.source_intake_id[:1] if opportunity else self.env["plasticos.intake"]
        from odoo.addons.plasticos_intake.source_origin import downstream_coordinates

        lat, lon = downstream_coordinates(
            profile.lat,
            profile.lon,
            intake.lat if intake else 0.0,
            intake.lon if intake else 0.0,
        )
        vals["lat"] = lat
        vals["lon"] = lon
        return vals

    @api.model
    def copy_from_profile(self, opportunity, profile):
        """Copy ``profile`` onto ``opportunity`` once. Never writes the profile."""
        opportunity.ensure_one()
        profile.ensure_one()
        if opportunity.opportunity_material_ids:
            return opportunity.opportunity_material_ids[:1]
        vals = self._vals_from_profile(profile, opportunity)
        vals["opportunity_id"] = opportunity.id
        material = self.with_context(**{SUPPLIER_OFFER_OPTIONAL: True}).create(vals)
        intake = opportunity.source_intake_id
        if intake:
            address = {}
            if not opportunity.street and intake.source_street:
                address["street"] = intake.source_street
            if not opportunity.city and intake.source_city:
                address["city"] = intake.source_city
            if not opportunity.zip and intake.source_zip:
                address["zip"] = intake.source_zip
            if address:
                opportunity.write(address)
        return material

    def apply_web_lead_specification(self, specifications, representation, grounded_lbs, bundle=None, web_lead=None):
        """Write a substantiated spec into an empty column and replace this block.

        The cited text must state the property, the number, and the unit. Two
        values for one property fill no column. An existing number is replaced
        only when this web lead's previous block recorded that number and the
        new evidence is a substantiated correction. A human-entered value stays.
        The first lead that writes a substantiated column owns the row. Another
        linked lead leaves the columns and the note unchanged. Replay replaces
        only the bounded note. Planning weight is not written into
        ``quantity_per_load_lbs``.
        """
        self.ensure_one()
        caller = web_lead[:1] if web_lead else self.env["plasticos.web.lead"]
        if self.source_web_lead_id and caller and self.source_web_lead_id != caller:
            return
        rows = [row for row in specifications or [] if isinstance(row, dict)]
        owned = _owned_column_numbers(self.freeform_notes or "")
        vals = {}
        for field_name, number in _column_updates(rows, bundle).items():
            current = _spec_number(self[field_name])
            previous = owned.get(field_name)
            if current is None:
                vals[field_name] = number
            elif previous is not None and math.isclose(current, previous) and not math.isclose(current, number):
                vals[field_name] = number
        grounded = _finite_positive(grounded_lbs)
        if grounded and not self.quantity_per_load_lbs:
            vals["quantity_per_load_lbs"] = grounded
        note = _specification_note(rows, representation)
        replaced = _replace_specification_note(self.freeform_notes or "", note)
        if replaced != (self.freeform_notes or ""):
            vals["freeform_notes"] = replaced or False
        if caller and not self.source_web_lead_id and _claimed_specification(vals):
            vals["source_web_lead_id"] = caller.id
        if vals:
            self.with_context(**{SUPPLIER_OFFER_OPTIONAL: True}).write(vals)

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for record, vals in zip(records, vals_list, strict=True):
            if record.source_profile_id and "image_attachment_ids" not in vals:
                record._copy_profile_images(record.source_profile_id)
        records._plasticos_sync_expected_revenue()
        return records

    def write(self, vals):
        res = super().write(vals)
        if {"buy_price_per_lb", "quantity_per_load_lbs"} & set(vals):
            self._plasticos_sync_expected_revenue()
        return res

    def _plasticos_sync_expected_revenue(self):
        """One load's weight times the supplier price. Monthly volume is not revenue."""
        for material in self:
            opportunity = material.opportunity_id
            if not opportunity:
                continue
            revenue = (material.quantity_per_load_lbs or 0.0) * (material.buy_price_per_lb or 0.0)
            if opportunity.expected_revenue != revenue:
                opportunity.expected_revenue = revenue

    @api.constrains("buy_price_per_lb", "opportunity_id")
    def _require_positive_offer_when_profile_backed(self):
        if self.env.context.get(SUPPLIER_OFFER_OPTIONAL):
            return
        for material in self:
            if material.opportunity_id.material_profile_id and material.buy_price_per_lb <= 0:
                raise ValidationError(_("Enter the supplier offer price before saving this opportunity."))

    def _copy_profile_images(self, profile):
        """Duplicate image attachments. The new rows are not the profile's files."""
        self.ensure_one()
        images = self.env["ir.attachment"].search(
            [
                ("res_model", "=", PROFILE_MODEL),
                ("res_id", "=", profile.id),
                ("mimetype", "like", "image/"),
            ]
        )
        copied = self.env["ir.attachment"]
        for image in images:
            copied |= image.copy(
                {
                    "res_model": self._name,
                    "res_id": self.id,
                    "res_field": False,
                }
            )
        if copied:
            self.image_attachment_ids = [(6, 0, copied.ids)]

    def _sell_product(self):
        """Product variant of this copy's polymer. Does not read the live profile."""
        self.ensure_one()
        polymer = self.polymer_id
        if not polymer:
            raise UserError(_("The opportunity material copy has no polymer to sell."))
        template = polymer._purchase_product()
        product = template.product_variant_id
        if not product:
            raise UserError(_("Polymer %s has no sellable product variant.") % polymer.name)
        return product

    def _line_specification(self, line_model):
        """Order-line specification values. ``material_profile_id`` is left empty."""
        self.ensure_one()
        present = self.env[line_model]._fields
        vals = {}
        for name in LINE_SPEC_FIELDS:
            if name not in present:
                continue
            related = self[name]
            vals[name] = related.id if related else False
        if "material_attribute_ids" in present:
            vals["material_attribute_ids"] = [(6, 0, self.material_attribute_ids.ids)]
        if "color_ids" in present:
            vals["color_ids"] = [(6, 0, self.color_ids.ids)]
        return vals
