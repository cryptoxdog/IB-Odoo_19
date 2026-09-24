"""Preserve existing web-lead provider choices when role fields are introduced."""

from __future__ import annotations

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Backfill new role-scoped fields only when an existing value is absent."""
    cr.execute(
        """
        UPDATE plasticos_web_lead_config
           SET text_inference_provider = COALESCE(NULLIF(text_inference_provider, ''), llm_primary_provider, 'openai'),
               vision_inference_provider = COALESCE(NULLIF(vision_inference_provider, ''), llm_primary_provider, 'openai'),
               economic_inference_provider = COALESCE(NULLIF(economic_inference_provider, ''), llm_primary_provider, 'openai'),
               openai_economic_model = COALESCE(NULLIF(openai_economic_model, ''), openai_model, 'gpt-4o'),
               anthropic_vision_model = COALESCE(NULLIF(anthropic_vision_model, ''), anthropic_model, 'claude-sonnet-4-20250514'),
               anthropic_economic_model = COALESCE(NULLIF(anthropic_economic_model, ''), anthropic_model, 'claude-sonnet-4-20250514'),
               anthropic_transport = COALESCE(NULLIF(anthropic_transport, ''), 'anthropic_messages'),
               anthropic_base_url = COALESCE(NULLIF(anthropic_base_url, ''), 'https://api.anthropic.com'),
               mistral_vision_model = COALESCE(NULLIF(mistral_vision_model, ''), mistral_model, 'mistral-large-latest'),
               mistral_economic_model = COALESCE(NULLIF(mistral_economic_model, ''), mistral_model, 'mistral-large-latest'),
               mistral_base_url = COALESCE(NULLIF(mistral_base_url, ''), 'https://api.mistral.ai/v1'),
               reusable_item_hot_min_lbs = COALESCE(reusable_item_hot_min_lbs, 8000),
               reusable_item_policy_codes = COALESCE(NULLIF(reusable_item_policy_codes, ''), 'PLASTIC_PALLETS|PALLETS|TOTES|CRATES')
        """
    )
    _logger.info("plasticos_web_leads 19.0.2.7.0 post-migrate: role provider configuration backfilled")
