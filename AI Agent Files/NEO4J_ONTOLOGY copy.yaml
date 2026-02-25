# NEO4J_ONTOLOGY.yaml — PlasticOS Neo4j Graph Database Schema
# Repository: cryptoxdog/IB-Odoo_19
# Branch: staging
# Last Updated: 2026-02-24

meta:
  version: "2.0.0"
  odoo_version: "19.0"
  neo4j_version: "5.15+"
  module: "plasticos_buyer_match_engine"
  description: "Graph schema for buyer-supplier matching with transaction history"

# ==============================================================================
# Node Types
# ==============================================================================
nodes:
  - label: Facility
    description: "Buyer facility with processing capabilities"
    source_model: "plasticos.facility.profile"
    sync_trigger: "facility write, partner geo update"
    properties:
      partner_id:
        type: Integer
        required: true
        indexed: true
        description: "res.partner.id (Odoo primary key)"

      name:
        type: String
        required: true
        description: "Facility name"

      company_name:
        type: String
        required: false
        description: "Parent company name"

      # Geographic
      latitude:
        type: Float
        required: false
        description: "Facility latitude (WGS84)"

      longitude:
        type: Float
        required: false
        description: "Facility longitude (WGS84)"

      city:
        type: String
        required: false
        description: "City"

      state:
        type: String
        required: false
        description: "State/province code"

      country:
        type: String
        required: false
        description: "Country code (ISO 3166-1 alpha-2)"

      max_radius_miles:
        type: Float
        required: false
        default: 300.0
        description: "Maximum shipping distance (per-buyer override)"

      # Material Acceptance
      accepted_polymers:
        type: List[String]
        required: false
        description: "Polymer codes buyer accepts (e.g., ['HDPE', 'PP'])"

      accepted_forms:
        type: List[String]
        required: false
        description: "Forms buyer accepts (e.g., ['bales', 'regrind'])"

      accepted_source_types:
        type: List[String]
        required: false
        description: "Source types buyer accepts (e.g., ['pi', 'pcr'])"

      # Material Property Ranges
      density_min:
        type: Float
        required: false
        description: "Minimum density (g/cm³)"

      density_max:
        type: Float
        required: false
        description: "Maximum density (g/cm³)"

      melt_index_min:
        type: Float
        required: false
        description: "Minimum MFI (g/10min)"

      melt_index_max:
        type: Float
        required: false
        description: "Maximum MFI (g/10min)"

      contamination_tolerance_pct:
        type: Float
        required: false
        default: 5.0
        description: "Maximum contamination percentage"

      moisture_tolerance_pct:
        type: Float
        required: false
        default: 1.0
        description: "Maximum moisture percentage"

      # Volume Constraints
      min_lot_size_lbs:
        type: Integer
        required: false
        description: "Minimum lot size (lbs)"

      max_lot_size_lbs:
        type: Integer
        required: false
        description: "Maximum lot size (lbs)"

      max_monthly_throughput_lbs:
        type: Integer
        required: false
        description: "Monthly processing capacity"

      # Equipment Capabilities
      has_wash_line:
        type: Boolean
        required: false
        default: false
        description: "Has washing equipment"

      can_reduce_moisture:
        type: Boolean
        required: false
        default: false
        description: "Has drying equipment"

      can_remove_metal:
        type: Boolean
        required: false
        default: false
        description: "Has metal separation"

      can_filter_fr:
        type: Boolean
        required: false
        default: false
        description: "Can filter flame retardants"

      has_granulator:
        type: Boolean
        required: false
        default: false
        description: "Has size reduction (bales → regrind)"

      has_shredder:
        type: Boolean
        required: false
        default: false
        description: "Has heavy-duty size reduction"

      has_extruder:
        type: Boolean
        required: false
        default: false
        description: "Has extrusion (pelletizing capability)"

      has_baler:
        type: Boolean
        required: false
        default: false
        description: "Can re-bale material"

      pvc_tolerant:
        type: Boolean
        required: false
        default: false
        description: "Can safely process PVC (rare)"

      # Certifications
      food_grade_certified:
        type: Boolean
        required: false
        default: false
        description: "FDA/FSMA certified for food contact"

      medical_grade_capable:
        type: Boolean
        required: false
        default: false
        description: "ISO 13485 or medical capability"

      # Metadata
      active:
        type: Boolean
        required: true
        default: true
        description: "Active in Odoo"

      last_synced:
        type: DateTime
        required: true
        description: "Last sync timestamp (ISO 8601)"

    indexes:
      - fields: [partner_id]
        unique: true
      - fields: [accepted_polymers]
      - fields: [city, state]
      - fields: [active]

    constraints:
      - type: uniqueness
        fields: [partner_id]
        name: "facility_partner_id_unique"

  - label: Material
    description: "Supplier material profile"
    source_model: "plasticos.material.profile"
    sync_trigger: "material profile write"
    properties:
      material_id:
        type: Integer
        required: true
        indexed: true
        description: "plasticos.material.profile.id"

      partner_id:
        type: Integer
        required: true
        indexed: true
        description: "Supplier res.partner.id"

      partner_name:
        type: String
        required: true
        description: "Supplier name"

      # Material Identity
      polymer:
        type: String
        required: true
        indexed: true
        description: "Polymer code (e.g., HDPE, PP)"

      form:
        type: String
        required: false
        description: "Form code (e.g., bales, regrind)"

      source_type:
        type: String
        required: false
        description: "Source type code (e.g., pi, pcr)"

      color:
        type: String
        required: false
        description: "Color code (e.g., natural, mixed)"

      packaging:
        type: String
        required: false
        description: "Packaging type (e.g., gaylord, supersack)"

      # Material Properties
      density:
        type: Float
        required: false
        description: "Density (g/cm³)"

      melt_index:
        type: Float
        required: false
        description: "MFI (g/10min)"

      contamination_pct:
        type: Float
        required: false
        description: "Contamination percentage"

      moisture_pct:
        type: Float
        required: false
        description: "Moisture percentage"

      # Quality Flags
      has_metal:
        type: Boolean
        required: false
        default: false
        description: "Contains metal contamination"

      has_fr:
        type: Boolean
        required: false
        default: false
        description: "Contains flame retardants"

      has_pvc:
        type: Boolean
        required: false
        default: false
        description: "Contains PVC (critical gate)"

      food_grade:
        type: Boolean
        required: false
        default: false
        description: "Food-grade material"

      medical_grade:
        type: Boolean
        required: false
        default: false
        description: "Medical-grade material"

      # Metadata
      active:
        type: Boolean
        required: true
        default: true

      last_synced:
        type: DateTime
        required: true

    indexes:
      - fields: [material_id]
        unique: true
      - fields: [partner_id]
      - fields: [polymer, form, source_type]

    constraints:
      - type: uniqueness
        fields: [material_id]
        name: "material_id_unique"

  - label: Intake
    description: "Temporary node for active buyer matching request"
    source_model: "plasticos.intake"
    sync_trigger: "intake match action"
    lifecycle: "Created on-demand, deleted after match"
    properties:
      intake_id:
        type: Integer
        required: true
        indexed: true
        description: "plasticos.intake.id"

      supplier_partner_id:
        type: Integer
        required: true
        description: "Supplier res.partner.id"

      # Material specs (same as Material node)
      polymer:
        type: String
        required: true

      form:
        type: String
        required: false

      source_type:
        type: String
        required: false

      quantity_lbs:
        type: Integer
        required: true

      latitude:
        type: Float
        required: false
        description: "Supplier facility latitude"

      longitude:
        type: Float
        required: false
        description: "Supplier facility longitude"

      max_radius_miles:
        type: Float
        required: false
        default: 300.0

      last_synced:
        type: DateTime
        required: true

    indexes:
      - fields: [intake_id]
        unique: true

    notes: |
      Intake nodes are ephemeral and created only during active matching.
      They are NOT persisted long-term to avoid graph bloat.

