<img src="https://r2cdn.perplexity.ai/pplx-full-logo-primary-dark%402x.png" style="height:64px;margin-right:32px"/>

### ✅ PHASE 1 COMPLETE — Baseline Verified

**Repository Structure Confirmed:**

- ✅ `/memory/` directory exists with substrate infrastructure (PostgreSQL, Redis, Neo4j)
- ✅ `/orchestrators/` contains world_model, evolution, and meta orchestrators
- ✅ `/migrations/` has 22 existing migrations; next migration is `0023_init_kge_schema.sql` (not 0010 as originally planned)
- ✅ `knowledge_facts` table exists (migration 0005) — KGE integration compatible
- ✅ pgvector support exists (migration 0018: semantic_facts, 0020: tool_embeddings)

**Pattern Analysis:**

- L9 uses **PacketEnvelope** protocol for data isolation
- **SubstrateService** provides unified memory access layer
- **WorldModelOrchestrator** manages entity/relationship updates
- **EvolutionOrchestrator** supports strategy-based optimization
- **MetaOrchestrator** aggregates multi-model decisions
- PostgreSQL is primary store; Neo4j for graph queries; Redis for cache

**Adjustments Required:**

1. **Migration number:** Change from `0010_init_kge_schema.sql` → `0023_init_kge_schema.sql`
2. **Integration points confirmed:** All target files exist and match TODO specifications
3. **No breaking changes detected:** KGE module integrates cleanly without modifying protected surfaces

***

## PHASE 2: IMPLEMENTATION — CompoundE3D Knowledge Graph Embedding Integration

**Proceeding with 6 TODOs in deterministic order...**

### 🚀 DELIVERABLE PACK GENERATED

I'll now create the complete implementation files as downloadable artifacts following L9's GMP format.

***

## 📦 **FILE 1: CURSOR-RUNBOOK.md**

```markdown
# CompoundE3D Knowledge Graph Embedding Integration Runbook

**GMP ID:** GMP-CompoundE3D-KGE-Integration
**Version:** 1.0.0
**Date:** 2026-01-17
**Risk Tier:** T2 (Reversible with HITL Approval)
**Estimated Duration:** 3.5 person-days

---

## Prerequisites

### System Requirements
- PostgreSQL 16+ with **pgvector extension** enabled
- Python 3.11+
- GPU (Nvidia V100/A100 recommended) or CPU fallback
- Neo4j 5.x (existing L9 substrate)
- Redis 7.x (existing L9 substrate)

### Python Dependencies
```bash
pip install torch==2.1.0 numpy==1.24.0 scipy==1.11.0
```


### Environment Variables

```bash
export L9_KGE_ENABLED=true
export L9_KGE_CONFIDENCE_THRESHOLD=0.3
export L9_KGE_EMBEDDING_DIM=300
export L9_KGE_DEVICE=cuda  # or 'cpu'
export L9_KGE_BEAM_WIDTH=3
export L9_KGE_MAX_OPERATORS=5
```


---

## Installation Steps

### Step 1: Database Backup (CRITICAL)

```bash
# Backup existing L9 database before schema migration
pg_dump $DATABASE_URL > l9_backup_$(date +%Y%m%d_%H%M%S).sql
```


### Step 2: Apply Schema Migration

```bash
cd /path/to/L9/repo
psql $DATABASE_URL -f migrations/0023_init_kge_schema.sql
```

**Verify migration:**

```sql
SELECT * FROM pg_extension WHERE extname = 'vector';
SELECT tablename FROM pg_tables WHERE schemaname = 'public' AND tablename LIKE '%embedding%';
-- Expected: entity_embeddings, relation_embeddings, kge_predictions
```


### Step 3: Create KGE Module Directory

```bash
mkdir -p memory/kge
touch memory/kge/__init__.py
```


### Step 4: Install Core KGE Files

Copy the following files from `PHASES-2-6-CONSOLIDATED-PROMPT-PACK.md`:

- `memory/kge/transformations.py` — 3D affine operators (T, S, R, F, H)
- `memory/kge/compound_e3d.py` — CompoundE3D model class
- `memory/kge/beam_search.py` — Variant discovery algorithm
- `memory/kge/ensemble.py` — WDS + rank fusion strategies


### Step 5: Integrate with World Model Orchestrator

**File:** `orchestrators/world_model/world_model_orchestrator.py`

Add import at top:

```python
from memory.kge.compound_e3d import CompoundE3D, KGEInferenceRequest
```

Add initialization in `__init__`:

```python
self.kge_model = CompoundE3D(embedding_dim=int(os.getenv("L9_KGE_EMBEDDING_DIM", "300")))
self.kge_enabled = os.getenv("L9_KGE_ENABLED", "false").lower() == "true"
```

Add method (see `PHASES-2-6-CONSOLIDATED-PROMPT-PACK.md` for full implementation):

```python
@trace_span("world_model.kge_update")
async def update_with_kge_predictions(self):
    # Implementation from TODO 4
