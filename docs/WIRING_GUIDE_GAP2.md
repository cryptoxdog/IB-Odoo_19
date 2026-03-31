# PlasticOS GAP-2 Wiring Guide

## What This Pack Fixes

| Gap | Root Cause | Fix |
|-----|-----------|-----|
| Match results never persisted to `plasticos.match.result` | `intake_extension.py` only wrote to `intake.match` lines | New `MatchResultWriter` AbstractModel + patch to `intake_extension.py` |
| `typical_price` always 0.0 in offers | `intake_extension.py` hardcoded `"typical_price": 0.0` | Removed hardcode; now reads `m.get("typical_price") or 0.0` from matcher output |
| `plasticos.offer` created with price 0 | No bridge between match line price and offer | New `offer_price_bridge.py` auto-fills `price_per_lb` from match line on create |
| No run_id for deduplication | Matching ran without tracking run ID | UUID4 generated per run, threaded through `persist_match_lines` |
| ICP defaults never seeded on install | No post-migrate hook | New `19.0.2.1.0/post-migrate.py` seeds stub/enabled/geo defaults |

---

## File-by-File Insertion Instructions

### 1. `plasticos_buyer_match_engine/models/match_result_writer.py`
**Action:** Create new file (does not exist in repo)
```
cp match_result_writer.py plasticos_buyer_match_engine/models/match_result_writer.py
```
**Wires into:**
- `__init__.py` via `from . import match_result_writer`
- Called by `intake_extension.py` → `self.env["plasticos.match.result.writer"].persist_match_lines(...)`
- Writes to `plasticos.match.result` (already exists in `plasticos_matching`)

**No server restart required if hotloaded during dev; requires `-u plasticos_buyer_match_engine` in prod.**

---

### 2. `plasticos_buyer_match_engine/models/intake_extension.py`
**Action:** Replace existing file with `intake_extension_patched.py`
```
cp intake_extension_patched.py plasticos_buyer_match_engine/models/intake_extension.py
```
**Before (line ~60):**
```python
"typical_price": 0.0,  # populated when Cypher pulls avg_price_per_lb
```
**After:**
```python
"typical_price": m.get("typical_price") or 0.0,
```
**Also adds (after match_line_ids writes, before status update):**
```python
if "plasticos.match.result.writer" in self.env:
    self.env["plasticos.match.result.writer"].persist_match_lines(record, matches, run_id=run_id)
```

**Requires:** `-u plasticos_buyer_match_engine`

---

### 3. `plasticos_buyer_match_engine/models/__init__.py`
**Action:** Replace with `__init___patched.py`
```
cp plasticos_buyer_match_engine/models/__init___patched.py \
   plasticos_buyer_match_engine/models/__init__.py
```
**Adds:** `from . import match_result_writer`
All other imports preserved.

---

### 4. `plasticos_buyer_match_engine/security/ir.model.access.csv`
**Action:** Append rows from `ir.model.access_append.csv`
```
cat ir.model.access_append.csv >> plasticos_buyer_match_engine/security/ir.model.access.csv
```
Adds 2 ACL rows for `plasticos.match.result.writer` (AbstractModel needs ACL entries).

---

### 5. `plasticos_buyer_match_engine/migrations/19.0.2.1.0/post-migrate.py`
**Action:** Create new directory + file
```
mkdir -p plasticos_buyer_match_engine/migrations/19.0.2.1.0
cp migrations/19.0.2.1.0/__init__.py plasticos_buyer_match_engine/migrations/19.0.2.1.0/
cp migrations/19.0.2.1.0/post-migrate.py plasticos_buyer_match_engine/migrations/19.0.2.1.0/
```
**Also bump `__manifest__.py` version to `19.0.2.1.0` to trigger migration.**

```python
# __manifest__.py line ~2:
"version": "19.0.2.1.0",   # was "19.0.2.0.0"
```

Requires: `-u plasticos_buyer_match_engine`

---

### 6. `plasticos_offer/models/offer_price_bridge.py`
**Action:** Create new file
```
cp offer_price_bridge.py plasticos_offer/models/offer_price_bridge.py
```
**Wires into:**
- `plasticos_offer/models/__init__.py` via `from . import offer_price_bridge`
- Extends `plasticos.offer.create()` — no existing method modified
- Reads `plasticos.intake.match` to pull `typical_price` when offer price is 0

Requires: `-u plasticos_offer`

---

### 7. `plasticos_offer/models/__init__.py`
**Action:** Replace with `__init___patched.py`
```
cp plasticos_offer/models/__init___patched.py plasticos_offer/models/__init__.py
```

---

## Execution Flow After Wiring

```
action_match_to_buyers()
  └─ BuyerMatcher.find_matches_for_supplier()
       └─ returns list[dict] with typical_price from Cypher (or 0.0 fallback)
  └─ create plasticos.intake.match lines  ← typical_price NOW populated
  └─ MatchResultWriter.persist_match_lines()
       └─ purge stale pending match.results for this intake
       └─ create plasticos.match.result records with run_id, score, breakdown
  └─ status = "matched"

action_send_offers()
  └─ for each selected match line:
       └─ Offer.create({ price_per_lb: match.typical_price, ... })
            └─ offer_price_bridge.create() auto-fills if price_per_lb == 0
```

---

## Docker Commands

```bash
# Apply all changes
docker compose run --rm odoo -u plasticos_buyer_match_engine
docker compose run --rm odoo -u plasticos_offer

# Run standalone tests (no Odoo)
pytest tests/test_wiring_gap2.py -v
```

---

## Residual Blockers (Not In This Pack)

| Item | Status |
|------|--------|
| Neo4j `avg_price_per_lb` Cypher query not implemented | `typical_price` will be 0.0 until `graph_service.match_buyers` returns price data from `SOLD_TO` edge |
| `__manifest__.py` version bump required | Must manually bump `19.0.2.0.0` → `19.0.2.1.0` to trigger migration |
| `pipeline_v2.py` | Still deferred — do not touch |
