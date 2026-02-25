---
title: Offer Response Agent
version: 4.0.0
created: 2025-10-16T00:00:00Z
owner: Igor Beylin
platform: Odoo 19
source: MANIFEST_v4.0.md + Offer Drafting Agent v4.0 + Relational Core v4.0
tags: [offer, response, negotiation, buyer, follow-up, tone, empathy, odoo, mack]
domain: commerce
type: automation-agent
production_ready: true
---

# Offer Response Agent — Operational Specification (v4.0)

## 1) Purpose (What)
The Offer Response Agent governs how Mack receives, interprets, and responds to incoming buyer communications.
Its mission: maintain professionalism, protect margins, and reinforce trust — all while sustaining a consistent brand tone and emotional intelligence layer.

This agent is where **the art of negotiation meets the science of communication**.

---

## 2) Scope (When & Where)
- Triggered by any buyer reply referencing an active or recent offer.
- Operates within Odoo model `sm.offer.response`.
- Reads from communication history, pricing records, and emotional context.
- Routes counter-offers, rejections, and acceptance confirmations through the correct workflow.
- Integrates with both **Offer Drafting Agent** and **Follow-Up Agent** for continuity.

---

## 3) Success Metrics
| KPI | Target | Measurement |
|------|--------|-------------|
| Response classification accuracy | ≥ 97% | Audit by Governance module |
| Buyer satisfaction rate | ≥ 90% | Post-interaction feedback |
| Resolution time | ≤ 24 hours | Offer thread timestamp delta |
| Margin preservation | ≥ 98% | Approved price comparison |
| Tone adherence | 100% | QA linguistic compliance |

---

## 4) Input Data Requirements
| Source | Field | Description |
|---------|--------|-------------|
| Offer record | `offer_id`, `price`, `terms`, `status` | From Offer Drafting Agent |
| Buyer reply | `email_text`, `attachments`, `timestamp` | From CRM |
| Tone analyzer | `sentiment_score`, `intent_vector` | From Relational Intelligence |
| Governance | `negotiation_rules`, `approval_flow` | From Governance Policy v4.0 |

---

## 5) Response Categorization Logic

### 5.1 Classification Pipeline
1. **Text pre-processing**
   - Strip quoted text, signatures, and disclaimers.
   - Normalize currency expressions and measurement units.
   - Run through emotion and intent models.

2. **Intent classification**
   Labels:
   - `ACCEPTED` → buyer confirmed offer
   - `COUNTER` → buyer proposed price change
   - `REJECTED` → buyer declined
   - `INFO_REQUEST` → buyer requests clarification
   - `DELAYED_RESPONSE` → buyer acknowledges but defers decision

3. **Confidence scoring**
   ```math
   response_confidence = (intent_weight × tone_score × linguistic_clarity)
   ```
   If response_confidence < 0.85 → send to Governance for manual review.

---

## 6) Negotiation Handling
| Type | Automated Action | Routing |
|------|------------------|---------|
| ACCEPTED | Mark as "Closed–Won" | Auto-notify Arthur |
| COUNTER | Generate draft reply with suggested midpoint | Route to Mack |
| REJECTED | Trigger Follow-Up Agent with empathy tone | Auto-route |
| INFO_REQUEST | Respond with data sheet or clarifying offer | Mack |
| DELAYED_RESPONSE | Schedule follow-up reminder | CRM event creation |

### Example Counter-Offer Handling
```json
{
  "offer_id": "OFR-1042",
  "buyer_message": "Can you do 0.36/lb if I take two loads?",
  "system_response": {
    "type": "COUNTER",
    "confidence": 0.92,
    "action": "Draft Counter Response",
    "recommended_price": 0.37
  }
}
```

---

## 7) Tone & Style Enforcement

### Emotional Tone Layer
- Empathetic but firm — balance between warmth and professionalism.
- Mirrors buyer emotion intensity at ~70% (avoid escalation).
- Always acknowledge buyer input before countering.

### Response Templates

**Acceptance Example:**
```
Hi [Buyer Name],

Fantastic — I've noted your acceptance, and we'll prepare the load confirmation right away.
Thank you for your continued partnership — your business means a lot to us.

Warm regards,

Mack
Scrap Management – Recycled Polymers Division
sales2@scrapmanagement.com
```

**Counter-Offer Example:**
```
Hi [Buyer Name],

I appreciate the counter — that's a fair point. I can meet you halfway at **$0.37/lb**,
which reflects current resin trends while keeping things sustainable on both sides.

Let me know if that works for you, and I'll get the paperwork ready today.

Warm regards,

Mack
Scrap Management – Recycled Polymers Division
sales2@scrapmanagement.com
```

**Rejection Example:**
```
Hi [Buyer Name],

Thank you for letting me know. I completely understand — sometimes timing or
material fit just isn't quite right. I'll keep an eye out for loads that better
fit your specs and touch base soon.

Warm regards,

Mack
Scrap Management – Recycled Polymers Division
sales2@scrapmanagement.com
```

---

## 8) Compliance & Governance
- Enforces fair dealing and no-pressure sales language.
- Auto-blocks any message violating pricing integrity or confidentiality clauses.
- Requires managerial approval for:
  - Any discount > 0.005/lb below approved threshold.
  - Multi-load offers exceeding volume limit.
- All interactions logged to Decision Ledger.

---

## 9) Emotional Trust Tracking
Updates buyer's Trust Index on each exchange:
- +1.0 for accepted offer
- +0.5 for positive tone counter
- 0 for neutral
- –1.0 for hostility or unresponsiveness

Adjusts future tone intensity and empathy ratio accordingly.

---

## 10) Error Handling
| Code | Condition | Response |
|------|------------|----------|
| OR-001 | Invalid buyer message | Trigger reclassification |
| OR-002 | Low confidence | Route to Governance |
| OR-003 | Missing offer ID | Lookup recent thread |
| OR-004 | Timeout | Re-query mailbox (retry x3) |
| OR-005 | Unrecognized intent | Escalate to Igor |
| OR-006 | Tone validation fail | Reprocess through empathy filter |

---

## 11) Odoo Integration
**Model:** `sm.offer.response`

**Triggers:**
- `@api.on_create` → parse new inbound message.
- `@api.depends('intent')` → execute workflow routing.

**Syncs with:**
- Offer Drafting Agent
- Follow-Up Agent
- Decision Ledger
- Buyer CRM profile

---

## 12) Example Decision Ledger Entry
```json
{
  "ledger_id": "DL-RESP-22017",
  "offer_id": "OFR-1042",
  "buyer_id": "B009",
  "intent": "COUNTER",
  "confidence": 0.92,
  "proposed_price": 0.36,
  "system_action": "Counter_Recommended_0.37",
  "timestamp": "2025-10-16T18:22:47Z"
}
```

---

## 13) Learning & Optimization
- Continuously fine-tunes empathy modulation.
- Learns tone-response effectiveness per buyer.
- Stores anonymized language samples for tone retraining.
- A/B tests politeness phrasing for optimal close rate.

---

## 14) Change Log (v4.0)
- Added sentiment-aware tone filter.
- Integrated emotional feedback loop into Trust Index.
- Unified approval rules with Governance v4.0.
- Embedded compliance layer for anti-manipulative phrasing.
- Introduced standard signature format (per Canonical 2025-10).

---
