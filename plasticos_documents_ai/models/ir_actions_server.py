"""Per-action AI model for Odoo's ``ai`` server actions (DEC-016 OPT-B).

Odoo 19 runs every ``state = 'ai'`` server action, Documents Auto-Sort included,
on two class constants: ``AI_PROVIDER = "openai"`` and ``AI_MODEL = "gpt-4.1"``
(``ai/models/ir_actions_server.py:26-27,279-280``). This override keeps those
values for every action except one an administrator explicitly set to DeepSeek
Flash through ``plasticos_llm_model``. Nothing here sets that field: installing or
upgrading the addon leaves every action on Odoo's own provider.
"""

from odoo import fields, models

from ..services import deepseek_protocol as protocol


class IrActionsServer(models.Model):
    _inherit = "ir.actions.server"

    plasticos_llm_model = fields.Selection(
        [(protocol.MODEL, protocol.MODEL_LABEL)],
        string="AI Model Override",
        groups="base.group_system",
        copy=True,
        help="Run this AI action on the selected model instead of Odoo's default AI model. "
        "DeepSeek Flash runs without thinking mode; it needs the ai.deepseek_key system "
        "parameter. See the Plasticos Documents AI README for what is sent to DeepSeek.",
    )

    def _plasticos_uses_deepseek(self) -> bool:
        # sudo: the field is restricted to system administrators for editing; any
        # user whose upload triggers the action must still run it on its model.
        return len(self) == 1 and self.sudo().plasticos_llm_model == protocol.MODEL

    @property
    def AI_PROVIDER(self):  # noqa: N802 - the Enterprise attribute name
        if self._plasticos_uses_deepseek():
            return protocol.PROVIDER
        return super().AI_PROVIDER

    @property
    def AI_MODEL(self):  # noqa: N802 - the Enterprise attribute name
        if self._plasticos_uses_deepseek():
            return protocol.MODEL
        return super().AI_MODEL
