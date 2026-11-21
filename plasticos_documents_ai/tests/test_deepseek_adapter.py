"""AC-068: the DeepSeek adapter's request contract, offline on synthetic fixtures.

No test reaches the network. ``requests.request`` is replaced by a recorder that
answers from ``tests/fixtures`` (shapes from the DeepSeek API docs, EVID-012), and
the retry sleep is replaced so a 429 costs no wall time.
"""

import base64
import copy
import json
import re
from pathlib import Path
from unittest.mock import patch

from odoo.addons.ai.utils.llm_api_service import LLMApiService
from odoo.addons.ai_fields.tools import ai_field_insert
from odoo.addons.plasticos_documents_ai.services import deepseek_protocol as protocol
from odoo.addons.plasticos_documents_ai.services.deepseek_llm_api_service import (
    FILE_TTL_PARAM,
    PDF_PURPOSE_PARAM,
    DeepSeekLLMApiService,
)
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged

FIXTURES = Path(__file__).parent / "fixtures"
SYNTHETIC_KEY = "synthetic-test-key-not-a-secret"
DOC_MARKER = "SYNTHETIC-DOC-MARKER-7731"
SYNTHETIC_TEXT = (DOC_MARKER + " Straight Bill of Lading. Shipper Example Recycler. Consignee Example Mill. ") * 5
SYNTHETIC_PDF = b"%PDF-1.4\n% synthetic scanned page, no text layer\n%%EOF\n"


