// ============================================================
// PLASTOS GRAPH CONSTRAINTS
// Idempotent | Neo4j 5.x | Cluster Safe
// ============================================================

// ONTOLOGY
CREATE CONSTRAINT polymer_name IF NOT EXISTS
FOR (n:Polymer) REQUIRE n.name IS UNIQUE;

CREATE CONSTRAINT form_name IF NOT EXISTS
FOR (n:Form) REQUIRE n.name IS UNIQUE;

CREATE CONSTRAINT color_name IF NOT EXISTS
FOR (n:Color) REQUIRE n.name IS UNIQUE;

CREATE CONSTRAINT filler_name IF NOT EXISTS
FOR (n:FillerType) REQUIRE n.name IS UNIQUE;

CREATE CONSTRAINT process_name IF NOT EXISTS
FOR (n:Process) REQUIRE n.name IS UNIQUE;

CREATE CONSTRAINT certification_name IF NOT EXISTS
FOR (n:Certification) REQUIRE n.name IS UNIQUE;

CREATE CONSTRAINT application_name IF NOT EXISTS
FOR (n:Application) REQUIRE n.name IS UNIQUE;

// SUPPLY
CREATE CONSTRAINT material_profile_id IF NOT EXISTS
FOR (n:MaterialProfile) REQUIRE n.profile_id IS UNIQUE;

CREATE CONSTRAINT intake_id IF NOT EXISTS
FOR (n:Intake) REQUIRE n.intake_id IS UNIQUE;

// DEMAND
CREATE CONSTRAINT facility_id IF NOT EXISTS
FOR (n:Facility) REQUIRE n.facility_id IS UNIQUE;

// QUALITY
CREATE CONSTRAINT tier_id IF NOT EXISTS
FOR (n:QualityTier) REQUIRE n.tier_id IS UNIQUE;

// KB
CREATE CONSTRAINT grade_id IF NOT EXISTS
FOR (n:Grade) REQUIRE n.grade_id IS UNIQUE;

CREATE CONSTRAINT rule_id IF NOT EXISTS
FOR (n:InferenceRule) REQUIRE n.rule_id IS UNIQUE;

// TRANSACTIONS
CREATE CONSTRAINT txn_id IF NOT EXISTS
FOR (n:Transaction) REQUIRE n.txn_id IS UNIQUE;

// INDEXES
CREATE INDEX mp_mfi IF NOT EXISTS FOR (n:MaterialProfile) ON (n.mfi);
CREATE INDEX mp_filler IF NOT EXISTS FOR (n:MaterialProfile) ON (n.filler_pct);
CREATE INDEX mp_contam IF NOT EXISTS FOR (n:MaterialProfile) ON (n.contamination_pct);
CREATE INDEX facility_mfi IF NOT EXISTS FOR (n:Facility) ON (n.min_mfi, n.max_mfi);