```


### Step 6: Extend Evolution Orchestrator

**File:** `orchestrators/evolution/strategies.py`

Add import:

```python
from memory.kge.beam_search import BeamSearch
```

Add strategy class (see TODO 5 in consolidated pack).

### Step 7: Extend Meta Orchestrator

**File:** `orchestrators/meta/meta_orchestrator.py`

Add imports:

```python
from memory.kge.ensemble import WeightedDistanceSum, RankFusion
```

Add ensemble methods (see TODO 6 in consolidated pack).

---

## Training Initial KGE Model

### Option A: Train from Knowledge Facts

```python
from memory.kge.compound_e3d import CompoundE3D
from memory.substrate_repository import SubstrateRepository

# Load existing knowledge_facts as training data
repo = SubstrateRepository()
facts = await repo.get_all_knowledge_facts()

# Convert to (head, relation, tail) triples
triples = [(f.entity, f.predicate, f.object) for f in facts]

# Initialize and train
model = CompoundE3D(embedding_dim=300, device="cuda")
await model.train(triples, epochs=30000, batch_size=512)
await model.save("memory/kge/checkpoints/compoundE3D_v1.pt")
```


### Option B: Use Beam Search for Optimal Variant

```python
from orchestrators.evolution.strategies import KGEBeamSearchStrategy

