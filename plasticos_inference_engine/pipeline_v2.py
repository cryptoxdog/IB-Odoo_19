"""
plasticos_enrichment/pipeline.py
Orchestrator — ties Sonar, inference, QA, and Odoo writer together.

Now delegates ALL property inference to the standalone
`plasticos_inference` package. This module owns only:
  - Sonar API orchestration
  - Prompt construction
  - QA scoring / gating
  - Odoo writing
  - Telemetry
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

# Inference engine (this addon — no Odoo model dependency)
from . import InferenceEngine, InferenceRequest
from .config import Settings
from .models import (
    EnrichedLead,
    FacilityProfile,
    LeadStatus,
    MaterialProfile,
    PipelineResult,
    QADecision,
    RawLead,
)
from .odoo_writer import OdooWriter
from .prompt_builder import build_system_prompt, build_user_prompt
from .qa_gate import evaluate
from .schema_loader import SchemaEnums, load_schema
from .sonar_client import SonarClient, SonarError
from .telemetry import log_result, log_run_summary

logger = logging.getLogger("plasticos_enrichment.pipeline")


class EnrichmentPipeline:
    """
    Main pipeline. Init once with settings, then call
    .run() or .run_batch() for each enrichment job.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.enums: SchemaEnums = load_schema()
        self.inference: InferenceEngine = InferenceEngine(kb_dir=settings.kb_dir)
        self._writer: OdooWriter | None = None

    # ── Public API ───────────────────────────────────────────

    async def run(self, lead: RawLead) -> PipelineResult:
        """Enrich a single lead through the full pipeline."""
        result = PipelineResult(
            raw=lead,
            started_at=datetime.now(UTC),
        )

        try:
            # 1. Sonar deep research
            enriched, tokens = await self._sonar_enrich(lead)
            result.enriched = enriched
            result.sonar_tokens_used = tokens

            # 2. Run inference on EACH material line
            for mat in enriched.materials:
                inf_request = self._build_inference_request(lead, mat, enriched.company_subtype)
                inf_response = self.inference.infer(inf_request)

                # Apply inferences back to material
                self._apply_inferences(mat, inf_response)
                result.inferences.extend(inf_response.results)

            # 3. QA scoring + gate
            decision = evaluate(result, self.settings)

            # 4. Retry loop
            while decision == QADecision.RETRY:
                result.retries += 1
                logger.info(
                    "Retrying '%s' (attempt %d/%d)",
                    lead.company_name,
                    result.retries,
                    self.settings.qa_max_retries,
                )
                enriched, tokens = await self._sonar_enrich(lead, retry=True)
                result.enriched = enriched
                result.sonar_tokens_used += tokens

                for mat in enriched.materials:
                    inf_req = self._build_inference_request(lead, mat, enriched.company_subtype)
                    inf_resp = self.inference.infer(inf_req)
                    self._apply_inferences(mat, inf_resp)
                    result.inferences.extend(inf_resp.results)

                decision = evaluate(result, self.settings)

            # 5. Write to Odoo (only if accepted)
            if decision == QADecision.ACCEPT:
                await self._write_to_odoo(result)
                result.status = LeadStatus.WRITTEN
            elif decision == QADecision.FLAG:
                result.status = LeadStatus.FLAGGED
            else:
                result.status = LeadStatus.ENRICHED

        except SonarError as exc:
            result.error = str(exc)
            result.status = LeadStatus.ERROR
            logger.error("Sonar failed for '%s': %s", lead.company_name, exc)
        except Exception as exc:
            result.error = str(exc)
            result.status = LeadStatus.ERROR
            logger.exception("Unexpected error for '%s'", lead.company_name)

        result.finished_at = datetime.now(UTC)
        if result.started_at and result.finished_at:
            result.latency_ms = int((result.finished_at - result.started_at).total_seconds() * 1000)

        log_result(result, self.settings)
        return result

    async def run_batch(self, leads: list[RawLead]) -> list[PipelineResult]:
        """Enrich a batch with bounded concurrency."""
        sem = asyncio.Semaphore(self.settings.batch_concurrency)

        async def _bounded(lead: RawLead) -> PipelineResult:
            async with sem:
                return await self.run(lead)

        results = await asyncio.gather(*[_bounded(lead) for lead in leads])
        log_run_summary(list(results), self.settings)
        return list(results)

    # ── Sonar ────────────────────────────────────────────────

    async def _sonar_enrich(self, lead: RawLead, *, retry: bool = False) -> tuple[EnrichedLead, int]:
        """Call Sonar and parse response into EnrichedLead."""
        sys_prompt = build_system_prompt(self.enums)
        usr_prompt = build_user_prompt(
            lead.company_name,
            website=lead.website,
            city=lead.city,
            state=lead.state,
            notes=lead.notes,
        )

        async with SonarClient(self.settings) as client:
            data, tokens = await client.research(sys_prompt, usr_prompt)

        enriched = self._parse_sonar_response(data, lead)
        return enriched, tokens

    # ── Inference bridge ─────────────────────────────────────

    @staticmethod
    def _build_inference_request(
        lead: RawLead,
        mat: MaterialProfile,
        company_subtype: str | None,
    ) -> InferenceRequest:
        """Translate a MaterialProfile into an InferenceRequest."""
        entity = "supplier"
        if company_subtype and company_subtype.lower() in ("buyer",):
            entity = "buyer"
        elif company_subtype and company_subtype.lower() in ("processor", "recycler", "compounder"):
            entity = "supplier"

        return InferenceRequest(
            entity_type=entity,
            polymer=mat.polymer,
            form=mat.form,
            color=mat.color,
            source_type=mat.source_type,
            process_type=mat.origin_process_type,
            origin_sector=mat.origin_sector,
            origin_application=mat.origin_application,
            mfi_value=mat.mfi_value,
            density_value=mat.density_value,
            moisture_ppm=mat.moisture_ppm,
            contamination_pct=mat.contamination_pct,
            has_metal=mat.has_metal,
            has_fr=mat.has_fr,
            filler_type=mat.filler_type,
            filler_pct=mat.filler_pct,
            monthly_volume_lbs=mat.monthly_volume_lbs,
            notes=lead.notes,
        )

    @staticmethod
    def _apply_inferences(mat: MaterialProfile, response) -> None:
        """Write inferred values back to the MaterialProfile."""
        best = response.to_dict()

        # MFI
        mfi = best.get("mfi_range")
        if mfi and mat.mfi_value is None and isinstance(mfi, dict):
            mat.mfi_value = (mfi.get("min", 0) + mfi.get("max", 0)) / 2

        # Density
        dens = best.get("density_range")
        if dens and mat.density_value is None and isinstance(dens, dict):
            mat.density_value = (dens.get("min", 0) + dens.get("max", 0)) / 2

    # ── Sonar response parsing ───────────────────────────────

    @staticmethod
    def _parse_sonar_response(data: dict, lead: RawLead) -> EnrichedLead:
        """Convert raw Sonar JSON into an EnrichedLead."""
        materials = []
        for m in data.get("materials", []):
            if isinstance(m, dict):
                mfi_data = m.get("melt_flow_index") or {}
                materials.append(
                    MaterialProfile(
                        polymer=m.get("polymer"),
                        form=m.get("form"),
                        color=m.get("color"),
                        source_type=m.get("source_type"),
                        mfi_value=(
                            mfi_data.get("typical") or mfi_data.get("min")
                            if isinstance(mfi_data, dict)
                            else mfi_data
                            if isinstance(mfi_data, int | float)
                            else None
                        ),
                        density_value=(m.get("density_value") or (m.get("density", {}) or {}).get("min")),
                        moisture_ppm=m.get("moisture_ppm"),
                        contamination_pct=m.get("contamination_pct"),
                        has_metal=m.get("has_metal"),
                        has_fr=m.get("has_fr"),
                        filler_type=m.get("filler_type"),
                        filler_pct=m.get("filler_pct"),
                        origin_process_type=m.get("origin_process_type"),
                        origin_sector=m.get("origin_sector"),
                        origin_application=m.get("origin_application"),
                        quantity_per_load_lbs=m.get("quantity_per_load_lbs"),
                        loads_per_month=m.get("loads_per_month"),
                        monthly_volume_lbs=m.get("monthly_volume_lbs"),
                        certifications=m.get("certifications", []),
                    )
                )

        facility_data = data.get("facility")
        facility = None
        if isinstance(facility_data, dict):
            facility = FacilityProfile(
                **{k: v for k, v in facility_data.items() if k in FacilityProfile.__annotations__}
            )

        return EnrichedLead(
            company_name=data.get("company_name", lead.company_name),
            company_subtype=data.get("company_subtype"),
            website=data.get("website", lead.website),
            phone=data.get("phone", lead.phone),
            email=data.get("email"),
            street=data.get("street"),
            city=data.get("city", lead.city),
            state=data.get("state", lead.state),
            zip_code=data.get("zip_code"),
            materials=materials,
            facility=facility,
            summary=data.get("summary"),
            sonar_citations=data.get("_citations", []),
        )

    # ── Odoo write ───────────────────────────────────────────

    async def _write_to_odoo(self, result: PipelineResult) -> None:
        """Write accepted lead to Odoo via XML-RPC."""
        if self._writer is None:
            self._writer = OdooWriter(self.settings)
        self._writer.write(result)
