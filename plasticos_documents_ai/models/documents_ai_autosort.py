"""Explicit administrator activation of Auto-Sort slices (TASK-071, DEC-018).

Nothing here runs on install or upgrade. A system administrator activates the P1
Inbox classifier from Documents > Configuration > Auto-Sort, and can deactivate
it the same way. Activation writes the versioned P1 prompt on the Plasticos Inbox
folder and lets Enterprise ``ai_documents`` create its rule
(``documents.document._ai_setup_sort_actions``), with exactly two tools: move in
folder and add tags. The rule's AI action is set to DeepSeek Flash (TASK-068).
The applied prompt version is recorded in the rule's chatter.

Real documents reach DeepSeek only after the operator's GATE-005 approval;
activating P1 on a database that receives real documents is that operator act.
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
        names = prompts.p1_tag_names()
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

    # ── P1 Inbox ────────────────────────────────────────────────
    def _p1_is_current(self, inbox, prompt) -> bool:
        action, rule = self._autosort_records(inbox)
        if not (action and rule):
            return False
        stored = inbox._fields["ai_sort_prompt"].convert_to_cache(prompt, inbox)
        return (
            action.plasticos_llm_model == protocol.MODEL
            and action.ai_tool_ids == self._p1_tools()
            and str(inbox.ai_sort_prompt or "") == str(stored or "")
        )

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

        replaced = bool(inbox.ai_sort_prompt)
        inbox.ai_sort_prompt = prompt
        tools = self._p1_tools()
        inbox._ai_setup_sort_actions(tools.ids)
        action, rule = self._autosort_records(inbox)
        action.plasticos_llm_model = protocol.MODEL
        rule.message_post(
            body=Markup("<p>%s</p><ul><li>%s</li><li>%s</li><li>%s</li><li>%s</li></ul>")
            % (
                _("Auto-Sort prompt applied by explicit activation."),
                _("prompt_version: %s", version),
                _("Model: %s (non-thinking)", protocol.MODEL_LABEL),
                _("Tools: %s", ", ".join(tools.mapped("name"))),
                _("Replaced an existing folder prompt.") if replaced else _("No previous folder prompt."),
            ),
            subtype_xmlid="mail.mt_note",
        )
        return self._notify(_("Auto-Sort %s activated on %s.", version, inbox.name))

    def action_deactivate_p1(self):
        """Remove the Inbox prompt, rule and AI action. Idempotent."""
        self._check_system_admin()
        inbox = self.env.ref(prompts.INBOX_FOLDER_XMLID)
        action, rule = self._autosort_records(inbox)
        if not (action or rule or inbox.ai_sort_prompt):
            return self._notify(_("Auto-Sort is not active on %s.", inbox.name), "info")
        inbox.ai_sort_prompt = False
        inbox._ai_setup_sort_actions(())
        inbox.message_post(
            body=_("Auto-Sort deactivated on this folder by explicit action."), subtype_xmlid="mail.mt_note"
        )
        return self._notify(_("Auto-Sort deactivated on %s.", inbox.name))
