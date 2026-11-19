import importlib

from odoo import SUPERUSER_ID, fields, models

Markup = importlib.import_module("markupsafe").Markup

# The copy below is the real propagation. Bridge tests wait on this flag.
SPEC_PROPAGATION = True
_SPEC_MARKER = 'data-plasticos-spec="1"'
_PDF_MARKER = 'data-plasticos-pdf="1"'
_MAX_SPEC_ROWS = 40
_MAX_PDF_PAGES = 12
_MAX_PAGE_CHARS = 1500
_MAX_PDF_CHARS = 6000


class PlasticosWebLeadCRM(models.Model):
    _inherit = "plasticos.web.lead"
    SPEC_PROPAGATION = SPEC_PROPAGATION

    crm_lead_id = fields.Many2one(
        "crm.lead",
        string="CRM Lead",
        index=True,
        ondelete="set null",
    )
    opportunity_user_id = fields.Many2one(
        "res.users",
        string="Opportunity Salesperson",
        related="crm_lead_id.user_id",
        readonly=False,
        ondelete="set null",
        domain=[("share", "=", False)],
        help="Salesperson on the opportunity. This is the commercial owner after the opportunity exists.",
    )

    def write(self, vals):
        """Apply an opportunity salesperson edit before the processed-lead guard.

        The queue field stays untouched. The stored salesperson is ``crm.lead.user_id``.
        """
        opportunity_user_set = "opportunity_user_id" in vals
        opportunity_user_id = vals.pop("opportunity_user_id", False) if opportunity_user_set else False
        result = super().write(vals)
        if opportunity_user_set:
            opportunities = self.mapped("crm_lead_id")
            if opportunities:
                opportunities.write({"user_id": opportunity_user_id})
        return result

    def _create_crm_lead(self):
        """Called after HOT classification — creates one native crm.lead opportunity.

        HOT is a triage signal, not broker approval: the opportunity starts in
        the seeded non-Won ``New`` stage and never creates a partner. It inherits
        the web lead queue assignee when one was chosen, and stays unassigned
        otherwise. Submitted facts are copied as-is; estimates are labelled.

        The material_profile_id from the linked intake is propagated to the
        crm.lead so brokers can see the normalised material specification
        without navigating to the intake record.

        env.uid fix: the public webhook endpoint uses auth="none" which leaves
        env.uid=None even after sudo(). message_post calls env.user._is_public()
        which requires a singleton. We bind a known uid (SUPERUSER_ID) for all
        mail-thread calls so the author is unambiguous. The crm.lead itself inherits
        the queue assignee. The webhook technical user is never the salesperson.

        HOT creates this opportunity. It does not create an offer.
        """
        self.ensure_one()
        actor = self.with_user(SUPERUSER_ID)
        if self.crm_lead_id:
            actor._propagate_one_pass_spec(self.crm_lead_id)
            return self.crm_lead_id

        ref = self.env.ref
        source = self.lead_source_id or ref("plasticos_crm_bridge.utm_source_web_lead", raise_if_not_found=False)
        stage = ref("crm.stage_lead1", raise_if_not_found=False)

        vals = {
            "name": " — ".join(filter(None, [self.company_name, self.material_description])) or "Web Lead",
            "partner_name": self.company_name,
            "contact_name": self.contact_name,
            "email_from": self.contact_email,
            "phone": self.contact_phone,
            "description": self._crm_opportunity_description(),
            "source_id": source.id if source else False,
            "type": "opportunity",
            "stage_id": stage.id if stage else False,
            # Queue assignee when an operator already chose one. Never the webhook user.
            "user_id": self.assigned_user_id.id or False,
            # Only an already-linked partner is kept; none is created here.
            "partner_id": self.partner_id.id if self.partner_id else False,
            "source_intake_id": self.intake_id.id if self.intake_id else False,
            # HOT is eligibility: the material profile is carried only when the
            # intake already qualified one. Partner stays unlinked until verified.
            "material_profile_id": self.intake_id.material_profile_id.id
            if self.intake_id and self.intake_id.material_profile_id
            else False,
        }

        # auth="none" leaves env.uid empty after sudo(). Lead creation, image
        # sync, and the opportunity note all reach mail.thread, which calls
        # env.user._is_public() and requires a singleton res.users. Bind that
        # sequence to SUPERUSER_ID. The opportunity salesperson is the inherited
        # queue assignee, or nobody.
        lead = actor.env["crm.lead"].create(vals)
        actor.crm_lead_id = lead
        synchronize_images = getattr(lead, "_propagate_available_commercial_images", None)
        if callable(synchronize_images):
            synchronize_images()
        actor.message_post(body=Markup("CRM opportunity created: %s") % lead.name)
        actor._propagate_one_pass_spec(lead)
        return lead

    def _propagate_one_pass_spec(self, opportunity):
        """Copy one-pass specs, PDF text, and the original PDF onto an existing opportunity.

        A planning weight is not a load quantity. A numerical sheet column is written
        only for a supported unit and a resolvable evidence ref. Replay replaces the
        previous specification block from this lead with the corrected records.
        """
        self.ensure_one()
        if not opportunity:
            return
        bundle = self.evidence_bundle if isinstance(self.evidence_bundle, dict) else {}
        rows = _spec_rows(bundle)
        pages = _pdf_pages(bundle)
        representation = _representation_text(bundle.get("representation_alignment"))
        _append_marked_html(opportunity, _SPEC_MARKER, _spec_html(rows, representation))
        _append_marked_html(opportunity, _PDF_MARKER, _pdf_html(pages))
        copy_pdfs = getattr(opportunity, "_plasticos_copy_web_lead_pdfs", None)
        if callable(copy_pdfs):
            copy_pdfs()
        material = opportunity.opportunity_material_ids[:1]
        if not material and rows:
            material = _spec_sheet(opportunity)
        if not material:
            return
        grounded = _seller_grounded_load_lbs(bundle)
        material.apply_web_lead_specification(rows, representation, grounded, bundle)

    def _crm_opportunity_description(self):
        """HTML-escaped summary of submitted facts; computed estimates are labelled, empty values omitted."""
        self.ensure_one()
        payload = self.canonical_payload or {}
        pickup = " ".join(filter(None, [payload.get("pickup_location_text"), payload.get("pickup_postal_code")]))
        rows = [
            ("Material (submitted)", self.material_description),
            ("Quantity (submitted)", payload.get("quantity_text")),
            ("Weight per load (submitted)", payload.get("weight_per_load_text")),
            ("Frequency (submitted)", payload.get("frequency_text") or self.frequency),
            ("Contaminants (submitted)", payload.get("contaminants_text") or self.contaminant_notes),
            ("Pickup location (submitted)", pickup),
            ("Est. lbs per load (computed)", self.estimated_lbs_per_load or None),
            ("Est. loads per month (computed)", self.estimated_loads_per_month or None),
        ]
        items = [Markup("<li><b>%s:</b> %s</li>") % (label, value) for label, value in rows if value]
        return Markup("<ul>%s</ul>") % Markup("").join(items) if items else False


