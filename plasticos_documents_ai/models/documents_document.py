"""Server-side tag and move allowlists for Plasticos Auto-Sort rules (TASK-073, INV-07).

Enterprise ``ai_documents`` grants a rule its tools (``ai_tool_ids``) but lets the
add-tags tool add any existing tag by name. A prompt is not a control, so a rule
that this addon configured (its AI action uses DeepSeek Flash through
``plasticos_llm_model``) is held here to the tags of its prompt
(``autosort_prompts.tag_refusal``), and a destination specialist (P2–P7) can never
move a document even if its tools were edited. Rules this addon did not configure
keep Enterprise behavior.
"""

from odoo import _, models
from odoo.exceptions import UserError

from ..services import autosort_prompts as prompts


class DocumentsDocument(models.Model):
    _inherit = "documents.document"

    def _plasticos_autosort_prompt_id(self):
        """The Plasticos prompt id of the AI action now running, or ``None``."""
        action = self.env.context.get("ai_executed_action")
        if not isinstance(action, models.BaseModel) or action._name != "ir.actions.server":
            return None
        action = action.sudo()  # sudo: read the admin-only plasticos_llm_model of the rule now running
        if not action.plasticos_llm_model:
            return None
        folder = action.ai_autosort_folder_id
        for xmlid, prompt_id in prompts.folder_prompt_ids().items():
            if folder == self.env.ref(xmlid, raise_if_not_found=False):
                return prompt_id
        return None

    def _ai_action_add_tags(self, tag_names):
        prompt_id = self._plasticos_autosort_prompt_id()
        if prompt_id:
            self.ensure_one()
            refusal = prompts.tag_refusal(prompt_id, tag_names or (), self.tag_ids.mapped("name"))
            if refusal:
                raise UserError(_("Tags refused by the %(prompt)s rule: %(reason)s", prompt=prompt_id, reason=refusal))
        return super()._ai_action_add_tags(tag_names)

    def _ai_action_move_in_folder(self, folder_id):
        prompt_id = self._plasticos_autosort_prompt_id()
        if prompt_id and prompt_id != prompts.P1_PROMPT_ID:
            raise UserError(_("The %s rule only adds tags; it never moves a document.", prompt_id))
        return super()._ai_action_move_in_folder(folder_id)
