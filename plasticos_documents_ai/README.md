---
auto_generated: false
authority: derived-index
component_id: plasticos_documents_ai
component_name: Plasticos Documents AI
module_version: 19.0.1.2.0
installable: true
auto_install: false
application: false
depends:
  - base
  - plasticos_documents_native
  - ai
  - ai_documents
models_owned:
  - plasticos.documents.ai.autosort
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

The adapter itself fetches and adds nothing else: no partner records, e-mail addresses, user identities or other attachments. The prompt, the document's content and the tool results are sent as they are, so whatever personal data they contain is sent too. The GATE-005 approval has to cover that. The original file always stays in Odoo.

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

## Auto-Sort P1: Inbox master classifier (TASK-071)

`services/autosort_prompts.py` builds the versioned P1 prompt (`P1_PROMPT_VERSION`) under Document AI Prompt Requirements v2.0 (DEC-019). It follows the six-step decision procedure and invariants INV-01..INV-07, and its taxonomy matches `AI_PROMPT_INVENTORY.yaml`.

Activation is explicit and admin-only. A system administrator runs **Documents > Configuration > Auto-Sort (AI) > Activate P1 Inbox Classifier**. The server checks that the user is in `base.group_system`. The action:

1. Refuses activation while any P1 tag is missing. Those tags are the DEC-014 types seeded by TASK-069.
2. Writes the P1 prompt on the Plasticos Inbox folder.
3. Lets Enterprise `ai_documents` create its rule with exactly two tools, *AI: Move To Folder* and *AI: Add Tags*. No bill or invoice creation, activity, code or webhook tool is attached.
4. Sets the rule's AI action to DeepSeek Flash.
5. Posts `prompt_version` in the rule's chatter.

Running the action again with the same version changes nothing. A new prompt version is applied only through this same action. **Deactivate P1 Inbox Classifier** removes the prompt, the rule and the AI action.

Install and upgrade never write a folder prompt or create a rule. An administrator's later edit of the Inbox prompt therefore survives an upgrade. Folder moves are limited to the six Plasticos destination folders named in the prompt. Enterprise enforces this.

The owner activity for review signals belongs to the activity router (TASK-060 / TASK-070), never to the prompt.

## Auto-Sort P2–P7: destination specialists (TASK-073)

`services/autosort_prompts.py` also builds one versioned prompt per destination folder (`SPECIALIST_PROMPT_VERSION`): P2 Bills of Lading, P3 Scale Tickets, P4 Loading Pictures, P5 Orders and Shipping Paperwork (the existing Customer Orders folder), P6 Vendor Bills and financial documents, P7 Compliance. Each follows its `AI_PROMPT_INVENTORY.yaml` entry: specialist invariant, allowed tags, must-not list and acceptance examples.

Every specialist is inactive until a system administrator activates it in **Documents > Configuration > Auto-Sort (AI) > Specialists (P2-P7)**. The administrator picks the specialist and enters the reference of its GATE-006 approval. The server checks the administrator group, refuses a missing reference or a missing tag, and then:

1. Writes the specialist prompt on its folder.
2. Lets Enterprise `ai_documents` create the folder's rule with one tool only, *AI: Add Tags*.
3. Sets the rule's AI action to DeepSeek Flash.
4. Posts `prompt_version` and the GATE-006 reference in the rule's chatter.

**Deactivate** in the same wizard removes that folder's prompt, rule and AI action and leaves the others in place.

When a specialist runs. Enterprise runs every Auto-Sort tool under `ai_documents_skip_autosort`, and the rules trigger on the folder only. So:

- a P1 move into a destination folder never starts that folder's rule;
- a tag added by any rule never starts any rule;
- a specialist runs on a document uploaded straight into its folder, on one a person moves there (for example out of the Inbox after Needs Review), and on one someone sorts with *AI Sort*.

No AI action can start another AI action. The tests count every rule run across all seven rules with adversarial model outputs.

What the application enforces, whatever the prompt says (`models/documents_document.py`). These checks apply only to rules this addon configured:

- A rule adds only the tags of its own prompt.
- Verified is never added.
- A destination specialist may add a type from another family only together with Needs Review. That is the v2.0 refinement conflict.
- A specialist cannot move a document, even if someone edits its rule to grant the move tool.

Two type tags send a document to a person through the TASK-070 bridge. For that reason a specialist adds no second type tag when the document already has a type that fits its folder.

The harness measures each specialist's benefit over P1 alone (`harness.score_specialist`, `--specialists`). It reads each labeled case of the specialist's family as a document arriving in that folder untyped, and compares exact-type accuracy, unnecessary review and unauthorized actions. A specialist without a measured benefit stays inactive. `eval/recorded/harness_fixture_specialists.py` is a hand-written fixture that tests the scorer. It is not a measurement.

## Evaluation and replay harness (TASK-074)

`eval/` scores a prompt version from recorded model outputs, with no Odoo and no network (v2.0 section E).

- `eval/dataset/synthetic_v1.py` is the versioned labeled set: written descriptions of fictional documents covering every v2.0 mandatory case. No real document is stored.
- `eval/harness.py` computes the six v2.0 metrics:
  - auto-routed share;
  - primary-family accuracy among routed documents;
  - human classification intervention;
  - unnecessary review;
  - unauthorized business actions (a tool the rule does not grant, the Verified tag, or a move outside the six prompted folders);
  - human-correction overwrites.

  It also builds a per-type confusion matrix and a regression replay that names every case the previous version got right and the candidate gets wrong. A metric with nothing to measure is reported as unknown (`null`), never as 0.
- `eval/recorded/harness_fixture_*.py` are hand-written recordings that test the scorer. They are not model runs, and no number computed from them describes any model.

Run it:

```bash
python3 plasticos_documents_ai/eval/harness.py --dataset plasticos_documents_ai/eval/dataset/synthetic_v1.py \
    --recorded <candidate recording> --baseline <previous recording>   # .py data module or .json
```

It exits 1 when an output is missing, a mandatory case is absent or the regression replay finds a regression.

Live scoring follows GATE-005. Until then it uses synthetic documents only. After GATE-005 it uses the operator's labeled Staging set (UNK-007). The v2.0 targets stay unmet claims until a representative labeled set has been measured.

## Tests

`tests/test_deepseek_adapter.py` runs offline. It uses synthetic fixtures in `tests/fixtures/` and replaces the HTTP layer with a recorder. Odoo runtime tests run under `odoo --test-enable`. The one live contract probe (UNK-006) uses synthetic documents only, on Staging, with the operator's key. It is not part of the test suite.
