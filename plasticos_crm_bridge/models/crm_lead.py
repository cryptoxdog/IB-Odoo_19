import re

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class CrmLeadPlastOS(models.Model):
    _inherit = "crm.lead"

    # ── Mobile (Odoo 19 removed mobile from crm.lead) ──────
    mobile = fields.Char(
        string="Mobile",
        help="Mobile phone number. Copied to partner on conversion.",
    )
    mobile_sanitized = fields.Char(
        string="Mobile (E.164)",
        compute="_compute_mobile_sanitized",
        store=True,
        help="Mobile number in E.164 format for SMS and integrations.",
    )

    # ── Personal Intel (from linked contact) ────────────────
    partner_personal_intel = fields.Html(
        related="partner_id.personal_intel",
        string="Personal Intel",
        readonly=True,
    )

    # ── Delivery Term (captured during qualification) ──────
    delivery_term = fields.Selection(
        [("fcfs", "FCFS"), ("appointment", "Appointment")],
        string="Delivery Term",
        help="Delivery term preference captured during lead qualification. Copied to transaction on conversion.",
    )

    # ── Web Lead Link ──────────────────────────────────────
    web_lead_ids = fields.One2many(
        "plasticos.web.lead",
        "crm_lead_id",
        string="Web Leads",
    )
    web_lead_count = fields.Integer(
        compute="_compute_web_lead_count",
    )

    # ── Intake Link ────────────────────────────────────────
    intake_ids = fields.One2many(
        "plasticos.intake",
        "crm_lead_id",
        string="Intakes",
    )
    intake_count = fields.Integer(
        compute="_compute_intake_count",
    )
    source_intake_id = fields.Many2one(
        "plasticos.intake",
        string="Originating Intake",
        index=True,
        ondelete="set null",
        help="The pre-existing web or CRM intake from which this commercial opportunity originated.",
    )
    material_profile_id = fields.Many2one(
        "plasticos.material.profile",
        string="Opportunity Material Profile",
        index=True,
        ondelete="set null",
        help="Material profile created from the originating intake when the opportunity is qualified for matching.",
    )
    facility_profile_id = fields.Many2one(
        "plasticos.facility.profile",
        string="Facility Profile",
        index=True,
        ondelete="set null",
        help="Facility profile this lead resolved to. Several leads may share one verified facility.",
    )
    commercial_image_count = fields.Integer(
        string="Commercial Images",
        compute="_compute_commercial_image_count",
        help="Image evidence copied from the linked web lead, intake, and offer sources.",
    )

    # ── Native Opportunity lineage (Lot → Run → Result → Offer) ──
    approval_ids = fields.One2many(
        "plasticos.opportunity.approval",
        "opportunity_id",
        string="Approved Lots",
    )
    match_run_ids = fields.One2many(
        "plasticos.match.run",
        "opportunity_id",
        string="Gate Match Runs",
    )
    # One native opportunity per originating intake. Partial: manual lots and
    # historical leads without a source intake are never collapsed.
    _unique_opportunity_per_source_intake = models.UniqueIndex(
        "(source_intake_id) WHERE type = 'opportunity' AND source_intake_id IS NOT NULL"
    )

    # ── Material Profile Summary (rolled up from partner) ──
    material_profile_count = fields.Integer(
        compute="_compute_profile_summary",
    )
    total_match_count = fields.Integer(
        string="Total Matches (All Profiles)",
        compute="_compute_profile_summary",
    )
    total_transaction_count = fields.Integer(
        string="Total Transactions",
        compute="_compute_profile_summary",
    )
    partner_total_revenue = fields.Float(
        string="Total Revenue (All Profiles)",
        compute="_compute_profile_summary",
    )
    partner_last_pickup = fields.Datetime(
        string="Last Load Shipped",
        compute="_compute_profile_summary",
    )

    @api.model
    def _plasticos_adopt_crm_role_tag(self, name, xmlid):
        """Bind the role-tag XML id to one existing crm.tag, or create the only one.

        Module data and the upgrade pre-migrate call this before any seed
        record. A stale or wrong-model XML id is not rebound.
        """
        from .crm_tag_adoption import adopt_role_tag  # noqa: PLC0415

        return adopt_role_tag(self.env, name, xmlid)

    @api.depends("web_lead_ids")
    def _compute_web_lead_count(self):
        for rec in self:
            rec.web_lead_count = len(rec.web_lead_ids)

    @api.depends("intake_ids")
    def _compute_intake_count(self):
        for rec in self:
            rec.intake_count = len(rec.intake_ids)

    @api.depends("web_lead_ids", "source_intake_id")
    def _compute_commercial_image_count(self):
        Attachment = self.env["ir.attachment"]
        for rec in self:
            rec.commercial_image_count = Attachment.search_count(
                [
                    ("res_model", "=", "crm.lead"),
                    ("res_id", "=", rec.id),
                    ("mimetype", "like", "image/"),
                ]
            )

    def _commercial_image_sources(self):
        """Return all source records available at the current commercial step."""
        self.ensure_one()
        sources = [("crm.lead", self.id)]
        sources.extend(("plasticos.web.lead", web_lead.id) for web_lead in self.web_lead_ids)
        if self.source_intake_id:
            sources.append(("plasticos.intake", self.source_intake_id.id))
            if "plasticos.offer" in self.env:
                offers = self.env["plasticos.offer"].search([("intake_id", "=", self.source_intake_id.id)])
                sources.extend(("plasticos.offer", offer.id) for offer in offers)
        return sources

    def _propagate_available_commercial_images(self, *, material_profile=None):
        """Attach currently available web-lead evidence to CRM and its profile.

        This is intentionally re-runnable: a later offer or manually added
        intake image can be incorporated without repeating a provider download.
        The web-lead attachment helper preserves distinct provider uploads and
        collapses only non-provider duplicate image bytes.
        An explicit false profile copies to CRM only; omitted/None retains the
        existing opportunity-profile default for other commercial callers.
        """
        self.ensure_one()
        from odoo.addons.plasticos_web_leads.models.attachment_processor import copy_images_to_commercial_record

        sources = self._commercial_image_sources()
        crm_copied = copy_images_to_commercial_record(
            env=self.env,
            target_model="crm.lead",
            target_id=self.id,
            sources=sources,
        )
        profile = self.material_profile_id if material_profile is None else material_profile
        profile_copied = 0
        if profile:
            profile_copied = copy_images_to_commercial_record(
                env=self.env,
                target_model="plasticos.material.profile",
                target_id=profile.id,
                sources=sources,
            )
        if crm_copied or profile_copied:
            self.message_post(
                body=(
                    f"Commercial image evidence synchronized: {crm_copied} image(s) to CRM; "
                    f"{profile_copied} image(s) to material profile."
                )
            )
        return {"crm": crm_copied, "material_profile": profile_copied}

    def action_sync_commercial_images(self):
        """Reconcile images currently available from linked commercial sources."""
        self.ensure_one()
        result = self._propagate_available_commercial_images()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Commercial Images Synchronized",
                "message": (
                    f"Added {result['crm']} image(s) to CRM and "
                    f"{result['material_profile']} image(s) to the material profile."
                ),
                "type": "success",
                "sticky": False,
            },
        }

    def _linked_material_profiles(self):
        """Materials on this lead's facility, its standalone company, or its child facilities."""
        self.ensure_one()
        profiles = self.facility_profile_id.material_profile_ids
        partner = self.partner_id
        if partner and partner.is_facility:
            profiles |= partner.material_profile_ids
        if partner:
            profiles |= partner.child_ids.material_profile_ids
        return profiles

    def _material_profile_domain(self):
        """Domain matching `_linked_material_profiles` for the CRM stat button."""
        self.ensure_one()
        clauses = []
        if self.facility_profile_id:
            clauses.append([("facility_profile_id", "=", self.facility_profile_id.id)])
        partner_ids = []
        if self.partner_id and self.partner_id.is_facility:
            partner_ids.append(self.partner_id.id)
        if self.partner_id:
            partner_ids.extend(self.partner_id.child_ids.ids)
        if partner_ids:
            clauses.append([("partner_id", "in", partner_ids)])
        if not clauses:
            return [("id", "=", 0)]
        if len(clauses) == 1:
            return clauses[0]
        return ["|", *clauses[0], *clauses[1]]

    @api.depends(
        "partner_id",
        "partner_id.is_facility",
        "partner_id.child_ids",
        "partner_id.material_profile_ids",
        "partner_id.child_ids.material_profile_ids",
        "facility_profile_id",
        "facility_profile_id.material_profile_ids",
    )
    def _compute_profile_summary(self):
        for rec in self:
            profiles = rec._linked_material_profiles()
            rec.material_profile_count = len(profiles)
            rec.total_match_count = sum(profiles.mapped("match_count"))
            rec.total_transaction_count = sum(profiles.mapped("transaction_count"))
            rec.partner_total_revenue = sum(profiles.mapped("total_revenue"))
            pickups = [day for day in profiles.mapped("last_pickup_date") if day]
            rec.partner_last_pickup = max(pickups) if pickups else False

    @api.depends("mobile")
    def _compute_mobile_sanitized(self):
        for lead in self:
            if lead.mobile:
                lead.mobile_sanitized = lead._phone_format(number=lead.mobile, force_format="E164") or lead.mobile
            else:
                lead.mobile_sanitized = False

    @api.constrains("mobile")
    def _check_mobile_format(self):
        for lead in self:
            if not lead.mobile:
                continue
            digits = re.sub(r"\D", "", lead.mobile)
            if digits.startswith("1") and len(digits) == 11:
                digits = digits[1:]
            if len(digits) != 10:
                raise ValidationError("Mobile must be a 10-digit US number (e.g., 555-100-0001).")

    def _find_matching_partner(self):
        """Extend Odoo's email-only matching to also try company name."""
        partner = super()._find_matching_partner()
        if not partner and self.partner_name:
            partner = self.env["res.partner"].search(
                [
                    ("name", "=ilike", self.partner_name.strip()),
                    ("is_company", "=", True),
                    ("parent_id", "=", False),
                ],
                limit=1,
            )
        return partner

    # ── Phase 5: Convert CRM Lead to Intake ──────────────────

    def _reject_foreign_material_profile(self, partner):
        """Refuse a profile owned by a supplier other than this lead's partner.

        Many2one domains are UI filters, so a conversion can still pair an
        explicit partner with another supplier's profile.
        """
        self.ensure_one()
        profile = self.material_profile_id
        if profile and partner and profile.partner_id and profile.partner_id != partner:
            raise ValidationError(
                "Material profile belongs to a different supplier and cannot be linked to this intake."
            )

    def _intake_snapshot_from_material_profile(self, profile):
        """Snapshot fields ``create()`` skips because it does not run onchange.

        Mirrors ``plasticos.intake._onchange_material_profile``: a falsy profile
        value leaves the intake default, and quantity is stored as an integer.
        """
        vals = {"material_profile_id": profile.id}
        for source_name, target_name in (
            ("polymer_id", "polymer_id"),
            ("form_id", "form_id"),
            ("color_id", "color_id"),
            ("source_type_id", "source_type_id"),
            ("material_grade_id", "material_grade_id"),
            ("packaging_type_id", "packaging_type_id"),
            ("filler_type_id", "filler_type_id"),
        ):
            related = profile[source_name]
            if related:
                vals[target_name] = related.id
        for source_name, target_name in (
            ("melt_flow_index", "mfi_value"),
            ("density", "density_value"),
            ("moisture_percent", "moisture_pct"),
            ("contamination_percent", "contamination_pct"),
            ("filler_pct", "filler_pct"),
            ("origin_process_type", "origin_process_type"),
            ("lat", "lat"),
            ("lon", "lon"),
            ("loads_per_month", "loads_per_month"),
        ):
            value = profile[source_name]
            if value:
                vals[target_name] = value
        if profile.quantity_per_load_lbs:
            vals["quantity_per_load_lbs"] = int(profile.quantity_per_load_lbs)
        if profile.material_attribute_ids:
            vals["material_attribute_ids"] = [(6, 0, profile.material_attribute_ids.ids)]
        return vals

    def action_convert_to_intake(self):
        """Convert CRM lead into a PlastOS material intake.

        Flow:
        1. Preserve explicitly linked partners; never infer a supplier identity
        2. Reuse or create plasticos.intake linked to this lead
        3. Open the new intake form

        The pipeline stage is untouched: creating or reusing an intake is not
        a Won disposition. Stage moves stay manual CRM operations.
        """
        self.ensure_one()

        partner = self.partner_id
        if not partner and self.source_intake_id.partner_id:
            partner = self.source_intake_id.partner_id
            self.partner_id = partner

        # A HOT web lead already owns an intake. Reuse it rather than creating a
        # duplicate. Conversion does not qualify material or create a profile.
        if self.source_intake_id:
            intake = self.source_intake_id
            if intake.crm_lead_id != self:
                intake.write({"crm_lead_id": self.id})
            profile = self.material_profile_id
            if not intake.material_profile_id and profile and profile.polymer_id == intake.polymer_id:
                if profile.form_id == intake.form_id:
                    intake.material_profile_id = profile
            if intake.material_profile_id:
                if not self.material_profile_id:
                    self.material_profile_id = intake.material_profile_id
            else:
                self.message_post(body="NOT_READY_FOR_MATCHING: material qualification is still pending.")
            self._propagate_available_commercial_images(material_profile=intake.material_profile_id or False)
            self.message_post(
                body=(
                    f'Reused originating intake: <a href="#" '
                    f'data-oe-model="plasticos.intake" data-oe-id="{intake.id}">'
                    f"{intake.name or 'Web Intake'}</a>"
                )
            )
            return {
                "type": "ir.actions.act_window",
                "name": f"Intake — {partner.name or intake.pending_company_name or self.name}",
                "res_model": "plasticos.intake",
                "res_id": intake.id,
                "view_mode": "form",
                "target": "current",
            }

        # 2. Create intake
        intake_vals = {
            "partner_id": partner.id,
            "pending_company_name": self.partner_name or self.contact_name or self.name,
            "crm_lead_id": self.id,
            "intake_notes": self.description or "",
        }

        # Set lead source from CRM source_id if available
        if self.source_id:
            intake_vals["lead_source_id"] = self.source_id.id

        # polymer_id and form_id are required on plasticos.intake.
        # CRM conversion has no material context yet, so fall back to the
        # canonical "Other / Unknown" records. The sales rep can refine these
        # on the intake form after conversion.
        Polymer = self.env["plasticos.polymer"]
        Form = self.env["plasticos.material.form"]
        other_polymer = Polymer.search([("code", "=ilike", "OTHER")], limit=1)
        other_form = Form.search([("code", "=ilike", "OTHER")], limit=1)
        if other_polymer:
            intake_vals["polymer_id"] = other_polymer.id
        if other_form:
            intake_vals["form_id"] = other_form.id

        self._reject_foreign_material_profile(partner)
        if self.material_profile_id:
            intake_vals.update(self._intake_snapshot_from_material_profile(self.material_profile_id))
        intake = self.env["plasticos.intake"].create(intake_vals)
        self.source_intake_id = intake
        self._propagate_available_commercial_images(material_profile=intake.material_profile_id or False)
        if not intake.material_profile_id:
            self.message_post(body="NOT_READY_FOR_MATCHING: material qualification is still pending.")

        self.message_post(
            body=f'Intake created: <a href="#" '
            f'data-oe-model="plasticos.intake" '
            f'data-oe-id="{intake.id}">{intake.name or "New Intake"}</a>'
        )

        # 3. Open intake form
        return {
            "type": "ir.actions.act_window",
            "name": f"Intake — {partner.name or intake.pending_company_name or self.name}",
            "res_model": "plasticos.intake",
            "res_id": intake.id,
            "view_mode": "form",
            "target": "current",
        }

    def _move_to_active_supplier_stage(self):
        """Move a converted CRM lead to the configured supplier stage."""
        self.ensure_one()
        won_stage = self.env.ref(
            "plasticos_crm_bridge.stage_active_supplier",
            raise_if_not_found=False,
        )
        if won_stage:
            self.stage_id = won_stage

    def _find_or_create_partner_from_lead(self):
        """Find existing partner by name or create new one from lead data."""
        Partner = self.env["res.partner"]
        name = self.partner_name or self.contact_name or self.name

        # Try exact match first
        existing = Partner.search(
            [
                ("name", "=ilike", name),
                ("is_company", "=", True),
                ("parent_id", "=", False),
            ],
            limit=1,
        )
        if existing:
            self.message_post(body=f"Linked to existing partner: {existing.name}")
            return existing

        # Create new partner
        vals = {
            "name": name,
            "is_company": True,
            "email": self.email_from,
            "phone": self.phone,
            "street": self.street,
            "city": self.city,
            "state_id": self.state_id.id if self.state_id else False,
            "zip": self.zip,
            "country_id": self.country_id.id if self.country_id else False,
            "supplier_rank": 1,
        }
        if "mobile" in Partner._fields:
            vals["mobile"] = self.mobile or False

        # Set lead source from CRM source_id
        if self.source_id:
            vals["lead_source_id"] = self.source_id.id

        partner = Partner.create(vals)
        self.message_post(body=f"Created new partner: {partner.name} (ID: {partner.id})")
        return partner

    def action_view_intakes(self):
        """Navigate to intakes linked to this CRM lead."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": f"Intakes — {self.partner_name or self.name}",
            "res_model": "plasticos.intake",
            "view_mode": "list,form",
            "domain": [("crm_lead_id", "=", self.id)],
            "context": {"default_crm_lead_id": self.id},
        }

    # ── Navigation Actions (for smart buttons) ───────────────

    def action_view_web_leads(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": f"Web Leads — {self.partner_name or self.name}",
            "res_model": "plasticos.web.lead",
            "view_mode": "list,form",
            "domain": [("crm_lead_id", "=", self.id)],
        }

    def action_view_material_profiles(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": f"Material Profiles — {self.partner_id.name or self.name or ''}",
            "res_model": "plasticos.material.profile",
            "view_mode": "list,form",
            "domain": self._material_profile_domain(),
        }

    def action_view_match_results(self):
        """Gate match results produced for this opportunity's runs."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Match Results — %s") % (self.name or ""),
            "res_model": "plasticos.match.result",
            "view_mode": "list,form",
            "domain": [("match_run_id.opportunity_id", "=", self.id)],
            "target": "current",
        }

    def action_view_match_runs(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Gate Match Runs — %s") % (self.name or ""),
            "res_model": "plasticos.match.run",
            "view_mode": "list,form",
            "domain": [("opportunity_id", "=", self.id)],
            "target": "current",
        }

    def action_view_offers(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Offers — %s") % (self.name or ""),
            "res_model": "plasticos.offer",
            "view_mode": "list,form",
            "domain": [("opportunity_id", "=", self.id)],
            "target": "current",
        }

    # ── Partners-first native Opportunity matching command ──────

    @api.model
    def _plasticos_manual_opportunity_action(self, *, partner=None, material_profile=None, facility_profile=None):
        """Open a new native Opportunity preset from a Partner and Material Profile.

        The manual route starts here. Nothing is created until the broker saves;
        no intake and no facility profile are synthesized.
        """
        partner = partner or (material_profile.partner_id if material_profile else None)
        context = {"default_type": "opportunity"}
        if partner:
            context["default_partner_id"] = partner.id
            context["default_name"] = _("Opportunity — %s") % partner.name
        if material_profile:
            context["default_material_profile_id"] = material_profile.id
            if partner:
                context["default_name"] = f"{partner.name} — {material_profile.display_name}"
        if facility_profile:
            context["default_facility_profile_id"] = facility_profile.id
        return {
            "type": "ir.actions.act_window",
            "name": _("New Opportunity"),
            "res_model": "crm.lead",
            "view_mode": "form",
            "target": "current",
            "context": context,
        }

    def _plasticos_opportunity_source(self):
        self.ensure_one()
        if self.source_intake_id and self.web_lead_ids:
            return "hot"
        if self.vanillasoft_id:
            return "vanillasoft"
        return "manual"

    def _plasticos_bind_opportunity_material(self):
        """Bind the one existing material profile of the verified partner; create nothing.

        VanillaSoft and manual ingress call this after the partner is verified.
        Several or zero profiles leave the choice to the broker.
        """
        Approval = self.env["plasticos.opportunity.approval"]
        candidates = self.filtered(lambda lead: lead.partner_id and not lead.material_profile_id)
        if not candidates:
            return
        owners_by_lead = {lead.id: Approval._allowed_profile_owners(lead.partner_id) for lead in candidates}
        all_owner_ids = {owner_id for owners in owners_by_lead.values() for owner_id in owners.ids}
        # One query for every candidate lead; profiles are then grouped per lead.
        profiles = self.env["plasticos.material.profile"].search([("partner_id", "in", list(all_owner_ids))])
        for lead in candidates:
            owned = profiles.filtered(lambda profile, owners=owners_by_lead[lead.id]: profile.partner_id in owners)
            if len(owned) == 1:
                lead.material_profile_id = owned

    def _plasticos_require_lot_inputs(self):
        self.ensure_one()
        if self.type != "opportunity":
            raise UserError(_("Only a native CRM opportunity can approve a lot. Convert the lead first."))
        if not self.partner_id:
            raise UserError(_("Link the verified Partner before approving a lot. No partner is created here."))
        if not self.material_profile_id:
            raise UserError(_("Select the approved Material Profile before approving a lot."))
        self._reject_foreign_material_profile(self.partner_id)

    def action_approve_lot(self):
        """Mint one immutable approved lot from the current Partner, Material Profile and optional Facility."""
        self._plasticos_require_lot_inputs()
        approval = self.env["plasticos.opportunity.approval"].mint(
            self,
            source=self._plasticos_opportunity_source(),
            partner=self.partner_id,
            material_profile=self.material_profile_id,
            facility_profile=self.facility_profile_id or None,
            source_intake=self.source_intake_id or None,
        )
        self.message_post(
            body=_(
                "Approved lot %(lot)s (%(source)s): %(partner)s / %(profile)s%(facility)s. Snapshot %(digest)s.",
                lot=approval.id,
                source=approval.source,
                partner=approval.partner_id.name,
                profile=approval.material_profile_id.display_name,
                facility=(" / " + approval.facility_profile_id.display_name) if approval.facility_profile_id else "",
                digest=(approval.snapshot_digest or "")[:12],
            ),
            message_type="notification",
            subtype_xmlid="mail.mt_note",
        )
        return approval

    def _plasticos_ensure_lot_durable(self):
        """Commit the approved lot before the orchestrator may roll the request back.

        The Gate orchestrator persists a classified failure by rolling the
        ambient transaction back and re-creating the run on an owned cursor
        (``_rollback_then_persist_failed_run_durable``). A lot minted in that
        same transaction would vanish in the rollback while the durable run
        still names it through ``approval_id``, so the failure receipt would
        fail its foreign key and the operator would lose both the lot and the
        retry entry point. The lot is immutable approval evidence: once minted
        it must survive whatever Gate does next, and a retry of the failed run
        is built from exactly this lot. Same I17 pattern as the CRM sync
        (``_ensure_caller_state_durable``): ``Cursor.commit()`` flushes first.
        """
        self.env.cr.commit()

    def action_match_opportunity(self):
        """The one Opportunity matching command: approve a lot, then match it through Gate.

        HOT, manual and VanillaSoft opportunities converge here. Each command is
        a new frozen lot; a retry of a failed run reuses its lot. No intake and
        no facility are synthesized, and facility evidence is sent only when a
        Facility Profile is linked.
        """
        from odoo.addons.plasticos_gate.services.gate_config import classify_gate_availability  # noqa: PLC0415

        orchestrator = self.env["plasticos.match.orchestrator"]
        runs = self.env["plasticos.match.run"]
        for rec in self:
            rec._plasticos_require_lot_inputs()
            verdict = classify_gate_availability(self.env)
            if not verdict.available:
                raise UserError(
                    _("Gate matching is unavailable (%s).") % ("; ".join(verdict.reasons) or verdict.status)
                )
            approval = rec.action_approve_lot()
            rec._plasticos_ensure_lot_durable()
            run, matches = orchestrator.run_match_for_lot(
                supplier_partner_id=approval.partner_id.id,
                snapshot=approval.snapshot,
                run_vals={"opportunity_id": rec.id, "approval_id": approval.id},
                intake=approval.source_intake_id or None,
                max_results=20,
                mode="strict",
            )
            orchestrator.persist_review_results(approval.source_intake_id, matches, run)
            runs |= run
            rec.message_post(
                body=_(
                    "Gate match run %(run)s on lot %(lot)s returned %(count)s eligible buyer(s). "
                    "Review the results, then create offers.",
                    run=run.id,
                    lot=approval.id,
                    count=len(matches),
                ),
                message_type="notification",
                subtype_xmlid="mail.mt_note",
            )
        return {
            "type": "ir.actions.act_window",
            "name": _("Match Results"),
            "res_model": "plasticos.match.result",
            "view_mode": "list,form",
            "domain": [("match_run_id", "in", runs.ids)],
            "target": "current",
        }

    def _plasticos_current_run(self):
        """The latest successful Gate run on this opportunity's latest lot (no query: lineage is loaded)."""
        self.ensure_one()
        approval = self.approval_ids.sorted(lambda lot: (lot.create_date or fields.Datetime.now(), lot.id))[-1:]
        if not approval:
            return self.env["plasticos.match.run"]
        runs = approval.match_run_ids.filtered(lambda run: run.state == "ok")
        return runs.sorted(lambda run: (run.create_date or fields.Datetime.now(), run.id))[-1:]

    @staticmethod
    def _plasticos_offer_vals(run, result):
        snapshot = run.approval_id.snapshot if run.approval_id and isinstance(run.approval_id.snapshot, dict) else {}
        return {
            "match_result_id": result.id,
            "intake_id": result.intake_id.id if result.intake_id else False,
            "supplier_id": run.supplier_partner_id.id,
            "buyer_id": result.buyer_partner_id.id,
            "quantity_lbs": float(snapshot.get("quantity_per_load_lbs") or 0.0),
        }

    def action_create_offers_from_results(self):
        """Create one unsent draft offer per reviewed (accepted) result of the current run; idempotent.

        Commercial terms are the broker's: the draft carries no price or
        quantity authority from the match. A second call creates nothing.
        """
        Offer = self.env["plasticos.offer"]
        run_by_lead = {}
        reviewed_all = self.env["plasticos.match.result"]
        for rec in self:
            run = rec._plasticos_current_run()
            if not run:
                raise UserError(_("Opportunity %s has no successful Gate match run on its current lot.") % rec.name)
            reviewed = run.result_ids.filtered(lambda result: result.state == "accepted")
            if not reviewed:
                raise UserError(_("No reviewed (accepted) match result on run %s. Review the results first.") % run.id)
            run_by_lead[rec.id] = (run, reviewed)
            reviewed_all |= reviewed
        # One lookup and one create for every opportunity in the batch.
        covered = set(Offer.search([("match_result_id", "in", reviewed_all.ids)]).mapped("match_result_id").ids)
        vals_list = [
            self._plasticos_offer_vals(run, result)
            for run, reviewed in run_by_lead.values()
            for result in reviewed
            if result.id not in covered
        ]
        new_offers = Offer.create(vals_list) if vals_list else Offer
        for rec in self:
            run, _reviewed = run_by_lead[rec.id]
            count = len(new_offers.filtered(lambda offer, run=run: offer.match_result_id.match_run_id == run))
            if count:
                rec.message_post(
                    body=_("Created %(count)s unsent draft offer(s) from run %(run)s.", count=count, run=run.id),
                    message_type="notification",
                    subtype_xmlid="mail.mt_note",
                )
        return {
            "type": "ir.actions.act_window",
            "name": _("Offers"),
            "res_model": "plasticos.offer",
            "view_mode": "list,form",
            "domain": [("opportunity_id", "in", self.ids)],
            "target": "current",
        }

    def action_view_transactions(self):
        self.ensure_one()
        facilities = self.partner_id.child_ids if self.partner_id else self.env["res.partner"]
        profiles = self.env["plasticos.material.profile"].search(
            [
                ("partner_id", "in", facilities.ids),
            ]
        )
        return {
            "type": "ir.actions.act_window",
            "name": f"Transactions — {self.partner_id.name or ''}",
            "res_model": "plasticos.transaction",
            "view_mode": "list,form",
            "domain": [
                "|",
                ("supplier_profile_id", "in", profiles.ids),
                ("buyer_profile_id", "in", profiles.ids),
            ],
        }