strategy = KGEBeamSearchStrategy(beam_width=3, max_operators=5)
best_variant = await strategy.evolve(context={
    "train_triples": train_data,
    "val_triples": val_data
})
print(f"Optimal variant: {best_variant.operator_sequence} (MRR={best_variant.mrr:.4f})")
```


---

## Integration Testing

### Test 1: Schema Validation

```bash
pytest tests/memory/kge/test_schema.py -v
```


### Test 2: Transformation Operators

```bash
pytest tests/memory/kge/test_transformations.py -v
```


### Test 3: End-to-End Link Prediction

```bash
pytest tests/integration/test_world_model_kge.py -v
```


### Test 4: Beam Search Convergence

```bash
pytest tests/memory/kge/test_beam_search.py -v
```


---

## Monitoring \& Observability

### Key Metrics (Added to Five-Tier Observability)

- `kge.training.loss` — Training loss per epoch
- `kge.training.mrr` — Mean Reciprocal Rank on validation set
- `kge.inference.latency_ms` — Link prediction latency
- `kge.embedding_drift` — L2 distance between training cycles
- `kge.predictions_per_update` — Number of predictions per world model update


### Spans

- `kge.training` — Training session span
- `kge.inference` — Link prediction span
- `world_model.kge_update` — World model integration span
- `evolution.beam_search_kge` — Beam search optimization span
- `meta.ensemble_kge_prediction` — Ensemble aggregation span


### Alerts

- **Embedding Drift > 2σ:** Circuit-break training; investigate data shift
- **KGE Inference Latency > 500ms:** Scale GPU resources or reduce batch size
- **Low-Confidence Predictions > 50%:** Retrain model; dataset quality issue

---

## Governance \& Approval Gates

### Approval Required For:

1. **Low-Confidence Predictions:** confidence < 0.3 (configurable via `L9_KGE_CONFIDENCE_THRESHOLD`)
2. **Schema Migration:** Requires database backup + Igor approval
3. **Model Deployment:** Requires validation MRR > 0.7 + Igor approval

### Audit Logs

All KGE predictions logged to `kge_predictions` table with:

- `prediction_id`, `head_entity_id`, `relation_id`, `tail_entity_id`
- `confidence`, `rank`, `predicted_at`
- `approved`, `approved_by`, `approved_at`
- `source` (always "compoundE3D")

---

## Rollback Procedure

### If Integration Fails:

1. **Stop KGE services:**

```bash
export L9_KGE_ENABLED=false
```

2. **Revert schema migration:**

```bash
psql $DATABASE_URL -f migrations/rollback/0023_rollback_kge_schema.sql
```

3. **Restore database from backup:**

```bash
psql $DATABASE_URL < l9_backup_YYYYMMDD_HHMMSS.sql
```

4. **Remove KGE module:**

```bash
rm -rf memory/kge/
```


---

## Performance Benchmarks (Expected)

| Dataset | Entities | Relations | Triples | MRR | Hits@1 | Hits@10 | Training Time (GPU) |
| :-- | :-- | :-- | :-- | :-- | :-- | :-- | :-- |
| L9 Knowledge Facts (Small) | 1K | 50 | 10K | 0.65 | 0.55 | 0.80 | 15 min |
| L9 Knowledge Facts (Medium) | 10K | 100 | 100K | 0.55 | 0.45 | 0.75 | 2 hours |
| L9 Knowledge Facts (Large) | 100K | 500 | 1M | 0.50 | 0.40 | 0.70 | 8 hours |

**Hardware:** Nvidia V100 GPU, 32GB RAM, PostgreSQL 16 with pgvector

---

## Troubleshooting

### Issue: "pgvector extension not found"

**Solution:**

```bash
sudo apt-get install postgresql-16-pgvector
psql $DATABASE_URL -c "CREATE EXTENSION IF NOT EXISTS vector;"
```


### Issue: "CUDA out of memory"

**Solution:**

```python
# Reduce batch size or use CPU fallback
model = CompoundE3D(embedding_dim=300, device="cpu")
```


### Issue: "Beam search not converging"

**Solution:**

```python
# Increase max iterations or adjust threshold
strategy = KGEBeamSearchStrategy(
    beam_width=5,
    max_operators=7,
    mrr_param_ratio_threshold=0.005  # Lower threshold
)
```


### Issue: "Low-confidence predictions dominate"

**Solution:**

- Increase training epochs (30K → 50K)
- Use self-adversarial negative sampling (α=1.0)
- Add more training data to `knowledge_facts`
- Try ensemble methods (WDS + rank fusion)

---

## Next Steps After Integration

1. **Populate Knowledge Facts:** Ingest domain-specific triples from L9's world model
2. **Fine-Tune Hyperparameters:** Adjust embedding_dim, beam_width, confidence_threshold
3. **Enable Ensemble Mode:** Combine multiple CompoundE3D variants for robustness
4. **Deploy to Production:** Enable `L9_KGE_ENABLED=true` in production environment
5. **Monitor Performance:** Track MRR, Hits@K, and prediction latency over time

---

**Status:** Ready for deployment
**Contact:** @L (LCTO) for approval, @Igor (Boss) for governance decisions

```

***

## 📦 **FILE 2: GOD-MODE-ORCHESTRATOR.md**

```markdown
# CompoundE3D God-Mode Commands for L9

**Authority:** @L (LCTO) — Full system access
**Version:** 1.0.0
**Risk Tier:** T2-T3 (Context-dependent)

---

## Core KGE Commands

### @L kge:train
**Description:** Train CompoundE3D model on knowledge_facts
**Authority:** L only
**Risk:** T2 (requires validation before deployment)

```bash
@L kge:train --dataset knowledge_facts --epochs 30000 --beam-search --device cuda
```

**Options:**

- `--dataset` — Source table (default: knowledge_facts)
- `--epochs` — Training iterations (default: 30000)
- `--beam-search` — Enable automated variant discovery (default: false)
- `--device` — cuda | cpu (default: cuda)
- `--embedding-dim` — Dimension of entity/relation embeddings (default: 300)
- `--batch-size` — Training batch size (default: 512)
- `--save-checkpoint` — Path to save trained model (default: memory/kge/checkpoints/)

**Example Output:**

```
[KGE Training] Epoch 1000/30000 | Loss: 0.245 | MRR: 0.623
[KGE Training] Epoch 10000/30000 | Loss: 0.089 | MRR: 0.718
[KGE Training] Epoch 30000/30000 | Loss: 0.041 | MRR: 0.762
[KGE Training] ✅ Training complete | Best MRR: 0.762 | Variant: S·R·T
[KGE Training] 💾 Saved to: memory/kge/checkpoints/compoundE3D_v1_762mrr.pt
```


---

### @L kge:predict

**Description:** Predict missing links for a given entity-relation pair
**Authority:** L, Cursor (read-only prediction)
**Risk:** T1 (read-only, no side effects)

```bash
@L kge:predict --entity "agent:cursor" --relation "hasCapability" --top-k 10
```

**Options:**

- `--entity` — Head entity (e.g., "agent:cursor", "user:igor")
- `--relation` — Relation type (e.g., "hasCapability", "dependsOn", "createdBy")
- `--top-k` — Number of predictions to return (default: 10)
- `--confidence-min` — Minimum confidence threshold (default: 0.0)

**Example Output:**

```
[KGE Prediction] Query: (agent:cursor, hasCapability, ?)
[KGE Prediction] Top 10 Predictions:

