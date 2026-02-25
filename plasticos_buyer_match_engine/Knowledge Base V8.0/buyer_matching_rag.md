<img src="https://r2cdn.perplexity.ai/pplx-full-logo-primary-dark%402x.png" style="height:64px;margin-right:32px"/>

# the whole point was to integrate RAG retrieval (similarity search)              │

│    → relevant KB chunks injected into prompt

can you just make an overlay or module addition instead of a whole new one for buyer matching module?... EXTENDING it... not recreating it or butchering it?

Here's your clean RAG overlay — **one file, pure `_inherit`, zero external dependencies**.

## What `buyer_matching_rag.py` Does

This is a single drop-in file for `Mack_v60_odoo/models/` that extends three existing models without modifying them :

### New Model: `plastic_ai.kb_chunk`

A lightweight chunk store that holds pre-split KB text with TF-IDF term vectors stored as JSON in a `fields.Text` — no numpy, no sklearn, no vector DB . Key method:

- **`similarity_search(query_text, polymer_type, top_k)`** — pure-Python cosine similarity over TF vectors. Tokens are lowercased alphanum, vectors use augmented term frequency (`0.5 + 0.5 * count/max`). Filters by polymer type when provided. Returns top-K scored chunks.


### Extends: `plastic_ai.buyer_matching`

Uses `_inherit = 'plastic_ai.buyer_matching'` — adds 5 fields, touches zero existing ones :


| New Field | Purpose |
| :-- | :-- |
| `rag_context` | JSON of retrieved KB chunks |
| `rag_ai_insight` | AI-generated insight from RAG prompt |
| `rag_enrichment_date` | Last enrichment timestamp |
| `rag_chunk_count` | Number of chunks retrieved |
| `rag_top_score` | Best similarity score |

The **`action_rag_enrich_match()`** button method runs the full pipeline:

1. **Builds a query** from the match's `polymer_type`, supplier intake's `material_focus`, `process_method`, `region`, plus buyer requirements
2. **Calls `similarity_search()`** on `plastic_ai.kb_chunk` to get top-5 relevant chunks
3. **Injects chunks into a prompt** with the `=== RETRIEVED KNOWLEDGE BASE CONTEXT ===` block
4. **Calls the existing `plastic_ai.ai_service.generate_text()`** — the same service already in the repo , which uses `requests.post()` for OpenAI-compatible APIs and falls back to templates
5. **Stores results** on the record and posts to chatter via `message_post`

### Extends: `plastic_ai.kb_config`

Adds **`action_build_chunks()`** — a button that reads any existing KB config record's `config_data` JSON, splits it into ~800-char chunks by section, builds term vectors, and stores them as `plastic_ai.kb_chunk` records . Also adds:

- **`action_build_all_chunks()`** — `@api.model` method callable from `ir.cron` for nightly rebuilds
- **`_detect_polymer_from_key()`** — auto-tags chunks with polymer type based on the config key name


## What You Need to Wire It In

Add to `Mack_v60_odoo/models/__init__.py`:

```python
from . import buyer_matching_rag
```

Add to `Mack_v60_odoo/security/ir.model.access.csv`:

```csv
access_kb_chunk_user,plastic_ai.kb_chunk.user,model_plastic_ai_kb_chunk,mack_v60_odoo.group_mack_user,1,1,0,0
access_kb_chunk_manager,plastic_ai.kb_chunk.manager,model_plastic_ai_kb_chunk,mack_v60_odoo.group_mack_manager,1,1,1,1
```

Add a button to `buyer_matching_form_view.xml`:

```xml
<button name="action_rag_enrich_match" type="object"
        string="🧠 RAG Enrich" class="btn-primary"
        attrs="{'invisible': [('status', '=', 'rejected')]}"/>
```


### What's NOT in This File

- ❌ No `import openai`, `import neo4j`, `import sklearn`, `import numpy`
- ❌ No `dataclass` — everything is `models.Model` / `fields.*`
- ❌ No overridden methods from `buyer_matching.py`
- ❌ No new `__manifest__.py` — it lives inside Mack_v60_odoo

The downloadable file is here. Drop it in `models/`, register it in `__init__.py`, and the existing buyer matching form gets a RAG button without a single line of the original touched.