# ==============================================================================
# Relationship Types
# ==============================================================================
relationships:
  - type: SOLD_TO
    description: "Supplier material sold to buyer facility (transaction history)"
    source: Material
    target: Facility
    properties:
      tx_count:
        type: Integer
        required: true
        description: "Number of historical transactions"

      total_volume_lbs:
        type: Integer
        required: true
        description: "Total volume sold (all transactions)"

      avg_price_per_lb:
        type: Float
        required: false
        description: "Average price per lb"

      last_transaction_date:
        type: Date
        required: false
        description: "Most recent transaction date"

      recency_days:
        type: Integer
        required: false
        description: "Days since last transaction"

    creation_logic: |
      Created/updated by sync_transaction_edges() when:
      - Transaction.state in ('invoiced', 'paid', 'settled')
      - Links supplier_material_id → buyer_facility_id
      - Aggregates tx_count, total_volume_lbs from all transactions

    scoring_weight: 0.25
    notes: |
      Used for "proven buyer" bonus in match scoring.
      Higher tx_count = higher trust signal.

  - type: CAN_ACCEPT
    description: "Facility can physically accept this material form"
    source: Facility
    target: Material
    properties:
      form_compatible:
        type: Boolean
        required: true
        description: "Form can be handled by facility equipment"

      equipment_reason:
        type: String
        required: false
        description: "Which equipment enables this (e.g., 'has_granulator')"

    creation_logic: |
      Inferred from equipment capabilities:
      - has_granulator OR has_shredder → bales, parts, lumps
      - has_extruder → regrind, flake, pellet
      - has_wash_line → any form (adds cleaning)

    notes: |
      This relationship is NOT explicitly stored; it's inferred
      during Cypher query via equipment boolean checks.

