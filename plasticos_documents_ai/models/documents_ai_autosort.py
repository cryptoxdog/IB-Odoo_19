"""Explicit administrator activation of Auto-Sort slices (TASK-071, TASK-073, DEC-018).

Nothing here runs on install or upgrade. A system administrator activates the P1
Inbox classifier from Documents > Configuration > Auto-Sort, and can deactivate
it the same way. Activation writes the versioned P1 prompt on the Plasticos Inbox
folder and lets Enterprise ``ai_documents`` create its rule
(``documents.document._ai_setup_sort_actions``), with exactly two tools: move in
folder and add tags. The rule's AI action is set to DeepSeek Flash (TASK-068).
The applied prompt version is recorded in the rule's chatter.

Slice 2 (TASK-073) does the same for each destination specialist P2–P7 on its
own folder, with the add-tags tool only. Each specialist is inactive until an
administrator activates it with the reference of its GATE-006 approval, which is
recorded in the rule's chatter.

Real documents reach DeepSeek only after the operator's GATE-005 approval;
activating a prompt on a database that receives real documents is that operator act.
"""

from markupsafe import Markup

from odoo import _, models
from odoo.exceptions import AccessError, UserError

from ..services import autosort_prompts as prompts
from ..services import deepseek_protocol as protocol

MOVE_TOOL_XMLID = "ai_documents.ir_actions_server_move_in_folder"
ADD_TAGS_TOOL_XMLID = "ai_documents.ir_actions_server_add_tags"
DOCUMENTS_DOCUMENT = "documents.document"
BASE_AUTOMATION = "base.automation"
IR_ACTIONS_SERVER = "ir.actions.server"