def _fixture(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


class FakeResponse:
    def __init__(self, status_code, payload, headers=None):
        self.status_code = status_code
        self._payload = payload
        self.headers = headers or {}

    def json(self):
        return copy.deepcopy(self._payload)


class Recorder:
    """Stands in for ``requests.request``; answers queued fixtures in order."""

    def __init__(self, answers):
        self.answers = list(answers)
        self.calls = []

    def __call__(self, method, url, headers=None, json=None, files=None, timeout=None, **_kwargs):
        self.calls.append(
            {
                "method": method,
                "url": url,
                "headers": headers,
                "json": copy.deepcopy(json),
                "files": files,
                "timeout": timeout,
            }
        )
        if not self.answers:
            raise AssertionError(f"unexpected DeepSeek call {method} {url}")
        return self.answers.pop(0)

    def bodies(self, endpoint):
        return [call["json"] for call in self.calls if call["url"].endswith(endpoint) and call["json"] is not None]


@tagged("post_install", "-at_install", "plasticos_documents_ai")
class TestDeepSeekAdapter(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.params = cls.env["ir.config_parameter"].sudo()
        cls.params.set_param(protocol.API_KEY_PARAM, SYNTHETIC_KEY)

    def _run(self, answers, **kwargs):
        recorder = Recorder(answers)
        with (
            patch.object(protocol.requests, "request", recorder),
            patch.object(protocol.time, "sleep", lambda _seconds: None),
        ):
            service = LLMApiService(self.env, provider=protocol.PROVIDER)
            result = service.request_llm(protocol.MODEL, ["synthetic system"], ["synthetic user"], **kwargs)
        return result, recorder

    # ── Provider registration ───────────────────────────────────
    def test_provider_is_selectable_and_default_actions_are_untouched(self):
        field = self.env["ir.actions.server"]._fields["plasticos_llm_model"]
        self.assertIn((protocol.MODEL, protocol.MODEL_LABEL), field.selection)

        model = self.env["ir.model"]._get_id("documents.document")
        plain = self.env["ir.actions.server"].create(
            {"name": "Synthetic plain AI action", "model_id": model, "state": "ai"}
        )
        deepseek = plain.copy({"name": "Synthetic DeepSeek AI action", "plasticos_llm_model": protocol.MODEL})
        self.assertEqual((plain.AI_PROVIDER, plain.AI_MODEL), ("openai", "gpt-4.1"))
        self.assertEqual((deepseek.AI_PROVIDER, deepseek.AI_MODEL), (protocol.PROVIDER, protocol.MODEL))

        self.assertIsInstance(LLMApiService(self.env, provider=protocol.PROVIDER), DeepSeekLLMApiService)
        self.assertIs(type(LLMApiService(self.env, provider="openai")), LLMApiService)
        self.assertIs(type(LLMApiService(self.env)), LLMApiService)

    # ── Request body ────────────────────────────────────────────
    def test_every_request_is_non_thinking_temperature_zero_without_strict_or_user(self):
        tools = {
            "synthetic_tool": (
                "Synthetic tool",
                True,
                lambda arguments: ("ok", None),
                {"type": "object", "properties": {"x": {"type": "string"}}, "required": []},
            )
        }
        result, recorder = self._run([FakeResponse(200, _fixture("response_message.json"))], tools=tools)
        self.assertEqual(result, ["done"])

        (body,) = recorder.bodies("/responses")
        self.assertEqual(recorder.calls[0]["url"], f"{protocol.BASE_URL}/responses")
        self.assertEqual(body["model"], protocol.MODEL)
        self.assertEqual(body["reasoning"], {"effort": "none"})
        self.assertEqual(body["temperature"], 0)
        for key in ("thinking", "user", "user_id", "store", "parallel_tool_calls", "text"):
            self.assertNotIn(key, body)
        self.assertEqual([tool["name"] for tool in body["tools"]], ["synthetic_tool"])
        self.assertNotIn("strict", json.dumps(body["tools"]))
        self.assertGreaterEqual(recorder.calls[0]["timeout"], protocol.RESPONSES_TIMEOUT_SECONDS)
        self.assertEqual(recorder.calls[0]["headers"]["Authorization"], f"Bearer {SYNTHETIC_KEY}")

    def test_sanitize_tools_strips_strict_at_both_levels(self):
        tools = [
            {"type": "function", "name": "a", "strict": True, "parameters": {}},
            {"type": "function", "function": {"name": "b", "strict": True}},
        ]
        cleaned = protocol.sanitize_tools(tools)
        self.assertNotIn("strict", json.dumps(cleaned))
        self.assertTrue(tools[0]["strict"], "the caller's tools are not mutated")

    def test_a_forbidden_key_is_refused_before_sending(self):
        transport = protocol.DeepSeekTransport(SYNTHETIC_KEY, request=Recorder([]))
        with self.assertRaises(protocol.DeepSeekError):
            transport.create_response({"model": protocol.MODEL, "input": [], "thinking": {"type": "disabled"}})

    # ── Tool loop ───────────────────────────────────────────────
    def test_function_call_round_trip_resends_full_history(self):
        calls = []

        def add_tags(arguments):
            calls.append(arguments)
            return "Tag(s) BOL added", None

        tools = {
            "ir_actions_server_add_tags": (
                "Add the tags on the document",
                True,
                add_tags,
                {"type": "object", "properties": {"tag_names": {"type": "array"}}, "required": ["tag_names"]},
            )
        }
        answers = [
            FakeResponse(200, _fixture("response_function_call.json")),
            FakeResponse(200, _fixture("response_message.json")),
        ]
        _result, recorder = self._run(answers, tools=tools)

        self.assertEqual(calls, [{"tag_names": ["BOL"]}])
        first, second = recorder.bodies("/responses")
        self.assertEqual(len(first["input"]), 2)
        call_item, output_item = second["input"][2:]
        self.assertEqual(call_item["type"], "function_call")
        self.assertEqual(call_item["call_id"], "call_synthetic_0001")
        self.assertEqual(
            output_item,
            {"type": "function_call_output", "call_id": "call_synthetic_0001", "output": "Tag(s) BOL added"},
        )
        self.assertEqual(second["reasoning"], {"effort": "none"})

    # ── Documents ───────────────────────────────────────────────
    def _pdf_file(self):
        return {
            "mimetype": "application/pdf",
            "value": base64.b64encode(SYNTHETIC_PDF).decode(),
            "file_ref": "<file_#1>",
        }

    def test_text_rich_pdf_is_sent_as_input_text_and_not_uploaded(self):
        with patch.object(DeepSeekLLMApiService, "_deepseek_pdf_text", return_value=SYNTHETIC_TEXT):
            _result, recorder = self._run(
                [FakeResponse(200, _fixture("response_message.json"))], files=[self._pdf_file()]
            )
        self.assertEqual([call["url"].rsplit("/", 1)[-1] for call in recorder.calls], ["responses"])
        user_content = recorder.bodies("/responses")[0]["input"][1]["content"]
        self.assertEqual(user_content[-1]["type"], "input_text")
        self.assertIn(DOC_MARKER, user_content[-1]["text"])
        self.assertNotIn("input_file", json.dumps(user_content))

    def test_scanned_pdf_is_uploaded_with_bounded_expiry_referenced_by_id_and_deleted(self):
        answers = [
            FakeResponse(200, _fixture("file_uploaded.json")),
            FakeResponse(200, _fixture("response_message.json")),
            FakeResponse(200, _fixture("file_deleted.json")),
        ]
        with patch.object(DeepSeekLLMApiService, "_deepseek_pdf_text", return_value=""):
            _result, recorder = self._run(answers, files=[self._pdf_file()])

        upload, respond, delete = recorder.calls
        self.assertEqual((upload["method"], upload["url"]), ("post", f"{protocol.BASE_URL}/files"))
        fields = [name for name, _value in upload["files"]]
        self.assertEqual(fields, ["purpose", "expires_after[anchor]", "expires_after[seconds]", "file"])
        form = dict(upload["files"])
        self.assertEqual(form["purpose"], (None, protocol.PURPOSE_RICH_LAYOUT))
        self.assertEqual(form["expires_after[anchor]"], (None, "created_at"))
        self.assertEqual(form["expires_after[seconds]"], (None, str(protocol.FILE_TTL_DEFAULT_SECONDS)))
        self.assertEqual(form["file"][0], "file_1.pdf")
        self.assertGreaterEqual(upload["timeout"], protocol.UPLOAD_TIMEOUT_SECONDS)

        self.assertIn(
            {"type": "input_file", "file_id": "file-api-synthetic0001"}, respond["json"]["input"][1]["content"]
        )
        self.assertNotIn("file_data", json.dumps(respond["json"]))
        self.assertEqual(
            (delete["method"], delete["url"]), ("delete", f"{protocol.BASE_URL}/files/file-api-synthetic0001")
        )

    def test_upload_lifetime_is_clamped_and_purpose_can_be_pinned(self):
        self.params.set_param(FILE_TTL_PARAM, "99999999")
        self.params.set_param(PDF_PURPOSE_PARAM, protocol.PURPOSE_TEXT)
        answers = [
            FakeResponse(200, _fixture("file_uploaded.json")),
            FakeResponse(200, _fixture("response_message.json")),
            FakeResponse(200, _fixture("file_deleted.json")),
        ]
        with patch.object(DeepSeekLLMApiService, "_deepseek_pdf_text", return_value=""):
            _result, recorder = self._run(answers, files=[self._pdf_file()])
        form = dict(recorder.calls[0]["files"])
        self.assertEqual(form["expires_after[seconds]"], (None, str(protocol.FILE_TTL_MAX_SECONDS)))
        self.assertEqual(form["purpose"], (None, protocol.PURPOSE_TEXT))
        self.assertEqual(protocol.bounded_file_ttl("12"), protocol.FILE_TTL_MIN_SECONDS)
        self.assertEqual(protocol.bounded_file_ttl("not a number"), protocol.FILE_TTL_DEFAULT_SECONDS)

    def test_failed_turn_still_sends_delete(self):
        recorder = Recorder(
            [
                FakeResponse(200, _fixture("file_uploaded.json")),
                FakeResponse(400, {"error": {"message": "synthetic bad request"}}),
                FakeResponse(200, _fixture("file_deleted.json")),
            ]
        )
        with (
            patch.object(protocol.requests, "request", recorder),
            patch.object(DeepSeekLLMApiService, "_deepseek_pdf_text", return_value=""),
            self.assertRaises(UserError),
        ):
            LLMApiService(self.env, provider=protocol.PROVIDER).request_llm(
                protocol.MODEL, ["s"], ["u"], files=[self._pdf_file()]
            )
        self.assertEqual(recorder.calls[-1]["method"], "delete")

    def test_images_are_inline_base64(self):
        image = {"mimetype": "image/png", "value": "aW1hZ2U=", "file_ref": "<file_#1>"}
        _result, recorder = self._run([FakeResponse(200, _fixture("response_message.json"))], files=[image])
        part = recorder.bodies("/responses")[0]["input"][1]["content"][-1]
        self.assertEqual(part["type"], "input_image")
        self.assertEqual(part["image_url"], "data:image/png;base64,aW1hZ2U=")

    # ── Reliability ─────────────────────────────────────────────
    def test_429_is_retried_with_backoff(self):
        sleeps = []
        recorder = Recorder(
            [
                FakeResponse(429, _fixture("error_rate_limited.json"), headers={"Retry-After": "1"}),
                FakeResponse(429, _fixture("error_rate_limited.json")),
                FakeResponse(200, _fixture("response_message.json")),
            ]
        )
        with (
            patch.object(protocol.requests, "request", recorder),
            patch.object(protocol.time, "sleep", sleeps.append),
        ):
            result = LLMApiService(self.env, provider=protocol.PROVIDER).request_llm(protocol.MODEL, ["s"], ["u"])
        self.assertEqual(result, ["done"])
        self.assertEqual(len(recorder.calls), 3)
        self.assertEqual(sleeps, [1.0, protocol.BACKOFF_BASE_SECONDS * 2])

    def test_429_exhaustion_raises_a_clean_error(self):
        recorder = Recorder([FakeResponse(429, _fixture("error_rate_limited.json"))] * protocol.MAX_ATTEMPTS)
        with (
            patch.object(protocol.requests, "request", recorder),
            patch.object(protocol.time, "sleep", lambda _seconds: None),
            self.assertRaisesRegex(UserError, "HTTP 429"),
        ):
            LLMApiService(self.env, provider=protocol.PROVIDER).request_llm(protocol.MODEL, ["s"], ["u"])
        self.assertEqual(len(recorder.calls), protocol.MAX_ATTEMPTS)

    # ── Missing key on an Auto-Sort upload ──────────────────────
    def _autosort_action(self, folder):
        model = self.env["ir.model"]._get_id("documents.document")
        return self.env["ir.actions.server"].create(
            {
                "name": "Synthetic DeepSeek Auto-Sort",
                "model_id": model,
                "state": "ai",
                "ai_autosort_folder_id": folder.id,
                "plasticos_llm_model": protocol.MODEL,
                "ai_tool_ids": [self.env.ref("ai_documents.ir_actions_server_add_tags").id],
                "ai_action_prompt": f"<p>Classify the synthetic document {ai_field_insert('attachment_id', 'Content')}</p>",
            }
        )

    def _synthetic_document(self, folder):
        return self.env["documents.document"].create(
            {
                "name": "synthetic_scan.pdf",
                "folder_id": folder.id,
                "datas": base64.b64encode(SYNTHETIC_PDF),
                "mimetype": "application/pdf",
            }
        )

    def test_missing_key_is_logged_without_failing_the_upload(self):
        self.params.set_param(protocol.API_KEY_PARAM, False)
        folder = self.env["documents.document"].create({"name": "Synthetic sort folder", "type": "folder"})
        action = self._autosort_action(folder)
        document = self._synthetic_document(folder)
        recorder = Recorder([])
        with (
            patch.object(protocol.requests, "request", recorder),
            self.assertLogs("odoo.addons.ai_documents", level="ERROR") as logs,
        ):
            action._ai_action_run(document)
        self.assertEqual(recorder.calls, [], "nothing is sent without a key")
        self.assertIn("No API key set for provider 'deepseek'", "\n".join(logs.output))
        self.assertTrue(document.exists())
        self.assertEqual(document.folder_id, folder)

    # ── Log and fixture hygiene ─────────────────────────────────
    def test_no_key_or_document_payload_in_logs(self):
        folder = self.env["documents.document"].create({"name": "Synthetic sort folder", "type": "folder"})
        action = self._autosort_action(folder)
        document = self._synthetic_document(folder)
        recorder = Recorder(
            [
                FakeResponse(429, _fixture("error_rate_limited.json")),
                FakeResponse(200, _fixture("file_uploaded.json")),
                FakeResponse(200, _fixture("response_function_call.json")),
                FakeResponse(200, _fixture("response_message.json")),
                FakeResponse(200, _fixture("file_deleted.json")),
            ]
        )
        # A partial text layer that carries the marker but is too thin to classify.
        with (
            patch.object(protocol.requests, "request", recorder),
            patch.object(protocol.time, "sleep", lambda _seconds: None),
            patch.object(DeepSeekLLMApiService, "_deepseek_pdf_text", return_value=DOC_MARKER),
            self.assertLogs("odoo", level="DEBUG") as logs,
        ):
            action._ai_action_run(document)

        output = "\n".join(logs.output)
        self.assertNotIn(SYNTHETIC_KEY, output)
        self.assertNotIn(DOC_MARKER, output)
        self.assertNotIn(base64.b64encode(SYNTHETIC_PDF).decode(), output)
        self.assertIn("BOL", document.tag_ids.mapped("name"))
        self.assertEqual(recorder.calls[-1]["method"], "delete")
        self.assertEqual(dict(recorder.calls[1]["files"])["purpose"], (None, protocol.PURPOSE_TEXT))

    def test_fixtures_hold_no_key_and_no_real_document(self):
        key_shape = re.compile(r"sk-[A-Za-z0-9]{16,}")
        for path in FIXTURES.iterdir():
            text = path.read_text(encoding="utf-8")
            self.assertIsNone(key_shape.search(text), path.name)
            self.assertNotIn("file_data", text, path.name)
            if path.suffix == ".json":
                self.assertIn("synthetic", text.lower(), f"{path.name} must be visibly synthetic")


@tagged("post_install", "-at_install", "plasticos_documents_ai")
class TestInstallIsInert(TransactionCase):
    """Installing the addon sends nothing and creates no Auto-Sort rule (GATE-005)."""

    def test_module_data_holds_no_rule_ai_action_or_cron(self):
        data = self.env["ir.model.data"].search([("module", "=", "plasticos_documents_ai")])
        self.assertFalse({"base.automation", "ir.cron"} & set(data.mapped("model")))
        actions = self.env["ir.actions.server"].browse(
            data.filtered(lambda d: d.model == "ir.actions.server").mapped("res_id")
        )
        # Only the explicit administrator buttons (TASK-071); none of them is an AI action.
        self.assertTrue(all(action.state == "code" for action in actions))
        self.assertFalse(actions.filtered("ai_autosort_folder_id"))

    def test_no_action_is_switched_to_deepseek_and_inbox_has_no_prompt(self):
        self.assertFalse(self.env["ir.actions.server"].sudo().search([("plasticos_llm_model", "!=", False)]))
        inbox = self.env.ref("plasticos_documents_native.folder_plasticos_inbox")
        self.assertFalse(inbox.sudo().ai_sort_prompt)
        self.assertFalse(self.env["base.automation"].sudo().search([("ai_autosort_folder_id", "=", inbox.id)]))

    def test_manifest_never_auto_installs(self):
        module = self.env["ir.module.module"].search([("name", "=", "plasticos_documents_ai")])
        self.assertFalse(module.auto_install)
