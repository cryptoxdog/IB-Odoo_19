# Controlled supersession / change ledger

**Version:** Export BRS v1.1.0 -> v1.2.0 (working design only).
**Direct predecessor SHA-256:** `50c68a9e40c8c90a981947c15e7bf6611fcaecf1abfbd1631ed1fc50d4d78884`
**Repository changes:** none. **Runtime validation:** NOT_RUN.

## Operator clarifications admitted as business intent, not as tested software

1. An actual export sale usually has a buyer, but legitimate purchased/owned and moving cargo can have **no buyer yet**. Buyer may be added when sold **on the water**. This supersedes *both* absolute “export load always has buyer” and absolute “export load never needs buyer” simplifications. Eligibility depends on movement purpose and actual sale state.
2. Buyer and physical destination are distinct: port/rail ramp can be delivery point while buyer is an overseas company.
3. One actual SO can cover 30 MRP loads; one supplier PO can authorize four weekly supplier loads. Each of the four shipments can have its **own booking**. The operator favors one four-load PO, not four one-load POs, where native Odoo permits.
4. Odoo 19 native AI Documents shall be leveraged to extract booking fields, match the **correct** shipment/order, and provide verified evidence for allowed, guarded state-owner transitions. No partner-only heuristic, direct state write, or duplicate document engine.
5. Prior locks stay: 40HC common, five ocean equipment types, six booking fields, industry FOB/FAS and formal Incoterm distinction, phases, one original/one verification owner, Linda sender, Logistics carrier/dispatch owner.

## Normative revisions in-place

- `BRS-EXP-01-R003`: Exact, non-fictitious links -> **Exact associations without mandatory early buyer**. Old block SHA `9aaef2ca8e6d`, new SHA `44f3bc27721d`.
- `BRS-EXP-01-R004`: No cross-owner consequential transitions -> **Evidence proposals are not unauthorized business transitions**. Old block SHA `cfe57ec625d4`, new SHA `472afa625603`.
- `BRS-EXP-02-R001`: One contextual booking with reusable native links -> **Booking-to-order and shipment cardinality independent**. Old block SHA `0961d83f1705`, new SHA `138a58123308`.
- `BRS-EXP-03-R001`: One intake/original, exact attribution -> **Native intake, AI-proposed extraction and exact document attribution**. Old block SHA `4a56159ff08e`, new SHA `b6777a84b89c`.
- `BRS-EXP-04-R003`: Factual handoff and responsibility evidence -> **Physical handoff and commercial allocation are independent**. Old block SHA `e6e1ab49c994`, new SHA `cfbe9dcb982b`.
- `BRS-EXP-05-R001`: Extend Phase 1 identities without migration -> **In-transit sale reuses original shipment and evidence**. Old block SHA `f1d91794c1dc`, new SHA `6db2061a9746`.
- `BRS-EXP-06-R003`: Independent operational and financial states -> **Order, shipment, evidence and transaction states remain scoped**. Old block SHA `864c7d17c5b8`, new SHA `cc99e5df8ec1`.
- `BRS-EXP-07-R004`: Booking equipment request, count and actual units are distinct -> **Booking equipment count and per-week physical units**. Old block SHA `094dedcf27c1`, new SHA `34befcb0606c`.

## New normative chapters

- `BRS-EXP-08`: commercial orders, buyer-optional material, 30 SO / 4 PO / 4 bookings / many physical loads.
- `BRS-EXP-09`: native AI booking extraction, exact linking, source/revision, guarded state actions.
- `BRS-EXP-10`: export-to-Logistics/Linda work orders, booking constraints, supplier/carrier packets and movement-specific eligibility.

## Explicit prior proposal dispositions

- **Withdraw** buyerless-is-always-required and buyer-always-required as global predicates. They are movement-specific and context-dependent.
- **Withdraw** a universal buyerless purchase order as a substitute for real buyer-linked sales and a requirement that all drayage be PO-only.
- **Preserve** existing normal sales partner validation where a real sale is being executed.
- **Preserve** buyer/destination separation, real port/rail gate acceptance, no cross-owner state changes, formal vs trade Incoterm separation.
- **Reject** one SO = one load, one PO = one load, one booking = one PO and mandatory PO reissue on every weekly booking.

## Cross-owner authority

The Export BRS **cannot** itself supersede canonical Logistics, Documents, native Purchase/Sales/Stock or Native-First POS BRS. `INTEROP/TARGET_OWNER_BRS_AMENDMENTS.md` holds explicit proposals for their authorized owners; no repository code altered. This distinction is mandatory to prevent a false “all BRS integrated” claim.
