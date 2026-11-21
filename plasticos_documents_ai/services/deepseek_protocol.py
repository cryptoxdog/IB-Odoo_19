"""DeepSeek Responses / Files API contract, free of Odoo imports.

Everything here follows the DeepSeek API documentation read on 2026-11-21
(EVID-012): ``guides/responses_api.md``, ``guides/files_api.md``,
``guides/document_parsing.md``, ``guides/thinking_mode.md``,
``guides/tool_calls.md`` and ``quick_start/rate_limit.md``.

The facts this module encodes:

* Thinking mode is on by default. On the Responses API it is turned off with
  ``reasoning: {"effort": "none"}``. The Chat Completions ``thinking`` key is
  never sent.
* ``strict`` function tools exist only on the ``/beta`` base URL, so ``strict``
  is removed from every tool.
* The API is stateless: ``store`` and ``previous_response_id`` are not supported,
  and every ``function_call`` / ``function_call_output`` item is sent again on
  each turn by the caller.
* Images may be sent inline as a base64 data URL in ``input_image``.
* A document that needs parsing (PDF, Word, PowerPoint) can be referenced only by
  ``file_id`` after ``POST /files``. The ``purpose`` form field must come before
  ``file``. Without ``expires_after`` the upload is kept permanently, so every
  upload carries ``expires_after[anchor]=created_at`` and a bounded
  ``expires_after[seconds]`` (3600 to 2592000), and the file is deleted with
  ``DELETE /files/{id}`` after the classification turn.
* HTTP 429 means the account is over its concurrency limit and is retried with
  backoff.

Nothing in this module logs a key, a header, a request body or a response body.
"""

from __future__ import annotations

import base64
import copy
import logging
import time
from collections.abc import Callable, Iterable
from typing import Any

import requests

_logger = logging.getLogger(__name__)

PROVIDER = "deepseek"
MODEL = "deepseek-flash"
MODEL_LABEL = "DeepSeek Flash"
BASE_URL = "https://api.deepseek.com"
API_KEY_PARAM = "ai.deepseek_key"

# Responses API: thinking disabled so temperature applies and no reasoning
# item has to be returned on tool turns (guides/thinking_mode.md).
REASONING = {"effort": "none"}
TEMPERATURE = 0.0

# Files API (guides/files_api.md).
PURPOSE_TEXT = "text_recognition"
PURPOSE_RICH_LAYOUT = "rich_layout_recognition"
DOCUMENT_PURPOSES = (PURPOSE_TEXT, PURPOSE_RICH_LAYOUT)
FILE_TTL_MIN_SECONDS = 3600
FILE_TTL_MAX_SECONDS = 2592000
FILE_TTL_DEFAULT_SECONDS = FILE_TTL_MIN_SECONDS

# Odoo's own request timeout is 30 s. A /responses call over a parsed document
# can take longer, and a document upload may take 120 s to transfer plus 120 s
# to parse (guides/document_parsing.md "Limits and Errors").
RESPONSES_TIMEOUT_SECONDS = 120
UPLOAD_TIMEOUT_SECONDS = 300
DELETE_TIMEOUT_SECONDS = 30

# 429: account concurrency exceeded or too many document uploads in progress.
# 503: service busy, "retry later" (document_parsing.md).
RETRY_STATUSES = frozenset({429, 503})
MAX_ATTEMPTS = 4
BACKOFF_BASE_SECONDS = 2.0
BACKOFF_CAP_SECONDS = 30.0

# A PDF text layer is used instead of an upload only when it carries enough
# readable text to classify the document on its own.
PDF_TEXT_MIN_ALNUM_CHARS = 200
PDF_TEXT_MIN_ALNUM_RATIO = 0.5

# Wire names (Responses API item and endpoint names, Odoo's text mimetype).
RESPONSES_ENDPOINT = "responses"
FUNCTION_CALL_OUTPUT = "function_call_output"
MIMETYPE_TEXT = "text/plain"
IMAGE_DETAIL = "high"

# Request keys this adapter must never send.
FORBIDDEN_BODY_KEYS = frozenset(
    {"thinking", "user", "user_id", "store", "previous_response_id", "parallel_tool_calls", "metadata"}
)


class DeepSeekError(Exception):
    """A DeepSeek call failed. The message names the endpoint and status only."""

    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


