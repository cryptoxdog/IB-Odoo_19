# BRS-EXP-07: Transport equipment types, booking quantities and container identity

**Class:** additive operator-locked equipment taxonomy plus proposed technical constraints; no replacement of existing BRS-EXP-01..06 or Native-First BRS.
**Owners:** PlasticOS Logistics/native Odoo for transport equipment/physical dispatch; `plasticos_export` for booking-specific equipment request and views; Odoo Stock for inventory; Documents for evidence.
**Phase:** BOTH where applicable; domestic transport specifically P1 and shared logistics.
**Source reality:** `plasticos.equipment.type` means facility capabilities, not freight equipment. `plasticos.load` has `trailer_number` and `seal_number`, not a demonstrated transport equipment type registry. Source observed at `cryptoxdog/IB-Odoo_19@04bd0594a7c9dcad53d9c45fc65276d76817c112`.
**Status:** User equipment options and 40HC default preference are LOCKED product decisions. New owner wiring/shape and conditional rules remain DESIGN; no implementation or runtime verification.

## Rules

### BRS-EXP-07-R001: Equipment vocabulary differentiates road trailers from ocean containers

**LOCKED · BOTH · owner: `Logistics transport equipment classification; Export uses scoped choices`.** The transport equipment selections SHALL distinguish domestic road trailers from maritime freight containers. It SHALL NOT conflate vehicle/trailer identity, ISO container identity, shipping booking identity, Odoo stock package identity, or an internal load. A chassis carrying an ocean container remains a ground transport leg associated with a distinct maritime container.

- **Positive:** A 40HC container travels on a chassis to a terminal while its ISO container number, drayage load, booking and scanned cargo packages remain distinct.
- **Negative:** A stock.package, trailer number or booking number substitutes for ISO container identity or its truck chassis.
- **Cross references:** BRS-EXP-01-R001,R002; BRS-EXP-02-R001; PlasticOS native stock/load boundaries
- **Acceptance:** `AC-EXP-07-001` / NOT_RUN.

### BRS-EXP-07-R002: Supported domestic trailer choices

**LOCKED · P1 · owner: `Logistics transport equipment; Export references for terminal drayage if applicable`.** Domestic dispatch SHALL support 53-foot trailers, 48-foot trailers and flatbeds. Flatbeds SHALL be a type independent of any assumed universal length; dimensions and restrictions MAY be specified for the actual move. Export SHALL NOT create a second domestic trailer catalog or dispatch process.

- **Positive:** Operator can specify a 53-foot trailer, 48-foot trailer or flatbed on native logistics movement and find it through the related export booking if relevant.
- **Negative:** Flatbed automatically means 48-foot, or Export creates a duplicate domestic load and rate workflow.
- **Cross references:** BRS-POS-02/BRS-EXP-01 native Logistics ownership
- **Acceptance:** `AC-EXP-07-002` / NOT_RUN.

### BRS-EXP-07-R003: Supported ocean container choices with a preference, not a hard constraint

**LOCKED · BOTH · owner: `Export booking presentation; shared logistics equipment semantics`.** Export booking choices SHALL include 40-foot high cube (40HC), 40-foot standard (40STD), 45-foot high cube (45HC), 45-foot standard (45STD) and 20-foot standard (20STD). For the operator's plastic exports, 40HC SHALL be the default suggested option, not an enforced selection. 20STD SHALL remain selectable for metal recyclers without precluding other cargo. Supported-in-UI does not assert steamship-line, route, port, or chassis availability.

- **Positive:** Plastic booking suggests 40HC; metal export can explicitly choose 20STD; 40STD, 45HC and 45STD remain separately selectable when offered.
- **Negative:** The system silently converts a requested 45STD to 45HC, bans a 20STD for non-metal cargo, or asserts any type is universally bookable.
- **Cross references:** BRS-EXP-02-R001,R002; carrier confirmation remains external evidence
- **Acceptance:** `AC-EXP-07-003` / NOT_RUN.

### BRS-EXP-07-R004: Booking equipment count and per-week physical units

**DESIGN · BOTH · owner: `Export reservation; Logistics actual movements; native Stock cargo`.** A booking SHALL capture requested container equipment and count; physical units SHALL separately retain ISO number, seal, actual equipment, native stock packages and linked movement/load identity. Several containers MAY share one booking; distinct weekly movements MAY each have their own booking even when they share one PO and SO. Requested/actual equipment amendments SHALL not overwrite other siblings or invent copy-per-unit cargo weight.

