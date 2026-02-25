GAP ANALYSIS: Offer Drafting Agent v4.0 + Offer Response Agent v4.0 vs plasticos_offer
Current vs target
Dimension	Current	Target	Gap
Offer Drafting	~25%	100%	75%
Offer Response	~15%	100%	85%
Governance	0%	100%	100%
Tests	0%	100%	100%
Docs	Minimal	Complete	~90%
Gaps (prioritized)
Offer Drafting Agent (Offer_Drafting_Agent_v4.0.md)
#	Gap	Priority	Fix
1	No auto-trigger at confidence ≥ 0.85	High	Add automation/cron to create offers from match results when confidence >= 85
2	No market pricing	High	Add plasticos_market (or similar) for price_band, market_trend, commodity_index; compute suggested price
3	No governance layer	High	Add approval routing (Arthur/Igor), PRICE_GOV_CAP, price override rules
4	No Decision Ledger	High	Add sm.decision.ledger or equivalent; log all offer events
5	No email composition	High	"Send Offer" should open mail.compose.message with template, not only change state
6	Missing spec fields	Medium	Add confidence_score, buyer_contact, governance_flag, linked_ledger_id, internal_target_price, external_offer_price
7	No template assembly	Medium	Add modular offer composition (header, material, pricing, closing) per Tone & Style Guide
8	No compliance validation	Medium	Add ASTM polymer check, trade jurisdiction, ethical tone validation
9	No relational intelligence	Medium	Add buyer history (last 5 offers, response delay, trust delta) for tone calibration
10	No error codes (OF-001–006)	Low	Add structured error handling and logging
11	No learning/optimization	Low	Add adaptive pricing, A/B tone testing, feedback loop
Offer Response Agent (Offer_Response_Agent_v4.0.md)
#	Gap	Priority	Fix
1	No sm.offer.response model	High	Spec uses separate response model; current uses response_notes + counter_price_per_lb on offer
2	No intent classification	High	Add pipeline: ACCEPTED, COUNTER, REJECTED, INFO_REQUEST, DELAYED_RESPONSE
3	No buyer reply ingestion	High	No parsing of inbound email/CRM messages
4	No tone/sentiment analysis	High	Add sentiment_score, intent_vector from Relational Intelligence
5	No automated negotiation handling	High	COUNTER → draft midpoint reply; REJECTED → Follow-Up Agent; etc.
6	No Trust Index updates	Medium	Add trust delta per exchange (+1 accepted, +0.5 positive counter, etc.)
7	No response templates	Medium	Add acceptance/counter/rejection templates per spec
8	No approval routing for discounts	Medium	Add approval for discount > 0.005/lb, multi-load volume limits
9	No error codes (OR-001–006)	Low	Add structured error handling
Shared / infrastructure
#	Gap	Priority	Fix
1	No tests	High	Add unit tests for offer lifecycle, bulk actions, cron
2	No integration tests	Medium	Test match → offer flow, offer → transaction flow
3	Model name mismatch	Low	Spec: sm.offer.draft; current: plasticos.offer (acceptable if intentional)
4	No match → offer creation	High	match_result.action_accept() does not create offer; add wizard or automation
Current implementation (what exists)
Component	Status
plasticos.offer model	Present
Lifecycle: draft → sent → responded → accepted/rejected/expired/cancelled	Present
match_result_id, intake_id, supplier_id, buyer_id	Present
price_per_lb, quantity_lbs, delivery_terms, payment_terms, valid_until	Present
response_notes, counter_price_per_lb	Present
action_send, action_accept, action_reject, etc.	Present
Bulk action wizard	Present
Cron: expire past-due offers	Present
Search, list, kanban, calendar, pivot, graph views	Present
Chatter	Present
