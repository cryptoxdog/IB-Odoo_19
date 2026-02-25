-- Version: 0023
-- Date: 2026-01-17
-- Author: L9 CompoundE3D Integration
-- Description: Add entity/relation embedding tables and KGE prediction infrastructure

-- Enable pgvector extension if not already enabled
CREATE EXTENSION IF NOT EXISTS vector;

-- Entity embeddings table (pgvector for semantic similarity)
CREATE TABLE IF NOT EXISTS entity_embeddings (
    entity_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_name TEXT NOT NULL,
    embedding vector(300) NOT NULL,  -- Adjustable dimension per dataset
    trained_at TIMESTAMP DEFAULT NOW(),
    model_variant TEXT,  -- e.g., "CompoundE3D_S·R·T"
    metadata JSONB,  -- Additional entity metadata
    CONSTRAINT entity_name_unique UNIQUE(entity_name)
);

-- HNSW index for fast similarity search (L2 distance)
CREATE INDEX IF NOT EXISTS idx_entity_embeddings_hnsw
ON entity_embeddings USING hnsw (embedding vector_l2_ops)
WITH (m = 16, ef_construction = 64);

-- Index for entity name lookups
CREATE INDEX IF NOT EXISTS idx_entity_embeddings_name
ON entity_embeddings(entity_name);

-- Relation embeddings table (transformation parameters)
CREATE TABLE IF NOT EXISTS relation_embeddings (
    relation_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    relation_name TEXT NOT NULL,
    transformation_sequence TEXT[],  -- e.g., ['T', 'S', 'R']
    parameters JSONB NOT NULL,  -- Operator params: {T: [vx,vy,vz], S: [sx,sy,sz], R: [yaw,pitch,roll], ...}
    symmetry_type TEXT CHECK (symmetry_type IN ('symmetric', 'asymmetric', 'hierarchical')),
    trained_at TIMESTAMP DEFAULT NOW(),
    model_variant TEXT,
    metadata JSONB,
    CONSTRAINT relation_name_unique UNIQUE(relation_name)
);

-- Index for relation name lookups
CREATE INDEX IF NOT EXISTS idx_relation_embeddings_name
ON relation_embeddings(relation_name);

-- KGE predictions table (link prediction results)
CREATE TABLE IF NOT EXISTS kge_predictions (
    prediction_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    head_entity_id UUID NOT NULL REFERENCES entity_embeddings(entity_id) ON DELETE CASCADE,
    relation_id UUID NOT NULL REFERENCES relation_embeddings(relation_id) ON DELETE CASCADE,
    tail_entity_id UUID NOT NULL REFERENCES entity_embeddings(entity_id) ON DELETE CASCADE,
    confidence FLOAT NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    rank INTEGER NOT NULL,  -- Rank among all candidates
    distance FLOAT,  -- L2 distance (lower = more confident)
    predicted_at TIMESTAMP DEFAULT NOW(),
    approved BOOLEAN DEFAULT FALSE,
    approved_by TEXT,
    approved_at TIMESTAMP,
    source TEXT DEFAULT 'compoundE3D',
    model_variant TEXT,
    metadata JSONB
);

-- Indexes for fast lookup of predictions by entity
CREATE INDEX IF NOT EXISTS idx_kge_predictions_head
ON kge_predictions(head_entity_id, confidence DESC);

CREATE INDEX IF NOT EXISTS idx_kge_predictions_tail
ON kge_predictions(tail_entity_id, confidence DESC);

CREATE INDEX IF NOT EXISTS idx_kge_predictions_relation
ON kge_predictions(relation_id, confidence DESC);

-- Index for unapproved predictions
CREATE INDEX IF NOT EXISTS idx_kge_predictions_unapproved
ON kge_predictions(approved, confidence)
WHERE approved = FALSE;