def bounded_file_ttl(seconds: Any) -> int:
    """The upload lifetime in seconds, clamped to the range the Files API accepts."""
    try:
        value = int(seconds)
    except (TypeError, ValueError):
        return FILE_TTL_DEFAULT_SECONDS
    return max(FILE_TTL_MIN_SECONDS, min(FILE_TTL_MAX_SECONDS, value))


def sanitize_tools(tools: Iterable[dict]) -> list[dict]:
    """Function tools without ``strict`` (``strict`` is /beta-only on DeepSeek)."""
    sanitized = []
    for tool in tools:
        clean = copy.deepcopy(tool)
        clean.pop("strict", None)
        if isinstance(clean.get("function"), dict):
            clean["function"].pop("strict", None)
        sanitized.append(clean)
    return sanitized


def pdf_text_is_sufficient(text: str | None) -> bool:
    """True when an extracted PDF text layer is rich enough to classify on its own.

    A scanned PDF has no text layer, or a few stray characters from stamps and
    headers. Those go through the Files API instead.
    """
    if not text:
        return False
    visible = [char for char in text if not char.isspace()]
    if not visible:
        return False
    alnum = sum(1 for char in visible if char.isalnum())
    return alnum >= PDF_TEXT_MIN_ALNUM_CHARS and alnum / len(visible) >= PDF_TEXT_MIN_ALNUM_RATIO


def pdf_upload_purpose(text: str | None, configured: str | None = None) -> str:
    """The Files API ``purpose`` for a PDF whose text layer is not sufficient.

    An administrator may pin one purpose. Otherwise a PDF with a partial text
    layer is mostly text and is OCR'd with ``text_recognition``; a PDF with no
    text layer at all is a scan or a picture, whose identity can depend on its
    figures, so ``rich_layout_recognition`` gives the model the figures too.
    """
    if configured in DOCUMENT_PURPOSES:
        return configured
    if text and any(not char.isspace() for char in text):
        return PURPOSE_TEXT
    return PURPOSE_RICH_LAYOUT


def build_responses_body(
    model: str,
    system_prompts: Iterable[str],
    user_content: list[dict],
    inputs: Iterable[dict] = (),
    tools: Iterable[dict] | None = None,
) -> dict:
    """The ``POST /responses`` body.

    Temperature is always 0 and thinking is always off. ``inputs`` carries the
    earlier ``function_call`` / ``function_call_output`` items in full because the
    API keeps no state between calls.
    """
    body: dict[str, Any] = {
        "model": model,
        "input": [
            {
                "role": "system",
                "content": [{"type": "input_text", "text": prompt} for prompt in system_prompts],
            },
            {"role": "user", "content": user_content},
            *inputs,
        ],
        "reasoning": dict(REASONING),
        "temperature": TEMPERATURE,
    }
    tool_list = sanitize_tools(tools or ())
    if tool_list:
        body["tools"] = tool_list
    return body


def image_content(mimetype: str, value: str) -> dict:
    """An inline base64 image part. ``high`` keeps the original resolution."""
    return dict(type="input_image", image_url=f"data:{mimetype};base64,{value}", detail=IMAGE_DETAIL)


def text_content(text: str) -> dict:
    return dict(type="input_text", text=text)


def file_content(file_id: str) -> dict:
    return dict(type="input_file", file_id=file_id)


def function_call_output(call_id: str, output: str) -> dict:
    return dict(type=FUNCTION_CALL_OUTPUT, call_id=call_id, output=output)


