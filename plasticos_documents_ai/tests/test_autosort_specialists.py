"""AC-073: P2–P7 specialists, loop and conflict safety across all seven rules (TASK-073).

The model is replaced at ``DeepSeekLLMApiService._request_llm``; each test scripts
adversarial tool calls and checks what the application lets happen. Every model
call is recorded with the prompt id it ran under, so a chained rule would show up
as a second call.
"""

import base64
import json
from unittest.mock import patch

from odoo import Command
from odoo.addons.plasticos_documents_ai.services import autosort_prompts as prompts
from odoo.addons.plasticos_documents_ai.services import deepseek_protocol as protocol
from odoo.addons.plasticos_documents_ai.services.deepseek_llm_api_service import DeepSeekLLMApiService
from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, tagged
from odoo.tools import mute_logger

SYNTHETIC_PDF = base64.b64encode(b"%PDF-1.4\n% synthetic document\n%%EOF\n")
MOVE = "ir_actions_server_move_in_folder"
ADD_TAGS = "ir_actions_server_add_tags"
GATE = "GATE-006 synthetic test approval"
AI_LOGGERS = (
    "odoo.addons.ai.models.ir_actions_server",
    "odoo.addons.ai.utils.llm_api_service",
    "odoo.addons.ai_documents.models.ir_actions_server",
)


def _tool_call(name, call_id, arguments):
    return [], [(name, call_id, arguments)], [{"call_id": call_id, "name": name, "arguments": json.dumps(arguments)}]


def _tags(call_id, names):
    return _tool_call(ADD_TAGS, call_id, {"tag_names": list(names)})