- **Positive:** One SO covers four weekly shipments with four booking numbers; a later booking includes two distinct 40HC containers each with its own seal and loading evidence.
- **Negative:** Changing week 3 equipment silently edits week 1 container or copies full shipment tonnage to both containers.
- **Related existing BRS:** BRS-EXP-02-R001; BRS-EXP-08-R005; BRS-POS-05.
- **Acceptance:** `AC-EXP-07-004` / NOT_RUN.

### BRS-EXP-07-R005: Reuse only the correct equipment owner and native records

**DESIGN · BOTH · owner: `Logistics transport master/native shipping record; Export only booking-specific fields`.** Before adding any transport-type persistence, inspect native Odoo delivery/shipping and existing PlasticOS Logistics fields and extend the canonical owner only for an actual gap. `plasticos.equipment.type` is an existing FACILITY production/handling equipment registry (balers, granulators, etc.) and SHALL NOT be repurposed as a freight-container type registry. `plasticos_export` SHALL NOT create a competing universal equipment master, stock package, carrier record or transport engine.

- **Positive:** A missing transport type is defined once at the appropriate logistics/native transport owner and Export uses a reference; facility granulator capabilities remain untouched.
- **Negative:** Export seeds ocean sizes into facility equipment types or clones an overlapping equipment catalog.
- **Cross references:** Repo plasticos_facility_profile/models/equipment_type.py and data/equipment_type_data.xml at SHA 04bd0594
- **Acceptance:** `AC-EXP-07-005` / NOT_RUN.

### BRS-EXP-07-R006: Do not infer payload, capacity or VGM from nominal equipment name

**DESIGN · BOTH · owner: `Physical weight: native Odoo Stock and verified scale evidence; Export displays source facts`.** Equipment labels SHALL NOT imply a fixed cargo limit or certified legal weight. Actual scale observations, package net/tare, container tare, gross, lashing/packing weight where applicable, local carrier/road/port constraints, and any valid VGM evidence SHALL retain their respective sources, units, revisions and verification. Export SHALL NOT derive a certified VGM or commercial settlement quantity solely from scanned package weights or from a 40HC/20STD selection.

- **Positive:** A 40HC shipment includes current package totals and independently attributed container tare/VGM evidence when required, without altering supplier/buyer settlement authority.
- **Negative:** 40HC code automatically inserts a universal max payload, self-certifies VGM or writes invoice weights.
- **Cross references:** BRS-EXP-03; BRS-POS weight authority; VGM governed outside equipment catalogue
- **Acceptance:** `AC-EXP-07-006` / NOT_RUN.

### BRS-EXP-07-R007: Equipment discrepancy and booking amendment are explicit

**DESIGN · BOTH · owner: `Export booking contextual exception; Documents evidence; Logistics physical movements`.** A mismatch between requested and supplied equipment SHALL be reported with provenance and require an authorized booking amendment or explicit exception resolution. Confirmed equipment type and actual container ID SHALL follow physical evidence. Export SHALL not rebook, dispatch, email the carrier, change stock, change the Incoterm or cancel a booking merely because an equipment selection changes.

- **Positive:** Carrier assigns 40STD instead of requested 40HC; the booking view shows discrepancy and a sourced operator approval before documentation is finalized.
- **Negative:** Export silently changes freight/dispatch and sends a replacement carrier instruction on a dropdown edit.
- **Cross references:** BRS-EXP-02-R004,R005; BRS-EXP-01-R004; Linda sending authority
- **Acceptance:** `AC-EXP-07-007` / NOT_RUN.

### BRS-EXP-07-R008: Reports and loading must use exact units without duplicate inventory

**DESIGN · BOTH · owner: `Export views/QWeb; native Stock physical movement; Documents evidence/verification`.** Booking screens, loading/packing reports and associated documents SHALL display requested equipment, confirmed equipment, count and each actual container ID/seal as available, sourced from their owner. QR scans SHALL continue to update native Odoo stock/package movements and per-container loading evidence, not an export-owned inventory ledger. Blank/unconfirmed equipment or ambiguous load association SHALL display Unknown/Needs Review instead of inventing capacity, seal or departure status.

- **Positive:** Packing list for one of two booked containers lists exactly the scanned inventory packages, distinct seal and observed weight with unresolved fields clearly shown.
- **Negative:** A booking-level 40HC field copies all 40,000 lb onto each of two containers, or report assumes goods are shipped before verified stock dispatch.
- **Cross references:** BRS-EXP-01,R002; BRS-EXP-03; RecycleOS QR boundary
- **Acceptance:** `AC-EXP-07-008` / NOT_RUN.