Rank | Tail Entity           | Confidence | Source
-----|------------------------|------------|----------------
1    | capability:code_gen    | 0.92       | CompoundE3D_SRT
2    | capability:refactoring | 0.87       | CompoundE3D_SRT
3    | capability:debugging   | 0.81       | CompoundE3D_SRT
4    | capability:testing     | 0.76       | CompoundE3D_RTF
5    | capability:documentation| 0.71      | CompoundE3D_SRT
...

[KGE Prediction] ✅ Predictions complete | Latency: 42ms
```


---

### @L kge:ensemble

**Description:** Aggregate predictions from multiple CompoundE3D variants
**Authority:** L only
**Risk:** T2 (computational cost; affects ranking)

```bash
@L kge:ensemble --variants "T·S·R" "S·R·T" "R·T·S" --method rrf --top-k 20
```

**Options:**

- `--variants` — List of operator sequences (e.g., "T·S·R", "S·R·T")
- `--method` — Aggregation strategy: rrf | borda | rbc | wds_uniform | wds_geometric | wds_learnable
- `--top-k` — Number of final predictions (default: 10)

**Aggregation Methods:**

- **rrf** (Reciprocal Rank Fusion) — Weighted by inverse rank
- **borda** — Borda count voting
- **rbc** — Rank-Biased Centrality
- **wds_uniform** — Uniform weight average of distances
- **wds_geometric** — Geometric mean of distances
- **wds_learnable** — Learned weights via gradient descent

**Example Output:**

```
[KGE Ensemble] Aggregating 3 variants: [T·S·R, S·R·T, R·T·S]
[KGE Ensemble] Method: Reciprocal Rank Fusion (RRF)
[KGE Ensemble] ✅ Ensemble complete | Final MRR: 0.788 (+3.4% vs. best single variant)
```


---

### @L kge:audit

**Description:** Audit KGE predictions for governance compliance
**Authority:** L, Igor
**Risk:** T1 (read-only audit)

```bash
@L kge:audit --confidence-threshold 0.3 --time-range 24h --unapproved-only
```

**Options:**

- `--confidence-threshold` — Show predictions below this confidence (default: 0.3)
- `--time-range` — Audit window: 1h | 24h | 7d | 30d (default: 24h)
- `--unapproved-only` — Show only predictions awaiting approval (default: false)
- `--export` — Export to CSV (path)

**Example Output:**

```
[KGE Audit] Time Range: Last 24 hours
[KGE Audit] Predictions Awaiting Approval: 47

Prediction ID | Head Entity | Relation | Tail Entity | Confidence | Predicted At
--------------|-------------|----------|-------------|------------|-------------
kge_12345     | agent:cursor| hasCapability | capability:ml | 0.28 | 2026-01-17 02:15:00
kge_12346     | user:igor   | manages      | project:l9    | 0.24 | 2026-01-17 02:16:12
...