def _spec_sheet(opportunity):
    """One working sheet so a cited specification has a column to land on."""
    from .opportunity_material import SUPPLIER_OFFER_OPTIONAL

    return (
        opportunity.env["plasticos.opportunity.material"]
        .with_context(**{SUPPLIER_OFFER_OPTIONAL: True})
        .create({"opportunity_id": opportunity.id})
    )


def _replace_marked_block(current, marker, block):
    """Replace the previous block that carries this marker. The first copy is not frozen."""
    token = f"<div {marker}>"
    start = current.find(token)
    if start < 0:
        if not block:
            return current
        return f"{current}{block}" if current else block
    end = current.find("</div>", start)
    tail = "" if end < 0 else current[end + len("</div>") :]
    head = current[:start]
    if not block:
        return f"{head}{tail}"
    return f"{head}{block}{tail}"


def _append_marked_html(opportunity, marker, block):
    current = str(opportunity.description or "")
    updated = _replace_marked_block(current, marker, str(block or ""))
    if updated != current:
        opportunity.description = Markup(updated) if updated else False


def _spec_rows(bundle):
    rows = bundle.get("document_specifications")
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, dict)]


def _spec_html(rows, representation):
    shown = rows[:_MAX_SPEC_ROWS]
    items = []
    for row in shown:
        label, detail = _spec_pair(row)
        if detail:
            items.append(Markup("<li><b>%s:</b> %s</li>") % (label, detail))
    if representation:
        items.append(Markup("<li><b>%s:</b> %s</li>") % ("Representation", representation))
    omitted = len(rows) - len(shown)
    if omitted:
        items.append(Markup("<li>%s</li>") % f"{omitted} further specification rows remain on the web lead.")
    if not items:
        return Markup("")
    return Markup('<div data-plasticos-spec="1"><ul>%s</ul></div>') % Markup("").join(items)


def _pdf_html(pages):
    items = []
    used = 0
    shown = 0
    for page in pages:
        if used >= _MAX_PDF_CHARS:
            break
        text = _bounded(page.get("text"), min(_MAX_PAGE_CHARS, _MAX_PDF_CHARS - used))
        if not text:
            continue
        used += len(text)
        shown += 1
        label = page.get("label") or "PDF text"
        items.append(Markup("<li><b>%s:</b> %s</li>") % (label, text))
    remaining = len(pages) - shown
    if remaining:
        items.append(Markup("<li>%s</li>") % f"{remaining} further PDF pages remain on the attached PDF.")
    if not items:
        return Markup("")
    return Markup('<div data-plasticos-pdf="1"><ul>%s</ul></div>') % Markup("").join(items)


def _spec_pair(row):
    label = str(row.get("property") or "Specification").strip() or "Specification"
    value = _plain(row.get("value"))
    unit = str(row.get("unit") or "").strip()
    conditions = str(row.get("test_conditions") or "").strip()
    refs = _refs(row.get("source_refs"))
    conflicts = _refs(row.get("conflicts"))
    if conflicts:
        conflicts = f"conflicts: {conflicts}"
    detail = " ".join(part for part in (value, unit, conditions, refs, conflicts) if part)
    return label, detail


