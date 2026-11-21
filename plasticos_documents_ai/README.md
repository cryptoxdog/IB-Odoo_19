---
auto_generated: false
authority: derived-index
component_id: plasticos_documents_ai
component_name: Plasticos Documents AI
module_version: 19.0.1.0.0
installable: true
auto_install: false
application: false
depends:
  - base
  - plasticos_documents_native
  - ai
  - ai_documents
models_owned: []
models_extended:
  - ir.actions.server
crons: []
---

# Plasticos Documents AI

The front matter above is a derived index. `__manifest__.py` wins on any conflict.

## What it is

A minimal addon (DEC-017) that lets an Odoo AI server action, such as a Documents Auto-Sort rule, run on DeepSeek Flash (`deepseek-flash`, non-thinking) instead of Odoo's default AI model (DEC-016 OPT-B). It is kept apart from `plasticos_documents_native`, which still owns the Documents bridge.

Campaign `ib-odoo-dashboard-command-centers`, TASK-068.

## Installing it does nothing visible

- `auto_install` is `False`. Nothing installs it implicitly.
- Installing or upgrading creates no Auto-Sort rule, no server action, no automation and no cron, and it sends nothing to DeepSeek.
- Every existing AI action keeps Odoo's own provider and model. An action uses DeepSeek only after a system administrator sets **AI Model Override** (`plasticos_llm_model`) to *DeepSeek Flash* on it.
- No real customer, supplier or financial document may be sent to DeepSeek before the operator records the external-data-processing approval (GATE-005). Until then only synthetic documents are used.

## Configuration

| System parameter | Meaning | Default |
| --- | --- | --- |
| `ai.deepseek_key` | DeepSeek API key, set by the operator on each database. Never committed. | none: the action is not run and the error is logged |
| `plasticos_documents_ai.deepseek_file_ttl_seconds` | Lifetime of an uploaded document on DeepSeek, clamped to 3600–2592000 | `3600` (one hour) |
| `plasticos_documents_ai.deepseek_pdf_purpose` | Pin the parsing purpose of uploaded PDFs: `text_recognition` or `rich_layout_recognition` | chosen per PDF, see below |

When the key is missing, the AI action raises *No API key set for provider 'deepseek'*. On an Auto-Sort folder, Enterprise `ai_documents` catches that error and logs it on the document, so the upload itself still succeeds and the document stays where it was put.

## What is sent to DeepSeek, and where

All calls go to `https://api.deepseek.com`, authenticated with `ai.deepseek_key`.

1. `POST /responses`, one call per model turn. The body holds:
   - Odoo's fixed system instruction for AI actions;
   - the action's rendered prompt. For Auto-Sort that is the folder prompt, the document name, tag names and mimetype, the current date and the record reference;
   - the document content (see below);
   - the tool definitions of the action (name, description, JSON schema) and the earlier tool calls and tool results of the same run.

   Fixed settings: `reasoning: {"effort": "none"}` (thinking off), `temperature: 0`, no `strict` on tools, no `user` / `user_id`, no `store`, no `thinking` key.
2. Document content, per file:
   - **Plain text**: sent inline as `input_text`.
   - **Images**: sent inline as a base64 `input_image` data URL. They are not uploaded.
   - **PDF with a usable text layer** (at least 200 letters and digits, mostly readable): only the extracted text is sent, as `input_text`. The PDF itself is not sent.
   - **Any other PDF** (scanned, or a text layer too thin to classify): uploaded to `POST /files` as `file_N.pdf`, without its original name, and referenced by `file_id`. DeepSeek accepts documents only this way. The `purpose` field is sent before `file`.
     - `text_recognition` (text only) is used when the PDF has some text layer.
     - `rich_layout_recognition` (text and figures) is used when it has none, because a scan or photo may need its figures to be identified.
     - An administrator can pin one purpose with the parameter above.
3. `DELETE /files/{id}`, sent for every uploaded file once the run ends, whether it succeeded or failed.

Nothing else is sent: no partner records, e-mail addresses, user identities or attachments other than the document being classified. The original file always stays in Odoo.

## Retention and deletion

- Every upload carries `expires_after[anchor]=created_at` and `expires_after[seconds]` (one hour by default, never more than 30 days). DeepSeek keeps an upload forever when `expires_after` is omitted, so this addon never omits it.
- The file is deleted explicitly after the run. If that deletion fails, a warning naming only the file id is logged, and the file still expires at its `expires_after` time.
- DeepSeek offers no download of an uploaded file or of its parse result.
- The DeepSeek API documentation does not state the data region or how long request bodies are retained. That is part of the GATE-005 operator approval.

## Reliability

- HTTP 429 (concurrency limit, or too many uploads in progress) and 503 are retried up to 3 times. The wait follows `Retry-After` when present, otherwise exponential backoff (2, 4, 8 s, capped at 30 s).
- Timeouts are raised above Odoo's 30 s default: 120 s for `/responses` and 300 s for an upload, which covers the 120 s transfer and 120 s parsing limits.
- Logs name the endpoint, the HTTP status, the attempt and the file id. They never contain the key, request headers, request or response bodies, or document content.

## How it plugs into Odoo

Odoo 19 `ai` supports only `openai` and `google` (`ai/utils/llm_providers.py`, `ai/utils/llm_api_service.py`) and runs every AI server action on the class constants `AI_PROVIDER` / `AI_MODEL`. No Enterprise file is edited.

- `models/ir_actions_server.py` resolves `AI_PROVIDER` / `AI_MODEL` per action. An action whose `plasticos_llm_model` is `deepseek-flash` gets `deepseek` / `deepseek-flash`. Every other action gets Odoo's values through `super()`.
- `services/deepseek_llm_api_service.py` subclasses `LLMApiService` for provider `deepseek` and overrides only provider-specific methods. One constructor hook makes `LLMApiService(env, provider="deepseek")` build that subclass, and every other provider is constructed exactly as before. Response parsing reuses Odoo's Responses parser, so every `function_call` / `function_call_output` item is sent again on each turn, as DeepSeek's stateless API requires.
- `services/deepseek_protocol.py` holds the request, upload, retry and deletion rules with no Odoo import.

## Tests

`tests/test_deepseek_adapter.py` runs offline. It uses synthetic fixtures in `tests/fixtures/` and replaces the HTTP layer with a recorder. Odoo runtime tests run under `odoo --test-enable`. The one live contract probe (UNK-006) uses synthetic documents only, on Staging, with the operator's key. It is not part of the test suite.