# ==============================================================================
# Cypher Query Patterns
# ==============================================================================
queries:
  - name: match_buyers_for_intake
    description: "Two-stage buyer matching query (v2.0)"
    stage_1: "Capability Matcher (Python)"
    stage_2: "Graph Service (Cypher)"
    parameters:
      - intake_id: Integer
      - facility_ids: List[Integer]  # From Stage 1
      - polymer: String
      - form: String (optional)
      - source_type: String (optional)
      - quantity_lbs: Integer
      - latitude: Float (optional)
      - longitude: Float (optional)
      - radius_miles: Float (default 300)
      - density: Float (optional)
      - melt_index: Float (optional)
      - contamination_pct: Float (optional)
      - has_pvc: Boolean (default false)
      - has_metal: Boolean (default false)
      - has_fr: Boolean (default false)

    cypher: |
      MATCH (f:Facility)
      WHERE f.partner_id IN $facility_ids
        AND f.active = true
        AND $polymer IN f.accepted_polymers

        // Hard Gates
        AND ($form IS NULL OR $form IN f.accepted_forms)
        AND ($source_type IS NULL OR $source_type IN f.accepted_source_types)
        AND ($quantity_lbs >= COALESCE(f.min_lot_size_lbs, 0))
        AND ($quantity_lbs <= COALESCE(f.max_lot_size_lbs, 999999999))
        AND ($contamination_pct <= COALESCE(f.contamination_tolerance_pct, 100))
        AND (NOT $has_pvc OR f.pvc_tolerant = true)
        AND (NOT $has_metal OR f.can_remove_metal = true)
        AND (NOT $has_fr OR f.can_filter_fr = true)

        // Range Gates
        AND ($density IS NULL OR (f.density_min IS NULL OR $density >= f.density_min))
        AND ($density IS NULL OR (f.density_max IS NULL OR $density <= f.density_max))
        AND ($melt_index IS NULL OR (f.melt_index_min IS NULL OR $melt_index >= f.melt_index_min))
        AND ($melt_index IS NULL OR (f.melt_index_max IS NULL OR $melt_index <= f.melt_index_max))

      // Geographic Distance
      WITH f,
        CASE
          WHEN $latitude IS NOT NULL AND $longitude IS NOT NULL AND f.latitude IS NOT NULL AND f.longitude IS NOT NULL
          THEN point.distance(
            point({latitude: $latitude, longitude: $longitude}),
            point({latitude: f.latitude, longitude: f.longitude})
          ) * 0.000621371  // meters to miles
          ELSE 0.0
        END AS distance_miles

      WHERE distance_miles <= COALESCE(f.max_radius_miles, $radius_miles)

      // Transaction History (optional join)
      OPTIONAL MATCH (m:Material {partner_id: $supplier_partner_id, polymer: $polymer})-[tx:SOLD_TO]->(f)

      // Scoring
      WITH f, distance_miles, COALESCE(tx.tx_count, 0) AS tx_count

      RETURN f.partner_id AS facility_partner_id,
             f.name AS facility_name,
             f.city AS city,
             f.state AS state,
             distance_miles,
             tx_count,

             // Composite Score (weighted)
             (
               (1000.0 - distance_miles) * 0.40 +  // Geo weight
               (tx_count * 10.0) * 0.25 +           // Transaction history
               50.0                                  // Base score
             ) AS match_score

      ORDER BY match_score DESC
      LIMIT 50

    returns:
      - facility_partner_id: Integer
      - facility_name: String
      - city: String
      - state: String
      - distance_miles: Float
      - tx_count: Integer
      - match_score: Float

  - name: sync_facility_nodes
    description: "Upsert Facility nodes from Odoo"
    cypher: |
      UNWIND $facilities AS facility
      MERGE (f:Facility {partner_id: facility.partner_id})
      SET f.name = facility.name,
          f.company_name = facility.company_name,
          f.latitude = facility.latitude,
          f.longitude = facility.longitude,
          f.city = facility.city,
          f.state = facility.state,
          f.country = facility.country,
          f.accepted_polymers = facility.accepted_polymers,
          f.accepted_forms = facility.accepted_forms,
          f.accepted_source_types = facility.accepted_source_types,
          f.density_min = facility.density_min,
          f.density_max = facility.density_max,
          f.melt_index_min = facility.melt_index_min,
          f.melt_index_max = facility.melt_index_max,
          f.contamination_tolerance_pct = facility.contamination_tolerance_pct,
          f.moisture_tolerance_pct = facility.moisture_tolerance_pct,
          f.min_lot_size_lbs = facility.min_lot_size_lbs,
          f.max_lot_size_lbs = facility.max_lot_size_lbs,
          f.has_wash_line = facility.has_wash_line,
          f.can_reduce_moisture = facility.can_reduce_moisture,
          f.can_remove_metal = facility.can_remove_metal,
          f.can_filter_fr = facility.can_filter_fr,
          f.has_granulator = facility.has_granulator,
          f.has_extruder = facility.has_extruder,
          f.pvc_tolerant = facility.pvc_tolerant,
          f.food_grade_certified = facility.food_grade_certified,
          f.medical_grade_capable = facility.medical_grade_capable,
          f.active = facility.active,
          f.last_synced = datetime($last_synced)

  - name: sync_material_nodes
    description: "Upsert Material nodes from Odoo"
    cypher: |
      UNWIND $materials AS material
      MERGE (m:Material {material_id: material.material_id})
      SET m.partner_id = material.partner_id,
          m.partner_name = material.partner_name,
          m.polymer = material.polymer,
          m.form = material.form,
          m.source_type = material.source_type,
          m.color = material.color,
          m.packaging = material.packaging,
          m.density = material.density,
          m.melt_index = material.melt_index,
          m.contamination_pct = material.contamination_pct,
          m.has_metal = material.has_metal,
          m.has_fr = material.has_fr,
          m.has_pvc = material.has_pvc,
          m.food_grade = material.food_grade,
          m.active = material.active,
          m.last_synced = datetime($last_synced)

  - name: sync_transaction_edges
    description: "Create/update SOLD_TO relationships from transactions"
    cypher: |
      UNWIND $transactions AS tx
      MATCH (m:Material {partner_id: tx.supplier_partner_id, polymer: tx.polymer})
      MATCH (f:Facility {partner_id: tx.buyer_facility_id})
      MERGE (m)-[r:SOLD_TO]->(f)
      ON CREATE SET r.tx_count = 1,
                    r.total_volume_lbs = tx.quantity_lbs,
                    r.last_transaction_date = date(tx.transaction_date)
      ON MATCH SET r.tx_count = r.tx_count + 1,
                   r.total_volume_lbs = r.total_volume_lbs + tx.quantity_lbs,
                   r.last_transaction_date = date(tx.transaction_date)

