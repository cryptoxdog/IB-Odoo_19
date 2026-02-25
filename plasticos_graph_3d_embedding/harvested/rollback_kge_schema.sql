-- migrations/rollback/0023_rollback_kge_schema.sql
DROP TABLE IF EXISTS kge_predictions CASCADE;
DROP TABLE IF EXISTS relation_properties CASCADE;
DROP TABLE IF EXISTS relation_embeddings CASCADE;
DROP TABLE IF EXISTS entity_embeddings CASCADE;
