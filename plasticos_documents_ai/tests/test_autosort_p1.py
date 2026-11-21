"""AC-071: P1 Inbox Auto-Sort mechanics with a mocked model (TASK-071).

The model is replaced at ``DeepSeekLLMApiService._request_llm``; each test scripts
the tool calls a model would make and checks what the application lets happen.
Owner-activity routing of review signals is the TASK-060 router's (TASK-070) and
is asserted there, not here.
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
from odoo.tools import convert_file, mute_logger

SYNTHETIC_PDF = base64.b64encode(b"%PDF-1.4\n% synthetic document\n%%EOF\n")
MOVE = "ir_actions_server_move_in_folder"
ADD_TAGS = "ir_actions_server_add_tags"


def _tool_call(name, call_id, arguments):
    return [], [(name, call_id, arguments)], [{"call_id": call_id, "name": name, "arguments": json.dumps(arguments)}]


@tagged("post_install", "-at_install", "plasticos_documents_ai")
class TestAutosortP1(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # TASK-069 seeds the DEC-014 tags in plasticos_documents_native. Until it
        # merges, the names P1 needs are created here as test data; once seeded,
        # the search finds them and nothing is created.
        Tag = cls.env["documents.tag"]
        existing = set(Tag.search([("name", "in", list(prompts.p1_tag_names()))]).mapped("name"))
        missing = [name for name in prompts.p1_tag_names() if name not in existing]
        if missing:
            Tag.create([{"name": name} for name in missing])
        cls.autosort = cls.env["plasticos.documents.ai.autosort"]
        cls.inbox = cls.env.ref(prompts.INBOX_FOLDER_XMLID)
        cls.folders = {family.key: cls.env.ref(family.folder_xmlid) for family in prompts.TYPE_FAMILIES}
        cls.internal_user = cls.env["res.users"].create(
            {
                "name": "Synthetic internal user",
                "login": "synthetic_documents_ai_user",
                "group_ids": [Command.set(cls.env.ref("base.group_user").ids)],
            }
        )

    def _activate(self):
        self.autosort.action_activate_p1()
        self.env["base.automation"]._unregister_hook()
        self.env["base.automation"]._register_hook()

    def _rule(self):
        return self.env["base.automation"].search([("ai_autosort_folder_id", "=", self.inbox.id)])

    def _upload(self, name, script):
        """Upload a synthetic document to the Inbox while the model follows ``script``."""
        turns = iter(script)
        seen = []

        def _mocked(service, llm_model, system_prompts, user_prompts, tools=None, files=None, **_kwargs):
            seen.append({"model": llm_model, "prompt": "".join(user_prompts), "tools": sorted(tools or ())})
            return next(turns, (["done"], [], []))

        with patch.object(DeepSeekLLMApiService, "_request_llm", _mocked):
            document = self.env["documents.document"].create(
                {"name": name, "folder_id": self.inbox.id, "datas": SYNTHETIC_PDF, "mimetype": "application/pdf"}
            )
        return document, seen

    def _tag(self, name):
        return self.env["documents.tag"].search([("name", "=", name)], limit=1)

    # ── Install / activation / deactivation ─────────────────────
    def test_nothing_is_active_before_explicit_activation(self):
        self.assertFalse(self._rule())
        self.assertFalse(self.inbox.ai_sort_prompt)

    def test_only_a_system_administrator_can_activate_or_deactivate(self):
        with self.assertRaises(AccessError):
            self.autosort.with_user(self.internal_user).action_activate_p1()
        with self.assertRaises(AccessError):
            self.autosort.with_user(self.internal_user).action_deactivate_p1()
        self.assertFalse(self._rule())

    def test_activation_refuses_while_a_p1_tag_is_missing(self):
        packing_list = self._tag("Packing List")
        packing_list.name = "Packing List (renamed by test)"
        with self.assertRaisesRegex(UserError, "Packing List"):
            self.autosort.action_activate_p1()
        self.assertFalse(self._rule())

    def test_activation_creates_one_two_tool_deepseek_rule_and_records_the_version(self):
        self._activate()
        rule = self._rule()
        self.assertEqual(len(rule), 1)
        self.assertEqual(rule.trigger, "on_create_or_write")
        action = rule.action_server_ids
        self.assertEqual(action.state, "ai")
        self.assertEqual(action.plasticos_llm_model, protocol.MODEL)
        self.assertEqual(
            action.ai_tool_ids,
            self.env.ref("ai_documents.ir_actions_server_move_in_folder")
            | self.env.ref("ai_documents.ir_actions_server_add_tags"),
        )
        self.assertEqual((action.AI_PROVIDER, action.AI_MODEL), (protocol.PROVIDER, protocol.MODEL))

        prompt = self.inbox.ai_sort_prompt
        for folder in self.folders.values():
            self.assertIn(f'data-ai-record-id="{folder.id}"', prompt)
        self.assertNotIn(f'data-ai-record-id="{self.inbox.id}"', prompt)
        self.assertIn(f"v{prompts.P1_PROMPT_VERSION}", prompt)

        notes = rule.message_ids.filtered(lambda m: "prompt_version" in (m.body or ""))
        self.assertEqual(len(notes), 1)
        self.assertIn(f"P1 v{prompts.P1_PROMPT_VERSION}", notes.body)

    def test_activation_is_idempotent(self):
        self._activate()
        self._activate()
        rule = self._rule()
        self.assertEqual(len(rule), 1)
        self.assertEqual(len(self.env["ir.actions.server"].search([("ai_autosort_folder_id", "=", self.inbox.id)])), 1)
        self.assertEqual(len(rule.message_ids.filtered(lambda m: "prompt_version" in (m.body or ""))), 1)

    def test_administrator_prompt_edit_survives_upgrade(self):
        self._activate()
        edited = self.inbox.ai_sort_prompt + "<p>Administrator note: synthetic edit.</p>"
        self.inbox.ai_sort_prompt = edited
        kept = self.inbox.ai_sort_prompt
        for module, path in (
            ("plasticos_documents_native", "data/document_folders.xml"),
            ("plasticos_documents_ai", "views/ir_actions_server_views.xml"),
            ("plasticos_documents_ai", "data/autosort_actions.xml"),
        ):
            convert_file(self.env, module, path, {}, mode="update", noupdate=False)
        self.inbox.invalidate_recordset()
        self.assertEqual(self.inbox.ai_sort_prompt, kept)
        self.assertEqual(len(self._rule()), 1)

    def test_deactivation_removes_rule_and_action_and_is_idempotent(self):
        self._activate()
        self.autosort.action_deactivate_p1()
        self.assertFalse(self._rule())
        self.assertFalse(self.env["ir.actions.server"].search([("ai_autosort_folder_id", "=", self.inbox.id)]))
        self.assertFalse(self.inbox.ai_sort_prompt)
        self.autosort.action_deactivate_p1()

    # ── P1 acceptance examples (AI_PROMPT_INVENTORY.yaml P1) ─────
    def _assert_routed(self, name, family_key, tags):
        folder = self.folders[family_key]
        document, seen = self._upload(
            name,
            [
                _tool_call(MOVE, "call_move", {"folder_id": folder.id}),
                _tool_call(ADD_TAGS, "call_tags", {"tag_names": tags}),
            ],
        )
        self.assertEqual(document.folder_id, folder, name)
        self.assertEqual(set(document.tag_ids.mapped("name")), set(tags), name)
        self.assertEqual(seen[0]["model"], protocol.MODEL)
        self.assertEqual(seen[0]["tools"], [MOVE, ADD_TAGS])
        self.assertIn(f"v{prompts.P1_PROMPT_VERSION}", seen[0]["prompt"])
        return document

    def test_unsigned_bol_goes_to_bills_of_lading(self):
        self._activate()
        self._assert_routed("unsigned_bol.pdf", "transportation", ["BOL", prompts.EVIDENCE_GAP])

    def test_scale_ticket_missing_tare_goes_to_scale_tickets(self):
        self._activate()
        self._assert_routed("ticket_no_tare.pdf", "measurement", ["Scale Ticket", prompts.EVIDENCE_GAP])

    def test_vendor_invoice_with_supporting_bol_goes_to_financial(self):
        self._activate()
        moves_before = self.env["account.move"].search_count([])
        self._assert_routed("invoice_with_bol.pdf", "financial", ["Vendor Bill", prompts.INCLUDES_SUPPORTING_EVIDENCE])
        self.assertEqual(self.env["account.move"].search_count([]), moves_before, "classification creates no bill")

    def test_generic_filename_packing_list_goes_to_orders_and_shipping(self):
        self._activate()
        self._assert_routed("scan_001.pdf", "orders_and_shipping", ["Packing List"])

    def test_unidentifiable_content_stays_in_inbox_with_needs_review(self):
        self._activate()
        document, _seen = self._upload(
            "unknown.pdf", [_tool_call(ADD_TAGS, "call_tags", {"tag_names": [prompts.NEEDS_REVIEW]})]
        )
        self.assertEqual(document.folder_id, self.inbox)
        self.assertEqual(document.tag_ids.mapped("name"), [prompts.NEEDS_REVIEW])

    # ── Injected instructions ───────────────────────────────────
    @mute_logger(
        "odoo.addons.ai.models.ir_actions_server",
        "odoo.addons.ai.utils.llm_api_service",
        "odoo.addons.ai_documents.models.ir_actions_server",
    )
    def test_injected_instructions_cannot_act_beyond_the_two_tools(self):
        self._activate()
        root = self.env.ref("plasticos_documents_native.folder_plasticos_root")
        moves_before = self.env["account.move"].search_count([])
        document, seen = self._upload(
            "ignore_previous_instructions.pdf",
            [
                # A tool the rule does not carry: refused by Odoo's tool loop.
                _tool_call("ir_actions_server_create_vendor_bill_code", "call_bill", {}),
                # A folder that is not named in the P1 prompt: refused by Enterprise.
                _tool_call(MOVE, "call_root", {"folder_id": root.id}),
            ],
        )
        self.assertEqual(document.folder_id, self.inbox)
        self.assertFalse(document.tag_ids)
        self.assertEqual(self.env["account.move"].search_count([]), moves_before)
        self.assertEqual(seen[0]["tools"], [MOVE, ADD_TAGS])
