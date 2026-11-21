"""DeepSeek as a provider of Odoo Enterprise ``ai`` (DEC-016 OPT-B, DEC-017).

Odoo 19 ``ai`` knows two providers. ``LLMApiService.__init__`` refuses any other
name, and ``_request_llm`` dispatches only ``openai`` and ``google``
(``ai/utils/llm_api_service.py:88-98,211-229,524-534``). ``LLMApiService`` is a
plain Python class that Enterprise constructs directly
(``ai/models/ir_actions_server.py:279``), so no Odoo model inheritance reaches it.

This module adds DeepSeek without editing Enterprise:

* ``DeepSeekLLMApiService`` subclasses ``LLMApiService`` and overrides only the
  provider-specific methods. Every other provider still goes to ``super()``.
* ``install_provider_dispatch`` adds one constructor hook to ``LLMApiService`` so
  that ``LLMApiService(env, provider="deepseek")`` builds the subclass. Any other
  provider builds exactly what it built before. The name ``deepseek`` is produced
  only by this addon's ``ir.actions.server`` override, so a database where the
  addon is not installed never reaches the subclass.

What is sent, where, and for how long is documented in the addon README.
"""

from __future__ import annotations

import hashlib
import logging

from odoo import _
from odoo.addons.ai.utils.ai_logging import api_call_logging
from odoo.addons.ai.utils.llm_api_service import LLMApiService
from odoo.exceptions import UserError

from . import deepseek_protocol as protocol

_logger = logging.getLogger(__name__)

FILE_TTL_PARAM = "plasticos_documents_ai.deepseek_file_ttl_seconds"
PDF_PURPOSE_PARAM = "plasticos_documents_ai.deepseek_pdf_purpose"


