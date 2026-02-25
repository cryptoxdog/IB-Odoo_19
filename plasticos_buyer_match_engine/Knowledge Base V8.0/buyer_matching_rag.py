# ============================================
# Canonical Header (v6.1 RAG Extension)
# ============================================
# File Name: buyer_matching_rag.py
# Version: 6.1.0
# Created: 2026-02-23
# Author: plasticos Dev
# Domain: Plastic Recycling / AI-Augmented ERP
# Purpose: RAG overlay for buyer_matching — adds KB similarity search
#          and context-injected AI prompts. EXTENDS, never replaces.
# Tags: #Odoo19 #RAG #Inherit #BuyerMatching #KBRetrieval
# Depends: Mack_v60_odoo (plastic_ai.buyer_matching, plastic_ai.kb_config,
#           plastic_ai.ai_service)
# External: NONE — uses only odoo.*, json, logging, math, re, requests
# ============================================
"""
RAG Extension for plastic_ai.buyer_matching
--------------------------------------------
What this file does:
  1. Adds a `kb_chunks` model to store pre-chunked KB text with TF-IDF
     term vectors (stored as JSON in a Text field — no numpy, no sklearn).
  2. Inherits `plastic_ai.buyer_matching` and injects two things:
     a) `action_rag_enrich_match()` — retrieves top-K KB chunks relevant
        to the match's polymer/process/region, then calls the existing
        `plastic_ai.ai_service.generate_text()` with those chunks
        injected into the prompt.
     b) `rag_context` / `rag_enrichment_date` fields to store results.
  3. Inherits `plastic_ai.kb_config` to add a chunk-building action
     that reads existing KB YAML/JSON configs and splits them into
     searchable chunks.

What this file does NOT do:
  - Import anything outside the Python stdlib + odoo.*
  - Replace or override any existing method on buyer_matching
  - Require neo4j, openai SDK, sklearn, numpy, or any pip package
"""

import json
import logging
import math
import re
from collections import Counter

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


# ================================================================
# 1. KB Chunk Store — lightweight TF-IDF similarity, zero deps
# ================================================================


class KBChunk(models.Model):
    """Pre-chunked KB text for RAG retrieval.

    Each record is one retrievable 'paragraph' of knowledge.
    Term vectors are stored as JSON so similarity search runs
    entirely inside Python / SQL — no external vector DB.
    """

    _name = "plastic_ai.kb_chunk"
    _description = "KB Chunk for RAG Retrieval"
    _order = "polymer_type, source_key, sequence"

    source_key = fields.Char(
        string="Source Config Key",
        required=True,
        index=True,
        help="plastic_ai.kb_config key this chunk was extracted from",
    )
    polymer_type = fields.Char(string="Polymer Type", index=True, help="HDPE, PP, PET, etc. — NULL means cross-polymer")
    section = fields.Char(string="Section Label", help='e.g. "density_specs", "contamination", "process_fit"')
    sequence = fields.Integer(string="Chunk Sequence", default=0)
    chunk_text = fields.Text(string="Chunk Text", required=True, help="The actual KB content for this chunk")
    term_vector = fields.Text(
        string="Term Vector (JSON)", help='{"term": tf_weight, …} — built by _build_term_vector()'
    )
    doc_norm = fields.Float(
        string="Document L2 Norm",
        digits=(12, 6),
        default=0.0,
        help="Pre-computed L2 norm of term_vector for fast cosine calc",
    )

    # ------ vectorisation (pure Python, no sklearn) ------

    @staticmethod
    def _tokenize(text):
        """Lowercase, strip punctuation, split on whitespace."""
        return re.findall(r"[a-z0-9]+(?:\.[0-9]+)?", text.lower())

    @staticmethod
    def _l2_norm(vec_dict):
        return math.sqrt(sum(v * v for v in vec_dict.values())) or 1e-9

    def _build_term_vector(self):
        """Build a simple TF (log-normalised) vector and store it."""
        for rec in self:
            tokens = KBChunk._tokenize(rec.chunk_text or "")
            if not tokens:
                rec.term_vector = "{}"
                rec.doc_norm = 0.0
                continue
            counts = Counter(tokens)
            max_count = max(counts.values())
            # augmented TF: 0.5 + 0.5 * (count / max_count)
            tf = {t: 0.5 + 0.5 * (c / max_count) for t, c in counts.items()}
            rec.term_vector = json.dumps(tf)
            rec.doc_norm = KBChunk._l2_norm(tf)

    @api.model
    def similarity_search(self, query_text, polymer_type=None, top_k=5):
        """Return top-K chunks most similar to *query_text*.

        Uses cosine similarity on TF vectors.  Not as powerful as
        embeddings, but runs with ZERO external dependencies and is
        surprisingly effective for domain-specific retrieval where
        vocabulary is constrained (polymer names, spec terms, etc.).

        Args:
            query_text (str):  Free-text query
            polymer_type (str): Optional filter (e.g. 'HDPE')
            top_k (int): How many chunks to return

        Returns:
            list[dict]: [{'id', 'chunk_text', 'section', 'score'}, …]
        """
        query_tokens = self._tokenize(query_text)
        if not query_tokens:
            return []

        query_counts = Counter(query_tokens)
        max_qc = max(query_counts.values())
        query_tf = {t: 0.5 + 0.5 * (c / max_qc) for t, c in query_counts.items()}
        query_norm = self._l2_norm(query_tf)

        # Pre-filter by polymer (or cross-polymer chunks)
        domain = [("term_vector", "!=", False), ("term_vector", "!=", "{}")]
        if polymer_type:
            domain.append("|")
            domain.append(("polymer_type", "=", polymer_type.upper()))
            domain.append(("polymer_type", "=", False))

        candidates = self.search(domain)

        scored = []
        for chunk in candidates:
            try:
                doc_tf = json.loads(chunk.term_vector or "{}")
            except json.JSONDecodeError:
                continue
            if not doc_tf:
                continue

            # Cosine similarity = dot(q, d) / (|q| * |d|)
            dot = sum(query_tf.get(t, 0.0) * w for t, w in doc_tf.items())
            d_norm = chunk.doc_norm or self._l2_norm(doc_tf)
            cos_sim = dot / (query_norm * d_norm)

            if cos_sim > 0.01:
                scored.append(
                    {
                        "id": chunk.id,
                        "chunk_text": chunk.chunk_text,
                        "section": chunk.section or "",
                        "source_key": chunk.source_key,
                        "polymer_type": chunk.polymer_type or "",
                        "score": round(cos_sim, 4),
                    }
                )

        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_k]


