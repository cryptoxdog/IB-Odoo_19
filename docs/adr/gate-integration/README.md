# Gate Integration ADR Pack

**Repository:** `cryptoxdog/IB-Odoo_19`
**Authoritative branch:** `Staging`
**Architecture status:** LOCKED
**Decision scope:** Odoo integration with `Quantum-L9/Gate_SDK`, `Constellation.Gate`, and canonical EIE convergence
**Effective date:** 2026-08-31

## Numbering

This is a **namespaced series**. `ADR-001` … `ADR-016` **inside this directory**
belong to this pack; they are distinct from the root `docs/adr/ADR-001` …
`ADR-019` series, which continues to own its own numbering. The pack's internal
cross-references (`ADR-006`, `ADR-013`, …) always mean this directory. Root ADRs
are referred to explicitly as "repo ADR-0NN".

The pack is namespaced rather than renumbered into the root sequence so that the
authored cross-references, the index below, and the machine-readable lock stay
byte-faithful to the accepted decision set.

## Index

| ADR | Decision | Status |
|-----|----------|--------|
| [ADR-001](ADR-001-gate-sdk-sole-transport-authority.md) | Gate_SDK is the sole transport authority | Accepted |
| [ADR-002](ADR-002-gate-only-egress.md) | Odoo uses Gate only; no peer-service transport | Accepted |
| [ADR-003](ADR-003-odoo-owns-domain-not-transport.md) | Odoo owns domain mapping, not transport semantics | Accepted |
| [ADR-004](ADR-004-canonical-enrichment-contract.md) | Canonical enrichment contract is EnrichRequest → EnrichResponse | Accepted |
| [ADR-005](ADR-005-canonical-entity-identity.md) | Canonical Odoo entity identity is `entity.id` | Accepted |
| [ADR-006](ADR-006-one-logical-operation-identity.md) | One logical operation identity spans replay boundaries | Accepted |
| [ADR-007](ADR-007-one-sdk-invocation-surface.md) | One SDK invocation surface replaces Odoo shadow transport | Accepted |
| [ADR-008](ADR-008-no-odoo-transport-retry.md) | Odoo owns no transport retry layer | Accepted |
| [ADR-009](ADR-009-one-caller-deadline.md) | One caller deadline governs Odoo → Gate execution | Accepted |
| [ADR-010](ADR-010-odoo-owns-crm-writeback.md) | Odoo owns CRM writeback policy | Accepted |
| [ADR-011](ADR-011-exact-sdk-revision-pins.md) | Runtime dependencies use exact proven SDK revisions | Accepted |
| [ADR-012](ADR-012-installed-and-runtime-proof.md) | Installed/runtime proof is required for Gate integration | Accepted |
| [ADR-013](ADR-013-sdk-capability-gaps-belong-in-gate-sdk.md) | SDK capability gaps must be fixed in Gate_SDK, not shadowed in Odoo | Accepted |
| [ADR-014](ADR-014-architecture-boundary-tests-are-release-gates.md) | Architecture-boundary tests are release gates | Accepted |
| [ADR-015](ADR-015-no-acknowledgement-implies-success.md) | No acknowledgement may imply unproven downstream success | Accepted |
| [ADR-016](ADR-016-shadow-sdk-elimination-release-invariant.md) | Shadow-SDK elimination is a release invariant | Accepted |

## Locked canonical Odoo execution graph

```
┌─────────────────────────────────────────┐
│                ODOO                     │
│ res.partner                             │
│     ↓                                   │
│ EnrichRequest builder                   │
│     ↓                                   │
│ entity.id = res.partner:N               │
│ operation_id = durable enrichment run   │
│     ↓                                   │
│ thin SDK invocation adapter             │
└────────────────┬────────────────────────┘
                 ▼
┌─────────────────────────────────────────┐
│              GATE_SDK                   │
│ canonical TransportPacket               │
│ transport identity                      │
│ idempotency header                      │
│ timeout                                 │
│ correlation / causation / lineage       │
│ validation / signing / integrity        │
│ Gate-only HTTP transport                │
└────────────────┬────────────────────────┘
                 ▼
┌─────────────────────────────────────────┐
│          CONSTELLATION.GATE             │
│ action="converge"                       │
│ canonical owner → EIE                   │
│ payload semantics unchanged             │
└────────────────┬────────────────────────┘
                 ▼
┌─────────────────────────────────────────┐
│                  EIE                    │
│ EnrichRequest                           │
│ shared deadline                         │
│ provider execution                      │
│ required persistence                    │
│ zero synchronous Graph                  │
│ EnrichResponse                          │
└────────────────┬────────────────────────┘
                 ▼
             Gate / SDK
                 ▼
┌─────────────────────────────────────────┐
│                 ODOO                    │
│ EnrichResponse mapper                   │
│ proposal persistence                    │
│ allowlist                               │
│ merge-not-overwrite                     │
│ CRM writeback                           │
└─────────────────────────────────────────┘
```

## Authority table