# ==============================================================================
# Indexes and Constraints
# ==============================================================================
indexes:
  - label: Facility
    fields: [partner_id]
    type: unique

  - label: Facility
    fields: [accepted_polymers]
    type: index

  - label: Material
    fields: [material_id]
    type: unique

  - label: Material
    fields: [partner_id]
    type: index

  - label: Material
    fields: [polymer, form, source_type]
    type: composite

constraints:
  - label: Facility
    property: partner_id
    type: uniqueness

  - label: Material
    property: material_id
    type: uniqueness

# ==============================================================================
# Data Sync Strategy
# ==============================================================================
sync_strategy:
  facility_nodes:
    trigger: "Facility profile write, partner geo update"
    frequency: "On-demand (write hooks)"
    batch_size: 100
    method: "MERGE (upsert)"
    notes: "Triggered by facilityprofile_graph_hooks.py"

  material_nodes:
    trigger: "Material profile write"
    frequency: "On-demand (write hooks)"
    batch_size: 100
    method: "MERGE (upsert)"
    notes: "Triggered by materialprofile_graph_hooks.py"

  transaction_edges:
    trigger: "Transaction state → invoiced/paid"
    frequency: "Nightly cron (for backfill)"
    batch_size: 500
    method: "MERGE (accumulate)"
    notes: "Aggregates tx_count, total_volume_lbs"

  intake_nodes:
    trigger: "Intake match action"
    frequency: "On-demand"
    lifecycle: "Ephemeral (deleted after match)"
    notes: "Not persisted to avoid graph bloat"