class DeepSeekLLMApiService(LLMApiService):
    """``LLMApiService`` for provider ``deepseek`` over the Responses API."""

    def __init__(self, env, provider: str = protocol.PROVIDER) -> None:
        if provider != protocol.PROVIDER:
            raise ValueError(f"DeepSeekLLMApiService serves provider {protocol.PROVIDER!r}, not {provider!r}")
        # The parent sets env and validates a provider it knows; the DeepSeek
        # identity and base URL replace its values afterwards.
        super().__init__(env, provider="openai")
        self.provider = protocol.PROVIDER
        self.base_url = protocol.BASE_URL
        self._deepseek_transport = None
        self._deepseek_file_parts: dict[str, dict] = {}
        self._deepseek_uploaded_file_ids: list[str] = []

    # ── Credentials ─────────────────────────────────────────────
    def _get_api_token(self):
        if self.provider != protocol.PROVIDER:
            return super()._get_api_token()
        # sudo: the key is a system parameter the acting user cannot read; it is
        # used only to authenticate this call and is never returned or logged.
        api_key = self.env["ir.config_parameter"].sudo().get_param(protocol.API_KEY_PARAM)
        if not api_key:
            raise UserError(_("No API key set for provider '%s'", protocol.PROVIDER))
        return api_key

    def _transport(self) -> protocol.DeepSeekTransport:
        if self._deepseek_transport is None:
            self._deepseek_transport = protocol.DeepSeekTransport(self._get_api_token(), base_url=self.base_url)
        return self._deepseek_transport

    # ── HTTP ────────────────────────────────────────────────────
    def _request(
        self,
        method,
        endpoint,
        headers,
        body,
        data=None,
        files=None,
        params=None,
        base_url=None,
        timeout=30,
    ):
        if self.provider != protocol.PROVIDER:
            return super()._request(method, endpoint, headers, body, data, files, params, base_url, timeout)
        if endpoint.strip("/") != protocol.RESPONSES_ENDPOINT:
            # DeepSeek serves no embeddings, transcription or realtime endpoint.
            raise UserError(_("DeepSeek does not provide the %s endpoint.", endpoint))
        try:
            return self._transport().create_response(body)
        except protocol.DeepSeekError as error:
            raise UserError(str(error)) from None

    # ── One model turn ──────────────────────────────────────────
    def _request_llm(self, *args, **kwargs):
        if self.provider != protocol.PROVIDER:
            return super()._request_llm(*args, **kwargs)
        return self._request_llm_deepseek(*args, **kwargs)

    def _request_llm_deepseek(
        self,
        llm_model,
        system_prompts,
        user_prompts,
        tools=None,
        files=None,
        schema=None,
        temperature=0.2,
        inputs=(),
        web_grounding=False,
    ):
        """One ``POST /responses`` turn in Odoo's ``_request_llm`` contract.

        ``temperature`` is accepted for signature compatibility and not used:
        the adapter always sends 0 (DEC-016).
        """
        if schema:
            raise UserError(_("Structured output is not supported by the DeepSeek adapter."))
        if web_grounding:
            raise UserError(_("Web grounding is not supported with %s.", protocol.MODEL_LABEL))

        user_content = [protocol.text_content(prompt) for prompt in user_prompts]
        user_content.extend(self._deepseek_file_part(index, file) for index, file in enumerate(files or (), start=1))

        tool_list = [
            {
                "type": "function",
                "name": tool_name,
                "description": tool_description,
                "parameters": tool_parameter_schema,
            }
            for tool_name, (tool_description, __, __, tool_parameter_schema) in (tools or {}).items()
        ]
        body = protocol.build_responses_body(llm_model, system_prompts, user_content, inputs, tool_list)

        with api_call_logging(body["input"], tools) as record_response:
            response, to_call, next_inputs, request_token_usage = self._request_llm_openai_helper(body, tools, inputs)
            if record_response:
                record_response(to_call, response, request_token_usage)
            return response, to_call, next_inputs

    def request_llm(self, *args, **kwargs):
        """Run the tool loop, then delete every file this call uploaded."""
        if self.provider != protocol.PROVIDER:
            return super().request_llm(*args, **kwargs)
        try:
            return super().request_llm(*args, **kwargs)
        finally:
            self._deepseek_delete_uploads()

    def _build_tool_call_response(self, tool_call_id, return_value):
        if self.provider != protocol.PROVIDER:
            return super()._build_tool_call_response(tool_call_id, return_value)
        return protocol.function_call_output(tool_call_id, str(return_value))

    # ── Documents ───────────────────────────────────────────────
    def _deepseek_file_part(self, index: int, file: dict) -> dict:
        """The content part for one of Odoo's prepared files, built once per call.

        The tool loop sends the same files on every turn; a document is uploaded
        on the first turn and its ``file_id`` is reused afterwards.
        """
        mimetype = file["mimetype"]
        value = file["value"]
        digest = hashlib.sha256(value.encode() if isinstance(value, str) else value).hexdigest()
        key = f"{mimetype}:{digest}"
        if key in self._deepseek_file_parts:
            return self._deepseek_file_parts[key]

        if mimetype == protocol.MIMETYPE_TEXT:
            part = protocol.text_content(value)
        elif mimetype.startswith("image/"):
            part = protocol.image_content(mimetype, value)
        elif mimetype == "application/pdf":
            part = self._deepseek_pdf_part(index, protocol.decode_base64(value))
        else:
            raise UserError(_("The DeepSeek adapter cannot send a %s file.", mimetype))
        self._deepseek_file_parts[key] = part
        return part

    def _deepseek_pdf_part(self, index: int, raw: bytes) -> dict:
        """Extracted text when it suffices to classify, otherwise a bounded upload."""
        text = self._deepseek_pdf_text(raw)
        if protocol.pdf_text_is_sufficient(text):
            return protocol.text_content(
                f"Text of document file_{index}.pdf (extracted from its PDF text layer):\n{text}"
            )

        params = self.env["ir.config_parameter"].sudo()
        purpose = protocol.pdf_upload_purpose(text, params.get_param(PDF_PURPOSE_PARAM))
        ttl = protocol.bounded_file_ttl(params.get_param(FILE_TTL_PARAM, protocol.FILE_TTL_DEFAULT_SECONDS))
        try:
            # A generic file name: the original name is not needed by the parser.
            file_id = self._transport().upload_document(raw, f"file_{index}.pdf", "application/pdf", purpose, ttl)
        except protocol.DeepSeekError as error:
            raise UserError(str(error)) from None
        self._deepseek_uploaded_file_ids.append(file_id)
        _logger.info("DeepSeek: uploaded file_%s.pdf for parsing (%s, expires after %ss)", index, purpose, ttl)
        return protocol.file_content(file_id)

    def _deepseek_pdf_text(self, raw: bytes) -> str:
        """The PDF text layer through Odoo's own attachment indexer, or ``""``."""
        try:
            text = self.env["ir.attachment"]._index(raw, "application/pdf")
        except Exception as error:  # noqa: BLE001 - any indexer failure means "no usable text layer"
            _logger.info("DeepSeek: PDF text layer unavailable (%s); the PDF is uploaded", type(error).__name__)
            return ""
        return text if isinstance(text, str) else ""

    def _deepseek_delete_uploads(self) -> None:
        if not self._deepseek_uploaded_file_ids:
            return
        transport = self._transport()
        while self._deepseek_uploaded_file_ids:
            transport.delete_file(self._deepseek_uploaded_file_ids.pop(0))
        self._deepseek_file_parts.clear()


_DISPATCH_FLAG = "_plasticos_deepseek_dispatch"


def install_provider_dispatch() -> None:
    """Make ``LLMApiService(env, provider="deepseek")`` build ``DeepSeekLLMApiService``.

    Idempotent. Construction for every other provider is unchanged.
    """
    if getattr(LLMApiService, _DISPATCH_FLAG, False):
        return
    previous_new = LLMApiService.__new__

    def __new__(cls, *args, **kwargs):
        provider = kwargs.get("provider", args[1] if len(args) > 1 else None)
        if cls is LLMApiService and provider == protocol.PROVIDER:
            cls = DeepSeekLLMApiService
        if previous_new is object.__new__:
            return object.__new__(cls)
        return previous_new(cls, *args, **kwargs)

    LLMApiService.__new__ = staticmethod(__new__)
    setattr(LLMApiService, _DISPATCH_FLAG, True)