| Concern | Authority |
|---------|-----------|
| CRM identity | Odoo |
| EnrichRequest construction | Odoo |
| Logical enrichment-run identity | Odoo |
| TransportPacket | Gate_SDK |
| Packet integrity | Gate_SDK |
| Packet signing | Gate_SDK |
| Transport timeout implementation | Gate_SDK |
| Gate HTTP transport | Gate_SDK |
| Transport errors | Gate_SDK |
| Action routing | Constellation.Gate |
| `converge` ownership | EIE |
| Enrichment computation | EIE |
| Provider retries | EIE |
| Enrichment persistence | EIE |
| EnrichResponse | EIE |
| CRM response mapping | Odoo |
| CRM writeback | Odoo |

No concern has two canonical authorities.

## Prohibited architectural patterns

Expressly rejected for IB-Odoo_19:

- Odoo → EIE directly
- Odoo manually POSTing `/v1/execute`
- Odoo building a second Gate protocol
- Odoo maintaining a second `TransportPacket` abstraction
- Odoo selecting downstream workers
- Odoo implementing Gate retries
- Odoo implementing packet signatures
- Odoo implementing transport hashes
- Odoo independently validating transport packets
- Odoo depending on EIE URLs
- Odoo inventing an EIE-specific response dialect
- Odoo hiding missing Gate_SDK features in local wrappers

## Change control

These ADRs are architecture constraints, not suggestions. A change that
violates one requires an explicit superseding ADR containing: the named
invariant that cannot be satisfied; executable evidence; the reason the current
architecture fails; simpler alternatives considered; the reason simpler
alternatives fail; migration strategy; cross-repository impact; rollback
strategy.

"No longer convenient", "existing wrapper already works this way", and "tests
are green" are each insufficient.

## Release gate

IB-Odoo_19 is locally GO for the Gate integration only when:

```yaml
architecture:
  shadow_sdk: ELIMINATED
  gate_sdk_transport_authority: true
  gate_only_egress: true
domain:
  request: EnrichRequest
  response: EnrichResponse
  canonical_entity_id: true
  one_logical_operation_identity: true
transport:
  manual_transport_logic_in_odoo: false
  odoo_retry_layer: false
  caller_budget_seconds: "<=30"
  timeout_mechanics_sdk_owned: true
runtime:
  clean_install: PASS
  real_odoo_19: PASS
  sdk_invocation: PASS
safety:
  response_fail_closed: true
  writeback_allowlisted: true
  merge_not_overwrite: true
```

If Gate_SDK cannot support the required application-facing call without Odoo
manually recreating transport behavior:

```yaml
odoo_local: NO_GO
shadow_sdk: PARTIALLY_ELIMINATED
sdk_capability: BLOCKED_EXTERNAL_SDK_CAPABILITY
next_move: fix_Gate_SDK
```

## Machine-readable architecture lock

```yaml
architecture_lock:
  repository: cryptoxdog/IB-Odoo_19
  branch: Staging
  status: LOCKED
  domain:
    producer: Odoo
    request: EnrichRequest
    response: EnrichResponse
    canonical_identity: "entity.id = res.partner:<id>"
    compatibility_identity: "entity._odoo_entity_id"
  transport:
    authority: Quantum-L9/Gate_SDK
    direct_peer_transport: prohibited
    gate_only_egress: required
    shadow_sdk: prohibited
    manual_packet_creation: prohibited
    manual_http_transport: prohibited
    manual_transport_validation: prohibited
    manual_transport_signing: prohibited
    manual_retry: prohibited
  routing:
    authority: Quantum-L9/Constellation.Gate
    converge_owner: EIE
  idempotency:
    business_identity_owner: Odoo
    one_logical_operation_identity: required
    transport_representation_owner: Gate_SDK
    durable_domain_semantics_owner: EIE
  deadlines:
    odoo_caller_ceiling_seconds: 30
    transport_mechanics_owner: Gate_SDK
    downstream_internal_budget_owner: EIE
  writeback:
    authority: Odoo
    field_allowlist: required
    merge_not_overwrite: required
  sdk_capability_gap:
    policy: >
      Fix canonical transport capability in Gate_SDK.
      Never compensate by recreating transport semantics in Odoo.
  proof:
    installed_package_required: true
    real_odoo_runtime_required: true
    architecture_boundary_tests_required: true
    mock_only_runtime_proof: rejected
  release_invariant:
    statement: >
      IB-Odoo_19 is a Gate_SDK consumer, not a second Gate SDK.
```

## Relationship to the root ADR series

| This pack | Root ADR | Relationship |
|---|---|---|
| ADR-001, ADR-002 | repo ADR-002, ADR-003-single | Names the transport authority under the existing Gate-hub topology |
| ADR-008, ADR-015 | repo ADR-013 (fail-closed Gate transport) | Same posture; this pack fixes ownership of retry and success semantics |
| ADR-010 | repo ADR-012 (writeback allowlist/provenance) | repo ADR-012 remains the field-level spec; ADR-010 fixes ownership |
| ADR-004 | repo ADR-011 (intelligence action topology) | `converge` payload contract for the action topology already accepted |
| ADR-003 | repo ADR-009, ADR-015 | Consistent with ranking-outside-Odoo and persistence-shell decisions |