# ================================================================
# 2. Buyer Matching RAG Extension  (_inherit overlay)
# ================================================================


class BuyerMatchingRAG(models.Model):
    """Extends plastic_ai.buyer_matching with RAG enrichment.

    Adds:
      - rag_context: stores the last injected KB chunks (JSON)
      - rag_enrichment_date: when RAG was last run
      - rag_ai_insight: the AI-generated insight from RAG context
      - action_rag_enrich_match(): button that runs the full pipeline
    """

    _inherit = "plastic_ai.buyer_matching"

    # --- new fields (additive, no conflicts) ---
    rag_context = fields.Text(string="RAG Context (JSON)", help="Top-K KB chunks used in last AI enrichment")
    rag_ai_insight = fields.Text(string="RAG AI Insight", help="AI-generated insight from RAG-augmented prompt")
    rag_enrichment_date = fields.Datetime(string="RAG Enrichment Date")
    rag_chunk_count = fields.Integer(string="KB Chunks Retrieved", default=0)
    rag_top_score = fields.Float(string="Top Chunk Similarity", digits=(5, 4))

    # --- main action ---

    def action_rag_enrich_match(self):
        """Run RAG enrichment pipeline on this buyer match.

        Steps:
          1. Build a query string from the match's polymer, process,
             region, and buyer requirements.
          2. Call kb_chunk.similarity_search() to get top-K chunks.
          3. Inject those chunks into an AI prompt.
          4. Call plastic_ai.ai_service.generate_text() to get insight.
          5. Store results on the record and post to chatter.
        """
        KBChunk = self.env["plastic_ai.kb_chunk"]
        AIService = self.env["plastic_ai.ai_service"]

        for rec in self:
            # ---- Step 1: Build retrieval query ----
            query_parts = []
            if rec.polymer_type:
                query_parts.append(rec.polymer_type)
            if rec.supplier_intake_id:
                si = rec.supplier_intake_id
                if hasattr(si, "material_focus") and si.material_focus:
                    query_parts.append(si.material_focus)
                if hasattr(si, "process_method") and si.process_method:
                    query_parts.append(si.process_method)
                if hasattr(si, "region") and si.region:
                    query_parts.append(si.region)
                if hasattr(si, "material_form") and si.material_form:
                    query_parts.append(str(si.material_form))
            if rec.buyer_quality_requirements:
                query_parts.append(rec.buyer_quality_requirements[:200])
            if rec.buyer_certifications_required:
                query_parts.append(rec.buyer_certifications_required[:200])

            query_text = " ".join(query_parts) or "plastic recycling material matching"

            # ---- Step 2: Similarity search ----
            chunks = KBChunk.similarity_search(
                query_text=query_text,
                polymer_type=rec.polymer_type,
                top_k=5,
            )

            if not chunks:
                rec.message_post(
                    body="<b>⚠️ RAG Enrichment:</b> No relevant KB chunks found. Run <i>Build KB Chunks</i> first.",
                    subtype_xmlid="mail.mt_note",
                )
                continue

            # ---- Step 3: Build RAG-augmented prompt ----
            context_block = "\n\n".join(
                f"[KB:{c['source_key']} / {c['section']}] (relevance {c['score']:.0%})\n{c['chunk_text']}"
                for c in chunks
            )

            prompt = (
                f"You are Mack, a plastic recycling broker AI.\n"
                f"A buyer match is being evaluated:\n"
                f"  Polymer: {rec.polymer_type or 'Unknown'}\n"
                f"  Buyer: {rec.buyer_partner_id.name if rec.buyer_partner_id else 'TBD'}\n"
                f"  Match Score: {rec.match_score:.1f}%\n"
                f"  Technical Validation: {'PASS' if rec.technical_validation_passed else 'REVIEW'}\n\n"
                f"=== RETRIEVED KNOWLEDGE BASE CONTEXT ===\n"
                f"{context_block}\n"
                f"=== END KB CONTEXT ===\n\n"
                f"Using ONLY the KB context above, provide:\n"
                f"1. Key technical considerations for this match\n"
                f"2. Contamination or compliance risks\n"
                f"3. Recommended talking points for the buyer conversation\n"
                f"4. Suggested price positioning based on material specs\n"
                f"Keep it concise (under 300 words). Be specific to the polymer and specs."
            )

            # ---- Step 4: Call AI service (or fallback) ----
            ai_service = AIService.get_default_service()
            if ai_service:
                try:
                    ai_insight = ai_service.generate_text(
                        prompt,
                        context={
                            "polymer_type": rec.polymer_type,
                            "match_score": rec.match_score,
                            "supplier_name": rec.supplier_intake_id.name if rec.supplier_intake_id else "",
                            "buyer_name": rec.buyer_partner_id.name if rec.buyer_partner_id else "",
                        },
                    )
                except Exception as e:
                    _logger.warning("AI service failed, using chunk summary: %s", e)
                    ai_insight = rec._rag_fallback_summary(chunks)
            else:
                ai_insight = rec._rag_fallback_summary(chunks)

            # ---- Step 5: Store and log ----
            rec.write(
                {
                    "rag_context": json.dumps(chunks, indent=2),
                    "rag_ai_insight": ai_insight,
                    "rag_enrichment_date": fields.Datetime.now(),
                    "rag_chunk_count": len(chunks),
                    "rag_top_score": chunks[0]["score"] if chunks else 0.0,
                }
            )

            rec.message_post(
                body=(
                    f"<b>🧠 RAG Enrichment Complete</b><br/>"
                    f"<b>Chunks Retrieved:</b> {len(chunks)}<br/>"
                    f"<b>Top Similarity:</b> {chunks[0]['score']:.0%}<br/>"
                    f"<b>Sources:</b> "
                    f"{', '.join(set(c['source_key'] for c in chunks))}<br/>"
                    f"<hr/><pre>{ai_insight}</pre>"
                ),
                subtype_xmlid="mail.mt_note",
            )

        return True

    def _rag_fallback_summary(self, chunks):
        """Generate a deterministic summary when AI service is unavailable."""
        lines = [
            f"KB Reference Summary ({len(chunks)} chunks retrieved):",
            "",
        ]
        for i, c in enumerate(chunks, 1):
            text_preview = (c["chunk_text"] or "")[:200]
            lines.append(
                f"{i}. [{c['section']}] (score: {c['score']:.0%})\n"
                f"   {text_preview}{'…' if len(c['chunk_text'] or '') > 200 else ''}"
            )
        lines.append("")
        lines.append(
            "⚠ AI service unavailable — showing raw KB excerpts. "
            "Configure an AI service in Settings > AI Services for "
            "synthesized insights."
        )
        return "\n".join(lines)