def _representation_text(alignment):
    if not isinstance(alignment, dict) or not alignment:
        return ""
    status = str(alignment.get("status") or "unknown").strip()
    direction = str(alignment.get("direction") or "neutral_or_unknown").strip()
    representativeness = str(alignment.get("representativeness") or "unknown").strip()
    refs = _refs(alignment.get("source_refs"))
    text = f"Status {status}; direction {direction}; lot {representativeness}."
    if refs:
        text = f"{text} Sources: {refs}."
    return text


def _pdf_pages(bundle):
    pages = []
    for row in _attachment_rows(bundle):
        for page in _row_pages(row):
            text = _page_text(page)
            if not text:
                continue
            pages.append({"label": _page_label(page, len(pages) + 1), "text": text})
            if len(pages) >= _MAX_PDF_PAGES:
                return pages
    if pages:
        return pages
    for document in bundle.get("documents") or []:
        if not isinstance(document, dict):
            continue
        for page in document.get("pages") or []:
            text = _page_text(page if isinstance(page, dict) else {})
            if not text:
                continue
            pages.append({"label": _page_label(page if isinstance(page, dict) else {}, len(pages) + 1), "text": text})
            if len(pages) >= _MAX_PDF_PAGES:
                return pages
    return pages


def _attachment_rows(bundle):
    rows = bundle.get("attachments")
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, dict)]


_ANALYSIS_DOCUMENT = "document"
_SOURCE_WEIGHT_FIELD = "weight_per_load_field_lbs"


def _row_pages(row):
    mimetype = str(row.get("content_type") or row.get("mimetype") or "")
    analysis = row.get("analysis") if isinstance(row.get("analysis"), dict) else {}
    page_rows = row.get("pages")
    if not isinstance(page_rows, list):
        page_rows = analysis.get("pages") if isinstance(analysis.get("pages"), list) else None
    if isinstance(page_rows, list):
        return [page for page in page_rows if isinstance(page, dict)]
    if mimetype != "application/pdf" and row.get("analysis_type") != _ANALYSIS_DOCUMENT:
        return []
    text = row.get("extracted_text") or row.get("page_text") or analysis.get("text")
    if not str(text or "").strip():
        return []
    return [
        {
            "text": text,
            "source_ref": row.get("source_ref") or row.get("source_id"),
            "parse_status": row.get("parse_status") or analysis.get("parse_status"),
        }
    ]


def _page_text(page):
    status = str(page.get("parse_status") or page.get("status") or "").strip().lower()
    text = page.get("text") or page.get("page_text") or page.get("extracted_text") or ""
    if status == "unknown" and not str(text).strip():
        return ""
    return _bounded(text, _MAX_PAGE_CHARS)


def _page_label(page, number):
    page_number = page.get("page_number") or number
    ref = str(page.get("source_ref") or "").strip()
    label = f"PDF page {page_number}"
    return f"{label} ({ref})" if ref else label


def _seller_grounded_load_lbs(bundle):
    """Point mass the seller typed in the per-load field. A range, a count, or a plan is empty."""
    quantity = bundle.get("quantity")
    if not isinstance(quantity, dict):
        return None
    source = str(quantity.get("weight_source") or "").strip()
    basis = str(quantity.get("basis") or quantity.get("mass_basis") or "")
    if "planning" in source or "planning" in basis:
        return None
    if source.startswith(("unit_count:", "bare_number:", "pallet_count")):
        return None
    if source != _SOURCE_WEIGHT_FIELD and not source.startswith("explicit_"):
        return None
    if _range_high(quantity.get("load_weight_lbs_high")):
        return None
    seller = bundle.get("seller") if isinstance(bundle.get("seller"), dict) else {}
    per_load = str(seller.get("weight_per_load_text") or "").strip()
    source_text = str(quantity.get("weight_source_text") or "").strip()
    if source != _SOURCE_WEIGHT_FIELD and (not per_load or source_text != per_load):
        return None
    if source == _SOURCE_WEIGHT_FIELD and source_text and per_load and source_text != per_load:
        return None
    return _positive_float(quantity.get("load_weight_lbs"))


def _range_high(value):
    if value in (None, False, ""):
        return False
    if isinstance(value, bool):
        return False
    if isinstance(value, (int, float)):
        return value > 0
    return bool(str(value).strip())


def _positive_float(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    if number != number or number <= 0 or number == float("inf"):
        return None
    return number


def _refs(value):
    if isinstance(value, str):
        refs = [value]
    elif isinstance(value, (list, tuple)):
        refs = value
    else:
        return ""
    return ", ".join(str(ref).strip() for ref in refs if str(ref).strip())


def _plain(value):
    if value is None or isinstance(value, bool):
        return ""
    if isinstance(value, (int, float)):
        return _bounded(value, 80)
    if isinstance(value, str):
        return _bounded(value, 240)
    return ""


def _bounded(value, limit):
    text = " ".join(str(value).split())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"