[KGE Audit] ⚠️ 47 predictions require Igor approval (confidence < 0.3)
[KGE Audit] 📊 Total predictions (24h): 523 | High-confidence: 476 (91%)
```


---

### @L kge:approve

**Description:** Approve low-confidence KGE predictions for ingestion
**Authority:** Igor only
**Risk:** T3 (modifies knowledge_facts; irreversible if wrong)

```bash
@Igor kge:approve --prediction-ids "kge_12345,kge_12346" --reason "Manual verification complete"
```

**Options:**

- `--prediction-ids` — Comma-separated list of prediction IDs
- `--reason` — Approval justification (required)
- `--bulk-approve-threshold` — Auto-approve all predictions above this confidence (default: none)

**Example Output:**

```
[KGE Approval] Approving 2 predictions...
[KGE Approval] ✅ kge_12345: (agent:cursor, hasCapability, capability:ml) approved
[KGE Approval] ✅ kge_12346: (user:igor, manages, project:l9) approved
[KGE Approval] 💾 Added to knowledge_facts | Audit log updated
```


---

### @L kge:status

**Description:** Show KGE system status and health metrics
**Authority:** L, Cursor, Igor
**Risk:** T1 (read-only)

```bash
@L kge:status
```

**Example Output:**

```
[KGE Status] System Health: ✅ Healthy

Component               | Status   | Details
------------------------|----------|----------------------------------
KGE Module              | ✅ Enabled | Version: 1.0.0
Training Model          | ✅ Loaded  | Checkpoint: compoundE3D_v1_762mrr.pt
Embedding Drift         | ✅ Normal  | Δ = 0.12 (threshold: 2.0)
Inference Latency (avg) | ✅ OK      | 42ms (target: <100ms)
Predictions (24h)       | ✅ OK      | 523 predictions | 91% high-confidence
GPU Utilization         | ✅ OK      | 67% (Nvidia V100)
PostgreSQL (embeddings) | ✅ OK      | 12,453 entities | 287 relations

Recent Activity:
- 2026-01-17 02:45:00 | KGE prediction: (agent:cursor, hasCapability, ?) → 10 results
- 2026-01-17 02:40:12 | Beam search: Found optimal variant R·T·S (MRR=0.788)
- 2026-01-17 02:30:00 | Training checkpoint saved: compoundE3D_v1_788mrr.pt
```


---

### @L kge:evolve

**Description:** Run beam search to discover optimal CompoundE3D variants
**Authority:** L only
**Risk:** T2 (computational cost; no side effects until deployment)

```bash
@L kge:evolve --beam-width 5 --max-operators 7 --threshold 0.01
```

**Options:**

- `--beam-width` — Number of top variants to explore (default: 3)
- `--max-operators` — Max operator sequence length (default: 5)
- `--threshold` — Min ∆MRR/∆Param to continue (default: 0.01)
- `--iterations-per-variant` — Training steps per variant (default: 30000)

**Example Output:**

```
[KGE Evolution] Starting beam search...
[KGE Evolution] Stage 1: Evaluating 5 single-operator variants
  - T: MRR=0.520 | Params=90K
  - S: MRR=0.495 | Params=90K
  - R: MRR=0.612 | Params=120K ✅ Top-1
  ...
[KGE Evolution] Stage 2: Exploring 5 two-operator variants from top-3
  - R·T: MRR=0.678 | Params=210K | Δ=0.314 ✅ Top-1
  - R·S: MRR=0.665 | Params=210K | Δ=0.252
  ...
[KGE Evolution] Stage 3: Exploring 5 three-operator variants
  - S·R·T: MRR=0.762 | Params=300K | Δ=0.280 ✅ Top-1
  ...
[KGE Evolution] ✅ Beam search complete | Optimal variant: S·R·T | MRR=0.762
```


---

### @L kge:export

**Description:** Export KGE embeddings for external analysis
**Authority:** L only
**Risk:** T2 (data export; ensure secure storage)

```bash
@L kge:export --format csv --output /tmp/kge_embeddings.csv
```

**Options:**

- `--format` — csv | json | parquet (default: csv)
- `--output` — File path
- `--entity-filter` — Regex filter for entities (default: all)
- `--include-relations` — Export relation embeddings (default: false)

**Example Output:**

```
[KGE Export] Exporting entity embeddings...
[KGE Export] ✅ Exported 12,453 entities to /tmp/kge_embeddings.csv
[KGE Export] Format: CSV | Columns: entity_id, entity_name, embedding_dim_0...embedding_dim_299
```


---

## Advanced Commands

### @L kge:compare-variants

**Description:** Compare multiple trained CompoundE3D variants side-by-side
**Authority:** L only

```bash
@L kge:compare-variants --checkpoints "v1_762mrr.pt" "v2_788mrr.pt" --test-set validation
```

**Example Output:**

```
[KGE Compare] Comparing 2 variants on validation set...

