"""Administrator wizard that activates or deactivates one Auto-Sort specialist (TASK-073)."""

from odoo import fields, models

from ..services import autosort_prompts as prompts


class PlasticosDocumentsAiSpecialistWizard(models.TransientModel):
    _name = "plasticos.documents.ai.specialist.wizard"
    _description = "Plasticos Auto-Sort specialist activation"

    prompt_id = fields.Selection(
        [(item.prompt_id, f"{item.prompt_id} {item.name}") for item in prompts.SPECIALISTS],
        string="Specialist",
        required=True,
        help="The destination-folder specialist to activate or deactivate. It only adds tags in its own folder.",
    )
    gate_006_reference = fields.Char(
        string="GATE-006 approval",
        help="Reference of the operator's GATE-006 approval of this specialist (loop safety and measured "
        "benefit). Required to activate; recorded in the rule's chatter.",
    )

    def action_activate(self):
        self.ensure_one()
        return self.env["plasticos.documents.ai.autosort"].action_activate_specialist(
            self.prompt_id, self.gate_006_reference
        )

    def action_deactivate(self):
        self.ensure_one()
        return self.env["plasticos.documents.ai.autosort"].action_deactivate_specialist(self.prompt_id)