class PlasticosDocumentsAiAutosort(models.AbstractModel):
    _name = "plasticos.documents.ai.autosort"
    _description = "Plasticos Documents AI Auto-Sort activation"

    # ── Guards ──────────────────────────────────────────────────
    def _check_system_admin(self):
        """Server-side authority: only a system administrator (re)configures Auto-Sort."""
        if not self.env.is_superuser() and not self.env.user.has_group("base.group_system"):
            raise AccessError(_("Only a system administrator can activate or deactivate Auto-Sort."))

    def _p1_tools(self):
        return self.env.ref(MOVE_TOOL_XMLID) | self.env.ref(ADD_TAGS_TOOL_XMLID)

    def _p1_missing_tags(self) -> list[str]:
        return self._missing_tags(prompts.p1_tag_names())

    def _missing_tags(self, names) -> list[str]:
        found = set(self.env["documents.tag"].search([("name", "in", list(names))]).mapped("name"))
        return [name for name in names if name not in found]

    def _p1_prompt(self):
        documents = self.env[DOCUMENTS_DOCUMENT]
        html = prompts.build_p1_prompt(lambda xmlid: str(documents._ai_folder_insert(self.env.ref(xmlid).id)))
        return Markup(html)  # noqa: S704 - built from constants and integer folder ids only

    def _autosort_records(self, folder):
        action = self.env[IR_ACTIONS_SERVER].search([("ai_autosort_folder_id", "=", folder.id)], limit=1)
        rule = self.env[BASE_AUTOMATION].search([("ai_autosort_folder_id", "=", folder.id)], limit=1)
        return action, rule

    @staticmethod
    def _notify(message, kind="success"):
        return dict(
            type="ir.actions.client",
            tag="display_notification",
            params=dict(message=message, type=kind, sticky=False),
        )

    # ── Shared ──────────────────────────────────────────────────
    def _is_current(self, folder, prompt, tools) -> bool:
        action, rule = self._autosort_records(folder)
        if not (action and rule):
            return False
        stored = folder._fields["ai_sort_prompt"].convert_to_cache(prompt, folder)
        return (
            action.plasticos_llm_model == protocol.MODEL
            and action.ai_tool_ids == tools
            and str(folder.ai_sort_prompt or "") == str(stored or "")
        )

    def _apply(self, folder, prompt, tools, version, extra_lines=()):
        """Write ``prompt`` on ``folder``, let Enterprise build the rule, pin DeepSeek Flash."""
        replaced = bool(folder.ai_sort_prompt)
        folder.ai_sort_prompt = prompt
        folder._ai_setup_sort_actions(tools.ids)
        action, rule = self._autosort_records(folder)
        action.plasticos_llm_model = protocol.MODEL
        lines = [
            _("prompt_version: %s", version),
            _("Model: %s (non-thinking)", protocol.MODEL_LABEL),
            _("Tools: %s", ", ".join(tools.mapped("name"))),
            *extra_lines,
            _("Replaced an existing folder prompt.") if replaced else _("No previous folder prompt."),
        ]
        items = Markup("").join(Markup("<li>%s</li>") % line for line in lines)
        rule.message_post(
            body=Markup("<p>%s</p><ul>%s</ul>") % (_("Auto-Sort prompt applied by explicit activation."), items),
            subtype_xmlid="mail.mt_note",
        )

    def _remove(self, folder):
        """Remove the folder prompt, rule and AI action. Returns False when nothing was active."""
        action, rule = self._autosort_records(folder)
        if not (action or rule or folder.ai_sort_prompt):
            return False
        folder.ai_sort_prompt = False
        folder._ai_setup_sort_actions(())
        folder.message_post(
            body=_("Auto-Sort deactivated on this folder by explicit action."), subtype_xmlid="mail.mt_note"
        )
        return True

    # ── P1 Inbox ────────────────────────────────────────────────
    def _p1_is_current(self, inbox, prompt) -> bool:
        return self._is_current(inbox, prompt, self._p1_tools())

    def action_activate_p1(self):
        """Apply P1 at ``P1_PROMPT_VERSION`` on the Inbox. Idempotent."""
        self._check_system_admin()
        inbox = self.env.ref(prompts.INBOX_FOLDER_XMLID)
        missing = self._p1_missing_tags()
        if missing:
            raise UserError(_("Auto-Sort P1 needs these document tags, which do not exist yet: %s", ", ".join(missing)))
        prompt = self._p1_prompt()
        version = f"{prompts.P1_PROMPT_ID} v{prompts.P1_PROMPT_VERSION}"
        if self._p1_is_current(inbox, prompt):
            return self._notify(_("Auto-Sort %s is already active on %s.", version, inbox.name), "info")
        self._apply(inbox, prompt, self._p1_tools(), version)
        return self._notify(_("Auto-Sort %s activated on %s.", version, inbox.name))

    def action_deactivate_p1(self):
        """Remove the Inbox prompt, rule and AI action. Idempotent."""
        self._check_system_admin()
        inbox = self.env.ref(prompts.INBOX_FOLDER_XMLID)
        if not self._remove(inbox):
            return self._notify(_("Auto-Sort is not active on %s.", inbox.name), "info")
        return self._notify(_("Auto-Sort deactivated on %s.", inbox.name))

    # ── P2–P7 destination specialists (TASK-073) ────────────────
    def _specialist_tools(self):
        return self.env.ref(ADD_TAGS_TOOL_XMLID)

    def _specialist_folder(self, prompt_id):
        if prompt_id not in prompts.SPECIALIST_IDS:
            raise UserError(_("Unknown Auto-Sort specialist: %s", prompt_id))
        return self.env.ref(prompts.specialist_folder_xmlid(prompt_id))

    def action_activate_specialist(self, prompt_id, gate_006_reference):
        """Apply specialist ``prompt_id`` at ``SPECIALIST_PROMPT_VERSION`` on its folder. Idempotent.

        ``gate_006_reference`` names the operator's GATE-006 approval of this
        specialist (loop safety and measured benefit); it is required and recorded.
        """
        self._check_system_admin()
        folder = self._specialist_folder(prompt_id)
        reference = (gate_006_reference or "").strip()
        if not reference:
            raise UserError(_("Activating %s needs the reference of its GATE-006 approval.", prompt_id))
        missing = self._missing_tags(prompts.specialist_tag_names(prompt_id))
        if missing:
            raise UserError(
                _(
                    "Auto-Sort %(prompt)s needs these document tags, which do not exist yet: %(tags)s",
                    prompt=prompt_id,
                    tags=", ".join(missing),
                )
            )
        prompt = Markup(prompts.build_specialist_prompt(prompt_id))  # noqa: S704 - built from module constants only
        version = f"{prompt_id} v{prompts.SPECIALIST_PROMPT_VERSION}"
        tools = self._specialist_tools()
        if self._is_current(folder, prompt, tools):
            return self._notify(_("Auto-Sort %s is already active on %s.", version, folder.name), "info")
        self._apply(folder, prompt, tools, version, [_("GATE-006 approval: %s", reference)])
        return self._notify(_("Auto-Sort %s activated on %s.", version, folder.name))

    def action_deactivate_specialist(self, prompt_id):
        """Remove specialist ``prompt_id`` from its folder. Idempotent."""
        self._check_system_admin()
        folder = self._specialist_folder(prompt_id)
        if not self._remove(folder):
            return self._notify(_("Auto-Sort is not active on %s.", folder.name), "info")
        return self._notify(_("Auto-Sort %s deactivated on %s.", prompt_id, folder.name))
