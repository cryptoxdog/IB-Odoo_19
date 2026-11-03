## Status and precedence clarification for v2.0.0

The `ROS-OPS-*` statements below are **product-local operational constraints and acceptance intent**, not a second repository-level constitutional file. The full candidate constitutional source is `GOVERNANCE/ODOO_INVARIANTS_v3.1.0_DRAFT_r1.md`; the exact original upload is preserved alongside it. Product-specific scan/label/device/costing instructions remain in this file and their BRS owners. See `GOVERNANCE/INVARIANT_ALIGNMENT_AND_IRREDUCIBILITY.md` for each parent invariant, duplication test, and scope. Repository `INVARIANTS.md` v2.2.0 remains admitted until formally changed.

---

# Operator decisions and sharp behavioral invariants

## Explicit decisions (LOCKED as captured; no implicit implementation authority)

| ID | Decision | Classification |
| --- | --- | --- |
| DEC-01 | Mobile receiving is a core operational RecycleOS capability. | Locked |
| DEC-02 | QR/barcode traceability for downstream physical material movement is core. | Locked |
| DEC-03 | Scale integration is a core product capability, but an individual site need not have a truck scale. | Locked, with equipment applicability inferred |
| DEC-04 | Detailed production cost-per-pound reporting is optional; native cost-accounting capability remains reusable. | Locked |
| DEC-05 | For a platform-scale-only site, the intuitive path is weigh container -> identify by barcode/QR -> receive into inventory -> scan when loading outbound. | Locked conceptual workflow |
| DEC-06 | A single receipt confirmation should complete the weigh/scan/receive operation; do not force a duplicate scan purely to post inventory. | Accepted UX refinement |
| DEC-07 | Use native Odoo capabilities and protect the installed PlasticOS business logic; add differentiated dock UX and device adapters, not parallel ERP records. | Agreed product posture |

## Candidate product invariants for authorized product-owner admission
These express the locked choices without pretending that the operator has admitted a new constitutional law file.

**ROS-OPS-001: Native authoritative inventory.** Physical receipt, transfer, reservation, manufacturing consumption/output, and delivery are carried out by Odoo's authoritative stock operations; RecycleOS Dock is a controlled interface, not a second stock ledger.

**ROS-OPS-002: Distinct identities.** Product/material definition, material lot/batch, physical container/package, stock move, scale reading, purchase/sale and load are distinct entities. Linking them does not merge them.

**ROS-OPS-003: Durable scan key.** A label holds an immutable and unique lookup identifier, not an authoritative cached weight, status, valuation or location. Changing a container's location or weight must not force relabeling unless a label is damaged or container identity changes.

**ROS-OPS-004: Atomic dock confirmation.** The operator can capture a container's identity, material, verified/entered net weight and destination and confirm one authorized receipt transaction. Scanning a second time only to transfer the same data into inventory is not required.

**ROS-OPS-005: Explicit transformation.** Material converted from one form/grade to another consumes the input stock via a native manufacturing/processing operation and creates distinct output product/lot/container identity with traceable inputs. Never relabel the unchanged source inventory as converted product without the production event.

**ROS-OPS-006: Physical weight provenance.** Every consequential recorded weighment retains scale/device or manual origin, original units, observed time, attribution, gross/tare/net where relevant, container and movement identity, and adjustment history.

**ROS-OPS-007: Weight is not automatically commercial authority.** An observed scale weight is physical evidence; the contractually governing receipt/settlement/invoice quantities are independently determined under applicable authenticated rules. No scanner or IoT event unilaterally posts or changes financial obligations.

**ROS-OPS-008: Device-neutral interfaces.** Mobile camera, Bluetooth/USB scanner, and dedicated handhelds are alternate input channels; platform and truck scales are device-specific adapters into validated weighment evidence, not exclusive hardware commitments.

**ROS-OPS-009: Partial operations remain accurate.** Partial receipts, multiple containers on one lot, split lots, repackaging, partial shipments, reweighs, returns and corrected scans must not lose quantities, create duplicates or obscure provenance.

**ROS-OPS-010: No phantom completion.** A scan is an observation, not proof that an inventory move, manufacturing consumption, truck departure, legal-scale certification or customer invoice is complete. Completion requires the corresponding authorized native state transition.

**ROS-OPS-011: No unproved device promises.** iPhone camera access, PWA use, specific scanner input, printer support, industrial scale integration, browser offline behavior and Odoo Enterprise Barcode availability must be verified for the chosen tenant, platform and licenses before they are advertised as functioning.

**ROS-OPS-012: Human-scale UX.** Frequent dock actions should be achievable with one obvious operation and minimal inputs, with guardrails for exceptions, not by asking dock workers to navigate accounting/manufacturing internals.

**ROS-OPS-013: Optional granular economics.** Native financial and manufacturing costing remain usable, but batch cost/lb and fine-grained allocation are optional and cannot block mobile receiving, physical traceability or scale evidence capture.

**ROS-OPS-014: Safe retrials and correction.** Lost connectivity, duplicate scans, late scale events and user corrections require idempotent, attributable handling; no silent overwrite or double receipt/delivery.

## Scope guards
- Do not create a competing warehouse, accounting, manufacturing or documents authority.
- Do not silently change legacy `plasticos.*` models, customer records or technical names to achieve outward branding.
- No automated financial posting from a scan, reported weight or unverified document.
- Do not conflate an Odoo-supported feature in documentation with an installed or operational PlasticOS capability.
- No deployment, device purchase, outreach, repo change or agent delegation is authorized by this packet.

## Global dashboard contract (operator-approved design direction, v2.3)

Every PlasticOS / RecycleOS dashboard must present the most vital truthful information from its material underlying reports and provide exact permission-checked drill-down to the same filtered report population and source records. `POS-INV-24` is the newly proposed constitutional home, still DRAFT; the six specific Phase 1 Export reports and their metrics are detailed only in `EXPORT_BRS/BOOKING_CONTROL_CENTER_UX.md` and BRS-EXP-14-R017/R021/R022. No new reporting engine or business fact writer is authorized. The existing repo v2.2.0 constitution remains in force until formal admission.
