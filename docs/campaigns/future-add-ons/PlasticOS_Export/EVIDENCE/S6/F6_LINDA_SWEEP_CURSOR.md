# F6: Linda load-sweep cursor write cost (S4 review O4)

Measured on `odoo_test_s6f6`, a restore of the post-upgrade backup (`L-RESTORE.json`). The ACK lane holds 240 eligible loads, which is more than `LOAD_SWEEP_BATCH` (200). Each measurement script ran in `odoo shell` and rolled back.

| Measure | Result |
|---|---|
| Eligible ACK loads | 240 (batch 200) |
| Six consecutive `_load_sweep_page(ack)` runs | page 200 each; cursor 215 → 175 → 135 → 95 → 55 → 255 (wraps) |
| Time per run | 43.2 ms (cold first run), then 2.7, 2.7, 2.2, 2.2, 1.2 ms |
| Queries per run | 8, then 5, 5, 5, 5, 4 |
| Registry cache clears per run | 1 (one `set_param`) |
| Full `_run_load_obligations()` | 0.13 s, both lanes |
| What a clear does (Odoo 19 source) | `set_param` → `registry.clear_cache('stable')`; the `stable` key covers `default`, `stable` and `templates.cached_values`, and is signalled to every worker |
| Rebuilding the parameter cache after a clear | 67 parameters: 6.3 ms and 67 queries (warm: 0.2 ms, 0 queries) |
| Load views plus an 80-row list after a clear | 15.1 ms and 9 queries (warm: 5.8 ms, 1 query) |

## Verdict

No defect was proven, so nothing changed (C06-RECON F6). The Logistics code is outside S6 effects in any case.

The real cost is that each worker flushes its `default` and `stable` ormcaches once per lane every five minutes while that lane holds more than 200 eligible loads. Each flush costs milliseconds per worker in the measured paths. This is recorded for the final audit. If production shows cache churn, the owner's remedy is to move the cursor to a dedicated row or table so the write does not invalidate the registry, as S4 O4 proposed.