class DeepSeekTransport:
    """HTTP calls to DeepSeek with retry on 429/503 and no payload logging.

    ``request`` and ``sleep`` are injectable so tests run offline.
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = BASE_URL,
        request: Callable[..., requests.Response] | None = None,
        sleep: Callable[[float], None] | None = None,
    ) -> None:
        self._api_key = api_key
        self.base_url = base_url.rstrip("/")
        # Resolved at call time so a test can replace requests.request / time.sleep.
        self._request = request
        self._sleep = sleep

    def _headers(self, json_body: bool) -> dict[str, str]:
        headers = {"Authorization": f"Bearer {self._api_key}"}
        if json_body:
            headers["Content-Type"] = "application/json"
        return headers

    @staticmethod
    def _retry_delay(response: requests.Response | None, attempt: int) -> float:
        if response is not None:
            retry_after = response.headers.get("Retry-After")
            if retry_after is not None:
                try:
                    return min(BACKOFF_CAP_SECONDS, max(0.0, float(retry_after)))
                except ValueError:
                    pass
        return min(BACKOFF_CAP_SECONDS, BACKOFF_BASE_SECONDS * (2 ** (attempt - 1)))

    @staticmethod
    def _error_message(endpoint: str, response: requests.Response) -> str:
        """The API's own error message, never the request or response body."""
        message = ""
        try:
            data = response.json()
        except ValueError:
            data = None
        if isinstance(data, dict) and isinstance(data.get("error"), dict):
            message = str(data["error"].get("message") or "")
        detail = f": {message}" if message else ""
        return f"DeepSeek {endpoint} failed with HTTP {response.status_code}{detail}"

    def call(
        self,
        method: str,
        endpoint: str,
        timeout: float,
        json: dict | None = None,
        files: list | None = None,
    ) -> dict:
        """Call ``endpoint`` and return the decoded JSON response."""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                response = (self._request or requests.request)(
                    method,
                    url,
                    headers=self._headers(json_body=json is not None),
                    json=json,
                    files=files,
                    timeout=timeout,
                )
            except requests.exceptions.RequestException as error:
                # The exception text can carry the URL, never a body; keep only its type.
                raise DeepSeekError(f"DeepSeek {endpoint} unreachable ({type(error).__name__})") from None

            if response.status_code in RETRY_STATUSES and attempt < MAX_ATTEMPTS:
                delay = self._retry_delay(response, attempt)
                _logger.warning(
                    "DeepSeek %s returned HTTP %s; retry %s/%s in %.1fs",
                    endpoint,
                    response.status_code,
                    attempt,
                    MAX_ATTEMPTS - 1,
                    delay,
                )
                (self._sleep or time.sleep)(delay)
                continue
            if response.status_code >= 400:
                raise DeepSeekError(self._error_message(endpoint, response), response.status_code)
            try:
                return response.json()
            except ValueError:
                raise DeepSeekError(f"DeepSeek {endpoint} returned a non-JSON response") from None
        raise DeepSeekError(f"DeepSeek {endpoint} did not succeed after {MAX_ATTEMPTS} attempts")

    def create_response(self, body: dict) -> dict:
        leaked = FORBIDDEN_BODY_KEYS.intersection(body)
        if leaked:
            raise DeepSeekError(f"DeepSeek request carries forbidden keys {sorted(leaked)}")
        return self.call("post", f"/{RESPONSES_ENDPOINT}", RESPONSES_TIMEOUT_SECONDS, json=body)

    def upload_document(self, raw: bytes, filename: str, mimetype: str, purpose: str, ttl_seconds: int) -> str:
        """Upload a document for parsing and return its ``file_id``.

        The multipart fields are an ordered list so ``purpose`` precedes ``file``
        (a document whose ``purpose`` comes after ``file`` is refused with 400).
        """
        if purpose not in DOCUMENT_PURPOSES:
            raise DeepSeekError(f"DeepSeek upload purpose {purpose!r} is not a document purpose")
        fields = [
            ("purpose", (None, purpose)),
            ("expires_after[anchor]", (None, "created_at")),
            ("expires_after[seconds]", (None, str(bounded_file_ttl(ttl_seconds)))),
            ("file", (filename, raw, mimetype)),
        ]
        data = self.call("post", "/files", UPLOAD_TIMEOUT_SECONDS, files=fields)
        file_id = data.get("id") if isinstance(data, dict) else None
        if not file_id:
            raise DeepSeekError("DeepSeek /files returned no file id")
        return file_id

    def delete_file(self, file_id: str) -> bool:
        """Delete an uploaded file. A failure is logged; the upload still expires on its own."""
        try:
            data = self.call("delete", f"/files/{file_id}", DELETE_TIMEOUT_SECONDS)
        except DeepSeekError as error:
            _logger.warning("DeepSeek file %s was not deleted (%s); it expires on its own", file_id, error)
            return False
        return bool(isinstance(data, dict) and data.get("deleted"))


def decode_base64(value: str | bytes) -> bytes:
    return base64.b64decode(value)