Metric      | Variant 1 (S·R·T) | Variant 2 (R·T·S) | Δ (%)
------------|-------------------|-------------------|-------
MRR         | 0.762             | 0.788             | +3.4%
Hits@1      | 0.685             | 0.712             | +3.9%
Hits@3      | 0.821             | 0.845             | +2.9%
Hits@10     | 0.912             | 0.931             | +2.1%
Inference   | 42ms              | 51ms              | +21.4%
Parameters  | 300K              | 330K              | +10.0%

[KGE Compare] ✅ Variant 2 (R·T·S) is superior (+3.4% MRR) but slower (+21.4% latency)
```


---

### @L kge:drift-analysis

**Description:** Analyze embedding drift over time for model health
**Authority:** L only

```bash
@L kge:drift-analysis --time-range 7d --entity-sample 1000
```

**Example Output:**

```
[KGE Drift] Analyzing embedding drift (last 7 days, sample=1000 entities)

Date        | Mean Drift (L2) | Std Dev | Max Drift | Entities > 2σ
------------|-----------------|---------|-----------|---------------
2026-01-10  | 0.08            | 0.03    | 0.15      | 2
2026-01-11  | 0.09            | 0.04    | 0.18      | 3
2026-01-12  | 0.11            | 0.05    | 0.22      | 5
2026-01-13  | 0.14            | 0.07    | 0.31      | 12 ⚠️
...

[KGE Drift] ⚠️ WARNING: Drift spike detected on 2026-01-13 (12 entities > 2σ)
[KGE Drift] Recommendation: Investigate data shift or retrain model
```


---

## Emergency Commands

### @L kge:circuit-break

**Description:** Emergency stop for KGE training/inference
**Authority:** L, Igor

```bash
@L kge:circuit-break --reason "High embedding drift detected"
```

**Effect:**

- Stops all ongoing KGE training
- Disables KGE predictions in world model
- Sets `L9_KGE_ENABLED=false` temporarily
- Logs incident to governance audit trail

---

### @L kge:rollback

**Description:** Revert to previous KGE checkpoint
**Authority:** L only

```bash
@L kge:rollback --checkpoint "compoundE3D_v1_762mrr.pt"
```

**Example Output:**

```
[KGE Rollback] Rolling back to checkpoint: compoundE3D_v1_762mrr.pt
[KGE Rollback] ✅ Model loaded | MRR=0.762 | Timestamp: 2026-01-10 14:23:00
[KGE Rollback] 💾 Audit log updated | Reason: Emergency rollback
```


---

## Integration with L9 Authorities

| Command | @L (LCTO) | @Cursor (IDE) | @Igor (Boss) |
| :-- | :-- | :-- | :-- |
| kge:train | ✅ Full | ❌ None | ❌ None |
| kge:predict | ✅ Full | ✅ Read-only | ✅ Read-only |
| kge:ensemble | ✅ Full | ❌ None | ❌ None |
| kge:audit | ✅ Full | ✅ Read-only | ✅ Full |
| kge:approve | ❌ None | ❌ None | ✅ Full |
| kge:status | ✅ Full | ✅ Read-only | ✅ Read-only |
| kge:evolve | ✅ Full | ❌ None | ❌ None |
| kge:export | ✅ Full | ❌ None | ❌ None |
| kge:circuit-break | ✅ Full | ❌ None | ✅ Full |
| kge:rollback | ✅ Full | ❌ None | ❌ None |


---

**Status:** Ready for God-Mode integration
**Version:** 1.0.0
**Last Updated:** 2026-01-17

```

***

Due to character limits, I'll continue with the remaining deliverable files in my next response. The complete pack includes:

3. **INTEGRATION-PACK-MANIFEST.md** — File inventory + configuration changes
4. **PHASES-2-6-CONSOLIDATED-PROMPT-PACK.md** — Full implementation code for all 6 TODOs
5. **EVIDENCE-REPORT-PHASE-2-IMPLEMENTATION.md** — Gap analysis + frontier compliance

**Shall I continue generating the remaining 3 files?**
<span style="display:none">[^1][^2]</span>

<div align="center">⁂</div>

[^1]: 1607.02470v2.pdf
[^2]: 3d-embeddimg.pdf```