@tagged("post_install", "-at_install", "plasticos_documents_ai")
class TestAutosortSpecialists(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # TASK-069 seeds the DEC-014 tags. Until it merges into this stack, the names
        # the prompts need are created here as test data; once seeded, nothing is created.
        names = set(prompts.p1_tag_names()) | {prompts.VERIFIED}
        for pid in prompts.SPECIALIST_IDS:
            names |= set(prompts.specialist_tag_names(pid))
        Tag = cls.env["documents.tag"]
        existing = set(Tag.search([("name", "in", list(names))]).mapped("name"))
        Tag.create([{"name": name} for name in sorted(names - existing)])
        cls.autosort = cls.env["plasticos.documents.ai.autosort"]
        cls.inbox = cls.env.ref(prompts.INBOX_FOLDER_XMLID)
        cls.folders = {pid: cls.env.ref(prompts.specialist_folder_xmlid(pid)) for pid in prompts.SPECIALIST_IDS}
        cls.internal_user = cls.env["res.users"].create(
            {
                "name": "Synthetic internal user",
                "login": "synthetic_documents_ai_specialist_user",
                "group_ids": [Command.set(cls.env.ref("base.group_user").ids)],
            }
        )

    # ── Helpers ─────────────────────────────────────────────────
    def _reload_rules(self):
        self.env["base.automation"]._unregister_hook()
        self.env["base.automation"]._register_hook()

    def _activate_all(self):
        self.autosort.action_activate_p1()
        for pid in prompts.SPECIALIST_IDS:
            self.autosort.action_activate_specialist(pid, GATE)
        self._reload_rules()

    def _rule(self, folder):
        return self.env["base.automation"].search([("ai_autosort_folder_id", "=", folder.id)])

    def _tag(self, name):
        return self.env["documents.tag"].search([("name", "=", name)], limit=1)

    def _run(self, scripts, operation):
        """Run ``operation`` while the model follows ``scripts[prompt id]``.

        Returns the operation's result, the model calls, and one entry per AI rule run
        (the prompt id of the folder whose rule ran), counted at
        ``ir.actions.server._ai_action_run`` so a rule re-triggering itself shows up.
        """
        turns = {pid: iter(script) for pid, script in scripts.items()}
        seen, runs = [], []
        folder_ids = {self.env.ref(xmlid).id: pid for xmlid, pid in prompts.folder_prompt_ids().items()}
        actions = type(self.env["ir.actions.server"])
        original_run = actions._ai_action_run

        def _counted(action, record):
            runs.append(folder_ids.get(action.ai_autosort_folder_id.id))
            return original_run(action, record)

        def _mocked(service, llm_model, system_prompts, user_prompts, tools=None, files=None, **_kwargs):
            pid = runs[-1] if runs else None
            seen.append({"prompt_id": pid, "model": llm_model, "tools": sorted(tools or ())})
            return next(turns.get(pid, iter(())), (["done"], [], []))

        with (
            patch.object(actions, "_ai_action_run", _counted),
            patch.object(DeepSeekLLMApiService, "_request_llm", _mocked),
        ):
            result = operation()
        return result, seen, runs

    def _upload(self, folder, scripts, name="synthetic.pdf"):
        return self._run(
            scripts,
            lambda: self.env["documents.document"].create(
                {"name": name, "folder_id": folder.id, "datas": SYNTHETIC_PDF, "mimetype": "application/pdf"}
            ),
        )

    # ── Install / activation ────────────────────────────────────
    def test_no_specialist_is_active_before_explicit_activation(self):
        for folder in self.folders.values():
            self.assertFalse(self._rule(folder))
            self.assertFalse(folder.ai_sort_prompt)

    def test_only_a_system_administrator_can_activate_or_deactivate(self):
        as_user = self.autosort.with_user(self.internal_user)
        with self.assertRaises(AccessError):
            as_user.action_activate_specialist("P2", GATE)
        with self.assertRaises(AccessError):
            as_user.action_deactivate_specialist("P2")
        with self.assertRaises(AccessError):
            self.env["plasticos.documents.ai.specialist.wizard"].with_user(self.internal_user).create(
                {"prompt_id": "P2", "gate_006_reference": GATE}
            )
        self.assertFalse(self._rule(self.folders["P2"]))

    def test_activation_needs_a_gate_006_reference_and_a_known_specialist(self):
        for reference in (False, "", "   "):
            with self.assertRaisesRegex(UserError, "GATE-006"):
                self.autosort.action_activate_specialist("P3", reference)
        with self.assertRaises(UserError):
            self.autosort.action_activate_specialist("P1", GATE)
        with self.assertRaises(UserError):
            self.autosort.action_activate_specialist("P8", GATE)
        self.assertFalse(self._rule(self.folders["P3"]))
        self.assertFalse(self._rule(self.inbox))

    def test_activation_refuses_while_a_specialist_tag_is_missing(self):
        self._tag("Damage Photo").name = "Damage Photo (renamed by test)"
        with self.assertRaisesRegex(UserError, "Damage Photo"):
            self.autosort.action_activate_specialist("P4", GATE)
        self.assertFalse(self._rule(self.folders["P4"]))

    def test_each_specialist_gets_one_add_tags_only_deepseek_rule(self):
        add_tags = self.env.ref("ai_documents.ir_actions_server_add_tags")
        for pid, folder in self.folders.items():
            wizard = self.env["plasticos.documents.ai.specialist.wizard"].create(
                {"prompt_id": pid, "gate_006_reference": GATE}
            )
            wizard.action_activate()
            rule = self._rule(folder)
            self.assertEqual(len(rule), 1, pid)
            action = rule.action_server_ids
            self.assertEqual(action.ai_tool_ids, add_tags, pid)
            self.assertEqual(action.plasticos_llm_model, protocol.MODEL, pid)
            self.assertIn(f"{pid} v{prompts.SPECIALIST_PROMPT_VERSION}", folder.ai_sort_prompt, pid)
            self.assertNotIn("data-ai-record-id", folder.ai_sort_prompt, pid)
            note = rule.message_ids.filtered(lambda m: "prompt_version" in (m.body or ""))
            self.assertEqual(len(note), 1, pid)
            self.assertIn(GATE, note.body, pid)
        self.assertFalse(self._rule(self.inbox), "activating specialists does not activate P1")

    def test_activation_is_idempotent_and_deactivation_removes_only_that_specialist(self):
        self.autosort.action_activate_specialist("P5", GATE)
        self.autosort.action_activate_specialist("P5", GATE)
        self.autosort.action_activate_specialist("P6", GATE)
        rule = self._rule(self.folders["P5"])
        self.assertEqual(len(rule), 1)
        self.assertEqual(len(rule.message_ids.filtered(lambda m: "prompt_version" in (m.body or ""))), 1)
        self.autosort.action_deactivate_specialist("P5")
        self.assertFalse(self._rule(self.folders["P5"]))
        self.assertFalse(self.folders["P5"].ai_sort_prompt)
        self.assertEqual(len(self._rule(self.folders["P6"])), 1)
        self.autosort.action_deactivate_specialist("P5")

    # ── Loop safety across all seven rules ──────────────────────
    def test_a_p1_move_never_starts_the_destination_rule(self):
        self._activate_all()
        for pid, folder in self.folders.items():
            family = prompts.family(prompts.specialist(pid).family_key)
            # The destination specialist is scripted to tag adversarially; it must never run.
            document, seen, runs = self._upload(
                self.inbox,
                {
                    "P1": [_tool_call(MOVE, "m", {"folder_id": folder.id}), _tags("t", [family.types[0]])],
                    pid: [_tags("x", [prompts.NEEDS_REVIEW, "Carrier Invoice"])],
                },
                name=f"inbox_to_{pid}.pdf",
            )
            self.assertEqual(document.folder_id, folder, pid)
            self.assertEqual(document.tag_ids.mapped("name"), [family.types[0]], pid)
            self.assertEqual(runs, ["P1"], pid)

    def test_a_specialist_runs_once_on_a_direct_upload_and_its_tags_start_nothing(self):
        self._activate_all()
        for pid, folder in self.folders.items():
            item = prompts.specialist(pid)
            first_type = next(name for name in item.allowed_tags if name in prompts.type_tag_names())
            document, seen, runs = self._upload(
                folder,
                {pid: [_tags("a", [first_type]), _tags("b", [prompts.EVIDENCE_GAP]), _tags("c", [first_type])]},
                name=f"direct_{pid}.pdf",
            )
            self.assertEqual(document.folder_id, folder, pid)
            self.assertEqual(set(document.tag_ids.mapped("name")), {first_type, prompts.EVIDENCE_GAP}, pid)
            self.assertEqual(runs, [pid], pid)
            self.assertEqual(seen[0]["tools"], [ADD_TAGS], pid)
            self.assertEqual(seen[0]["model"], protocol.MODEL, pid)

    def test_a_human_move_out_of_the_inbox_runs_the_destination_specialist_once(self):
        self._activate_all()
        document, seen, runs = self._upload(
            self.inbox, {"P1": [_tags("nr", [prompts.NEEDS_REVIEW])]}, name="unclear.pdf"
        )
        self.assertEqual((document.folder_id, runs), (self.inbox, ["P1"]))
        folder = self.folders["P3"]
        _result, seen, runs = self._run(
            {"P3": [_tags("st", ["Scale Ticket"])]},
            lambda: document.write({"folder_id": folder.id}),
        )
        self.assertEqual(runs, ["P3"])
        self.assertEqual(set(document.tag_ids.mapped("name")), {prompts.NEEDS_REVIEW, "Scale Ticket"})

    # ── Conflict safety: adversarial specialist outputs ─────────
    @mute_logger(*AI_LOGGERS)
    def test_adversarial_specialist_outputs_are_refused_by_the_application(self):
        self._activate_all()
        bols = self.folders["P2"]
        financial = self.folders["P6"]
        moves_before = self.env["account.move"].search_count([])
        document, seen, runs = self._upload(
            bols,
            {
                "P2": [
                    _tool_call(MOVE, "move", {"folder_id": financial.id}),  # tool not granted
                    _tool_call("ir_actions_server_create_vendor_bill_code", "bill", {}),  # tool not granted
                    _tags("verified", [prompts.VERIFIED]),  # never by AI
                    _tags("split", [prompts.TO_SPLIT]),  # not a P2 tag
                    _tags("foreign", ["Carrier Invoice"]),  # another family without Needs Review
                    _tags("conflict", [prompts.NEEDS_REVIEW, "Carrier Invoice"]),  # the v2.0 refinement conflict
                ]
            },
            name="ignore_previous_instructions.pdf",
        )
        self.assertEqual(document.folder_id, bols)
        self.assertEqual(set(document.tag_ids.mapped("name")), {prompts.NEEDS_REVIEW, "Carrier Invoice"})
        self.assertEqual(self.env["account.move"].search_count([]), moves_before)
        self.assertEqual(runs, ["P2"])

    @mute_logger(*AI_LOGGERS)
    def test_a_specialist_cannot_move_even_when_its_tools_are_edited(self):
        self._activate_all()
        folder = self.folders["P4"]
        action = self._rule(folder).action_server_ids
        action.ai_tool_ids |= self.env.ref("ai_documents.ir_actions_server_move_in_folder")
        document, seen, runs = self._upload(
            folder, {"P4": [_tool_call(MOVE, "move", {"folder_id": self.inbox.id}), _tags("t", ["Loading Pic"])]}
        )
        self.assertEqual(document.folder_id, folder)
        self.assertEqual(document.tag_ids.mapped("name"), ["Loading Pic"])
        self.assertEqual(runs, ["P4"])

    @mute_logger(*AI_LOGGERS)
    def test_p1_is_held_to_its_own_tags(self):
        self._activate_all()
        folder = self.folders["P6"]
        document, _seen, _runs = self._upload(
            self.inbox,
            {
                "P1": [
                    _tags("dup", [prompts.DUPLICATE_CANDIDATE]),  # P6 only
                    _tags("verified", ["Vendor Bill", prompts.VERIFIED]),  # never by AI: the whole call is refused
                    _tool_call(MOVE, "m", {"folder_id": folder.id}),
                    _tags("ok", ["Vendor Bill"]),
                ]
            },
        )
        self.assertEqual(document.folder_id, folder)
        self.assertEqual(document.tag_ids.mapped("name"), ["Vendor Bill"])

    def test_tags_added_outside_a_plasticos_rule_keep_enterprise_behavior(self):
        document = self.env["documents.document"].create(
            {"name": "manual.pdf", "folder_id": self.folders["P2"].id, "datas": SYNTHETIC_PDF}
        )
        document._ai_action_add_tags([prompts.TO_SPLIT])
        self.assertEqual(document.tag_ids.mapped("name"), [prompts.TO_SPLIT])