# ================================================================
# 3. KB Config Extension — chunk builder
# ================================================================


class KBConfigRAGExtension(models.Model):
    """Extends plastic_ai.kb_config to build RAG chunks."""

    _inherit = "plastic_ai.kb_config"

    def action_build_chunks(self):
        """Convert this KB config record into searchable RAG chunks.

        Called from a button on the kb_config form view.
        Splits config_data JSON into chunks by top-level key,
        then builds term vectors for each.
        """
        KBChunkModel = self.env["plastic_ai.kb_chunk"]

        total_created = 0
        for rec in self:
            # Delete existing chunks for this source
            existing = KBChunkModel.search([("source_key", "=", rec.key)])
            if existing:
                existing.unlink()

            try:
                data = json.loads(rec.config_data or "{}")
            except json.JSONDecodeError:
                _logger.warning("Cannot parse config_data for %s", rec.key)
                continue

            if not isinstance(data, dict):
                # Wrap non-dict data
                data = {"content": data}

            # Detect polymer type from key name
            polymer = rec._detect_polymer_from_key()

            seq = 0
            for section_key, section_val in data.items():
                chunk_text = rec._flatten_to_text(section_key, section_val)
                if not chunk_text or len(chunk_text.strip()) < 20:
                    continue

                # Split oversized sections into ~500-char chunks
                sub_chunks = rec._split_chunk(chunk_text, max_chars=800)

                for sub in sub_chunks:
                    chunk = KBChunkModel.create(
                        {
                            "source_key": rec.key,
                            "polymer_type": polymer,
                            "section": section_key,
                            "sequence": seq,
                            "chunk_text": sub,
                        }
                    )
                    chunk._build_term_vector()
                    seq += 1
                    total_created += 1

            rec.message_post(
                body=f"<b>📦 RAG Chunks Built:</b> {seq} chunks created from config <code>{rec.key}</code>",
                subtype_xmlid="mail.mt_note",
            )

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "KB Chunks Built",
                "message": f"{total_created} chunks created and vectorised.",
                "type": "success",
                "sticky": False,
            },
        }

    @api.model
    def action_build_all_chunks(self):
        """Build RAG chunks from ALL active KB configs. Callable via cron."""
        configs = self.search([("active", "=", True)])
        configs.action_build_chunks()
        _logger.info("RAG chunk rebuild complete: %d configs processed", len(configs))

    def _detect_polymer_from_key(self):
        """Try to extract polymer type from the config key name."""
        key_upper = (self.key or "").upper()
        polymers = [
            "HDPE",
            "LDPE",
            "LLDPE",
            "PP",
            "PET",
            "PVC",
            "PS",
            "ABS",
            "PC",
            "PA",
            "HIPS",
            "TPE",
            "TPU",
            "EVA",
            "POM",
            "PMMA",
            "PBT",
            "PPO",
        ]
        for p in polymers:
            if p in key_upper:
                return p
        return None

    def _flatten_to_text(self, key, value, depth=0):
        """Recursively flatten a nested dict/list into readable text."""
        if depth > 6:
            return str(value)[:500]

        if isinstance(value, str):
            return f"{key}: {value}"
        elif isinstance(value, int | float | bool):
            return f"{key}: {value}"
        elif isinstance(value, list):
            parts = [f"{key}:"]
            for i, item in enumerate(value):
                if isinstance(item, dict):
                    sub = self._flatten_to_text(f"item_{i}", item, depth + 1)
                    parts.append(f"  - {sub}")
                else:
                    parts.append(f"  - {item}")
            return "\n".join(parts)
        elif isinstance(value, dict):
            parts = [f"{key}:"]
            for k, v in value.items():
                sub = self._flatten_to_text(k, v, depth + 1)
                parts.append(f"  {sub}")
            return "\n".join(parts)
        else:
            return f"{key}: {value}"

    @staticmethod
    def _split_chunk(text, max_chars=800):
        """Split text into chunks of roughly max_chars, on paragraph boundaries."""
        if len(text) <= max_chars:
            return [text]

        paragraphs = text.split("\n\n")
        chunks = []
        current = ""

        for para in paragraphs:
            if len(current) + len(para) + 2 > max_chars and current:
                chunks.append(current.strip())
                current = para
            else:
                current = current + "\n\n" + para if current else para

        if current.strip():
            chunks.append(current.strip())

        return chunks if chunks else [text[:max_chars]]