-- Relation properties for modeling hints
CREATE TABLE IF NOT EXISTS relation_properties (
    relation_id UUID PRIMARY KEY REFERENCES relation_embeddings(relation_id) ON DELETE CASCADE,
    is_symmetric BOOLEAN DEFAULT FALSE,
    is_transitive BOOLEAN DEFAULT FALSE,
    is_hierarchical BOOLEAN DEFAULT FALSE,
    hierarchy_score FLOAT,  -- Krackhardt score (0-1)
    curvature_estimate FLOAT,  -- ξGr metric for hyperbolic geometry
    multiplicity_count INTEGER DEFAULT 1,  -- Number of co-existing relations between same (h,t)
    example_triples JSONB,  -- Sample triples for this relation
    updated_at TIMESTAMP DEFAULT NOW()
);

-- KGE training checkpoints table
CREATE TABLE IF NOT EXISTS kge_training_checkpoints (
    checkpoint_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    model_variant TEXT NOT NULL,
    operator_sequence TEXT[] NOT NULL,
    epoch INTEGER NOT NULL,
    loss FLOAT NOT NULL,
    mrr FLOAT NOT NULL,
    hits_at_1 FLOAT,
    hits_at_3 FLOAT,
    hits_at_10 FLOAT,
    parameter_count INTEGER,
    training_duration_seconds INTEGER,
    checkpoint_path TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    metadata JSONB
);

-- Index for checkpoint retrieval
CREATE INDEX IF NOT EXISTS idx_kge_checkpoints_variant_mrr
ON kge_training_checkpoints(model_variant, mrr DESC);

-- Audit log for KGE operations
CREATE TABLE IF NOT EXISTS kge_audit_log (
    log_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    operation TEXT NOT NULL,  -- 'train', 'predict', 'approve', 'circuit_break', etc.
    actor TEXT NOT NULL,  -- 'L', 'Igor', 'Cursor', 'system'
    details JSONB NOT NULL,
    timestamp TIMESTAMP DEFAULT NOW()
);

-- Index for audit log queries
CREATE INDEX IF NOT EXISTS idx_kge_audit_log_timestamp
ON kge_audit_log(timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_kge_audit_log_actor
ON kge_audit_log(actor, timestamp DESC);

-- Function to auto-update relation properties based on predictions
CREATE OR REPLACE FUNCTION update_relation_properties()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE relation_properties
    SET multiplicity_count = (
        SELECT COUNT(DISTINCT (head_entity_id, tail_entity_id))
        FROM kge_predictions
        WHERE relation_id = NEW.relation_id
        AND approved = TRUE
    ),
    updated_at = NOW()
    WHERE relation_id = NEW.relation_id;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to update relation properties on prediction approval
CREATE TRIGGER trigger_update_relation_properties
AFTER UPDATE OF approved ON kge_predictions
FOR EACH ROW
WHEN (NEW.approved = TRUE)
EXECUTE FUNCTION update_relation_properties();

-- View for high-confidence unapproved predictions
CREATE OR REPLACE VIEW kge_predictions_pending_approval AS
SELECT
    p.prediction_id,
    e1.entity_name AS head_entity,
    r.relation_name,
    e2.entity_name AS tail_entity,
    p.confidence,
    p.rank,
    p.predicted_at,
    p.model_variant
FROM kge_predictions p
JOIN entity_embeddings e1 ON p.head_entity_id = e1.entity_id
JOIN relation_embeddings r ON p.relation_id = r.relation_id
JOIN entity_embeddings e2 ON p.tail_entity_id = e2.entity_id
WHERE p.approved = FALSE
ORDER BY p.confidence DESC;

-- Grants (adjust based on L9 role system)
GRANT SELECT, INSERT, UPDATE, DELETE ON entity_embeddings TO l9_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON relation_embeddings TO l9_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON kge_predictions TO l9_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON relation_properties TO l9_app;
GRANT SELECT, INSERT ON kge_training_checkpoints TO l9_app;
GRANT SELECT, INSERT ON kge_audit_log TO l9_app;
GRANT SELECT ON kge_predictions_pending_approval TO l9_app;

-- Migration complete
COMMENT ON TABLE entity_embeddings IS 'CompoundE3D entity embeddings (300D vectors)';
COMMENT ON TABLE relation_embeddings IS 'CompoundE3D relation transformation parameters';
COMMENT ON TABLE kge_predictions IS 'Link prediction results awaiting approval or ingestion';
