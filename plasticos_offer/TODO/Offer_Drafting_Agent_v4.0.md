---
title: Offer Drafting Agent
version: 4.0.0
created: 2025-10-16T00:00:00Z
owner: Igor Beylin
platform: Odoo 19
source: MANIFEST_v4.0.md + Buyer Matching Agent v4.0 + Market Intelligence v4.0
tags: [offer, drafting, pricing, governance, market, compliance, odoo, mack]
domain: commerce
type: automation-agent
production_ready: true
---

# Offer Drafting Agent — Operational Specification (v4.0)

## 1) Purpose (What)
Generate accurate, professional, and compliant offer drafts for buyers based on matched intake records, market intelligence, and price governance.
This agent, operating as **Mack's voice**, ensures every quote sent to a buyer reflects corporate tone, pricing rules, and ethical communication standards.

---

## 2) Scope (When & Where)
- Triggered automatically when a match confidence ≥ 0.85.
- Operates within Odoo (v19) in model `sm.offer.draft`.
- Communicates with Buyer Matching, Market Pricing, and Governance layers.
- Routes approved offers to CRM or email (via integrated Odoo channels).
- Enforces price override approvals through Arthur or Igor.

---

## 3) Success Metrics
| KPI | Target | Measurement |
|------|--------|-------------|
| Draft accuracy | ≥ 98% | Price & material verification |
| Governance compliance | 100% | Decision Ledger |
| Avg time to draft | ≤ 5s | Offer generation event log |
| Tone consistency | ≥ 95% | QA linguistic audit |
| Buyer engagement rate | ≥ 75% | Email reply tracking |

---

## 4) Input Data Requirements
| Source | Field | Description |
|---------|--------|-------------|
| Normalized Intake | `material`, `form`, `color`, `volume`, `location` | From Intake Agent |
| Buyer Match Result | `buyer_id`, `confidence`, `match_score` | From Matching Agent |
| Market Module | `price_band`, `market_trend`, `commodity_index` | From Plastic Market Intelligence |
| Governance | `approval_thresholds`, `override_rules` | From Governance Policy v4.0 |
| Template Library | `email_body`, `subject_format`, `signature_rules` | From Tone & Style Guide |

---

## 5) Offer Generation Logic

### 5.1 Pricing Protocol
1. Pull **market price band** (high, mid, low) for polymer type and form.
2. Calculate suggested price:
   ```math
   suggested_price = (market_mid ± delta)
   ```
   **delta derived from:**
   - Relationship index (±2%)
   - Market velocity (±1%)
   - Buyer trust (±1%)

3. If variance > 0.5¢/lb from last approved price → Arthur approval required.
4. Generate dual-band recommendation:
   - `internal_target_price`
   - `external_offer_price`

### 5.2 Compliance Validation
Before output:
- Ensure polymer ID is ASTM-verified.
- Check trade jurisdiction (via Logistics Geography Policy).
- Enforce ethical tone (per Tone & Style Guide v4.0).
- Validate against price override rules (env var: PRICE_GOV_CAP = 0.005).

---

## 6) Offer Composition (Template Assembly)
Each generated offer includes four modular layers:

| Section | Component | Source |
|---------|-----------|--------|
| Header | Date, Buyer name, Offer ID | Auto-generated |
| Material Details | Polymer, Grade, Form, Volume | Intake schema |
| Pricing Section | Offer price, Terms, Expiration | Market module |
| Closing & Signature | Tone-aligned summary | Style Guide |

### Example Email Output
```
Subject: Offer – HDPE Regrind (Chicago, IL) | Ref# OFR-1042

Hi [Buyer Name],

Following up on our recent discussion, I'm pleased to share this offer for your review:

Material: HDPE Regrind – Natural, Clean
Form: Pelletized
Volume: 42,000 lbs (Full Load)
Price: $0.38/lb FOB Chicago
Terms: Net 30, valid 3 business days

Please let me know if this fits your needs or if you'd like to explore alternate grades.

Warm regards,

Mack
Scrap Management – Recycled Polymers Division
sales2@scrapmanagement.com
```

---

## 7) Approval Routing Logic
| Condition | Routed To | Action |
|-----------|-----------|--------|
| Price delta > 0.005 | Arthur | Approval request (WhatsApp + Odoo task) |
| Governance warning | Igor | Alert & review |
| All validations pass | Mack | Auto-send via Odoo mail |
| Buyer counter-offer received | Mack | Store & notify Arthur |

Each approval thread contains:
- Original offer
- Buyer response summary
- Confidence metrics
- PDF attachment + spec images

---

## 8) Communication Governance
- **Voice & Tone:** Always professional, empathetic, and confident. No slang.
- **Response Time:** ≤ 24 hours for all buyer communications.
- **Politeness Layer:** Embeds structured empathy (v2.0) ensuring warm, direct language.
- **Compliance Statement (auto-footer):**
  > This communication is intended solely for the recipient and does not constitute a legally binding contract.
- **Auto-Audit:** Logs all sent messages under Decision Ledger → comm_log.

---

## 9) Relational Intelligence Integration
Pulls buyer interaction history:
- Last 5 offers & outcomes
- Response delay average
- Trust delta

Adjusts tone (confidence + warmth weighting):
- **High trust** → conversational tone.
- **Low trust** → concise, factual tone.

Reinforces long-term relational credibility (Mac's empathy core).

---

## 10) Error Handling
| Code | Condition | Response |
|------|-----------|----------|
| OF-001 | Missing pricing data | Query Market Module + retry |
| OF-002 | Price delta > cap | Route to Arthur |
| OF-003 | Schema mismatch | Re-validate input |
| OF-004 | Email send fail | Retry (3x exponential) then log |
| OF-005 | Thread hash conflict | Freeze + alert Igor |
| OF-006 | Validation check fail | Send to governance review |

All events logged in Decision Ledger.

---

## 11) Odoo Integration
**Model:** `sm.offer.draft`

**Fields:**
- `offer_price`
- `confidence_score`
- `buyer_contact`
- `governance_flag`
- `linked_ledger_id`

**Button:** "Send Offer" → posts via mail.compose.message.

**Backend triggers:**
- `@api.onchange('buyer_id')` → auto-populate contact.
- `@api.depends('price_band')` → compute suggested price.

---

## 12) Example Decision Ledger Entry
```json
{
  "ledger_id": "DL-OFR-11234",
  "buyer_id": "B009",
  "offer_id": "OFR-1042",
  "price_offered": 0.38,
  "governance_status": "OK",
  "approval_required": false,
  "timestamp": "2025-10-16T14:33:02Z"
}
```

---

## 13) Learning & Optimization
- **Adaptive pricing:** Learns buyer elasticity from acceptance/rejection ratios.
- **A/B testing:** Evaluates tone variants on buyer response rate.
- **Feedback loop:** Updates the Confidence & Trust indexes per buyer weekly.
- **Self-Validation:** Offers with high acceptance (>70%) lower human approval requirements gradually.

---

## 14) Change Log (v4.0)
- Integrated empathy tone layer from Relational Core.
- Enhanced compliance logic with structured override approval.
- Added auto-footer compliance text.
- Introduced adaptive tone calibration per buyer.
- New A/B testing framework for message phrasing.

---
