# Roadmap tooling

PlasticOS roadmaps follow a **registry → sync → check** pattern (same idea as manifest wiring for modules).

## Canonical files

| Role | Path |
|------|------|
| **Registry (source of truth)** | `docs/roadmap/registry.yaml` |
| **Domain roadmap (sync-managed sections)** | e.g. `docs/GATE_AUTONOMY_ROADMAP.md` |
| **ADR (binding decision)** | `docs/adr/` — index at [docs/adr/README.md](../adr/README.md) (not `reports/adr/`) |
| **Index** | `ROADMAP.md`, `docs/README_INDEX.md` |
| **Structure** | `ARCHITECTURE.md` |

## Commands

```bash
# Sync all roadmap docs + validate IDs (no item added)
make roadmap

# Add item → auto ID (ROAD-GATE-NNN) → sync → validate — one command
make roadmap domain=gate-autonomy phase=1 kind=backlog title="Your item text"

make roadmap-list         # print all registry items
make roadmap-sync         # sync only (prefer make roadmap)
```

### Item kinds

| Kind | Written to |
|------|------------|
| `backlog` | Phase N product backlog checkboxes |
| `scope_in` | Phase 1 “In scope” column |
| `scope_out` | Phase 1 “Out of scope (defer)” column |
| `observability` | Phase 1 observability bullets |
| `capability` | Phase 2/3 capability tables (`notes` → second column) |

Optional: `notes="..."`, `status=done|deferred|in_progress`

### Adding a new roadmap domain

1. Add ADR under `docs/adr/ADR-NNN-….md` (decision).
2. Add domain block to `registry.yaml` (`domains:`).
3. Create `docs/YOUR_ROADMAP.md` with sync markers (copy from `GATE_AUTONOMY_ROADMAP.md`).
4. Run `make roadmap`.

Sync markers look like:

```markdown
<!-- roadmap:gate-autonomy:phase1-backlog:start -->
…generated…
<!-- roadmap:gate-autonomy:phase1-backlog:end -->
```

**Do not** edit text between markers by hand — change `registry.yaml` and run `make roadmap`.