# ==============================================================================
# Scoring Weights (v2.0)
# ==============================================================================
scoring:
  weights:
    geographic_proximity: 0.40
    transaction_history: 0.25
    color_match: 0.15
    packaging_match: 0.10
    base_score: 0.10

  formulas:
    match_score: |
      (1000 - distance_miles) * 0.40 +
      (tx_count * 10) * 0.25 +
      (color_match ? 150 : 0) * 0.15 +
      (packaging_match ? 100 : 0) * 0.10 +
      50.0  // base score

  max_score: 1000.0
  min_score: 0.0

# ==============================================================================
# Performance Tuning
# ==============================================================================
performance:
  connection_pool:
    max_size: 50
    connection_timeout: 10.0
    max_transaction_retry_time: 30.0

  query_timeouts:
    match_buyers: 5.0  # seconds
    sync_nodes: 30.0
    sync_edges: 60.0

  batch_sizes:
    facility_sync: 100
    material_sync: 100
    transaction_sync: 500

  recommendations:
    - "Index partner_id on all node types"
    - "Index accepted_polymers for fast filtering"
    - "Use MERGE for idempotent upserts"
    - "Batch sync operations (100-500 records)"
    - "Use APOC for bulk operations (if available)"

# ==============================================================================
# Version History
# ==============================================================================
changelog:
  - version: "2.0.0"
    date: "2026-02-24"
    changes:
      - "Two-stage matching: Capability Matcher → Graph Service"
      - "Added facility_ids parameter to constrain graph search"
      - "Added per-buyer max_radius_miles override"
      - "Added equipment capability gates (has_granulator, etc.)"
      - "Removed intake persistence (ephemeral only)"

  - version: "1.5.0"
    date: "2026-02-23"
    changes:
      - "Added PVC hard gate (pvc_tolerant)"
      - "Added form handling equipment fields"
      - "Separated compounder (company type) from extruder (equipment)"
      - "Synced filler_type and material_attribute seed data"

  - version: "1.0.0"
    date: "2026-02-20"
    changes:
      - "Initial ontology with Facility, Material, Intake nodes"
      - "SOLD_TO relationship for transaction history"
      - "Basic match query with 14 hard gates, 9 soft signals"
