# RecycleOS operational expansion v1.5.0: Transport equipment extension

**Additive only.** Predecessor: v1.4.0. Frozen prior original decisions remain; this updates the export BRS registry and acceptance index to include BRS-EXP-07, without altering any original six BRS chapters or earlier RecycleOS narrative files. Runtime tests: NOT_RUN; repo mutations: NONE.

## Operator-locked requirements

Domestic: 53-foot trailer, 48-foot trailer and flatbed. Export: 40-foot high cube (**40HC default suggestion for plastics**), 40-foot standard, 45-foot high cube, 45-foot standard, 20-foot standard (**used by metal recyclers**). These are supported choices, not claims that every carrier/route can supply each.

## Required distinctions

A booking may request multiple units of a type. An actual unit has its own physical ISO number, seal, tare/gross evidence and contents. Drayage trailers and chassis must not be mistaken for the ocean container. Stock package and lot identities remain native Odoo; physical dispatched load remains Logistics-owned. Equipment type never authorizes billing weight, legal VGM or shipment readiness automatically.

## Semantic owner

The existing `plasticos.equipment.type` records describe facility equipment and capability, not transport. Do not seed transport equipment there. Find an appropriate native Odoo/Logistics transport representation before creating any new master. Export stores only booking-specific requested type and quantity when missing elsewhere. See `EXPORT_BRS/RULES/BRS-EXP-07.md` and `EXPORT_BRS/EQUIPMENT_OWNER_ADDENDUM.md`.
