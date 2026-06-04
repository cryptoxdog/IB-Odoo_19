# Roadmap tooling

PlasticOS roadmaps follow a **registry → sync → check** pattern (same idea as manifest wiring for modules).

## Canonical files

| Role | Path |
|------|------|
| **Registry (edit items here via CLI)** | `docs/roadmap/registry.yaml` |
| **Domain roadmap (sync-managed sections)** | e.g. `docs/GATE_AUTONOMY_ROADMAP.md` |
| **ADR (binding decision)** | e.g. `docs/adr/ADR-002-gate-hub-phased-autonomy.md` |
| **Index** | `ROADMAP.md`, `docs/README_INDEX.md` |
| **Structure** | `ARCHITECTURE.md` |

## Commands

```bash
make roadmap              # validate registry + synced docs (default)
make roadmap-sync         # regenerate sync blocks from registry.yaml
make roadmap-list         # print all registry items

# Add one item, then sync:
make roadmap-add domain=gate-autonomy phase=1 kind=backlog title="Your item text"
make roadmap-sync
```

### Item kinds

| Kind | Written to |
|------|------------|
| `backlog` | Phase N product backlog checkboxes |
| `scope_in` | Phase 1 “In scope” column |
| `scope_out` | Phase 1 “Out of scope (defer)” column |
| `observability` | Phase 1 observability bullets |
| `capability` | Phase 2/3 capability tables (`notes` → second column) |

### Adding a new roadmap domain

1. Add ADR under `docs/adr/ADR-NNN-….md` (decision).
2. Add domain block to `registry.yaml` (`domains:`).
3. Create `docs/YOUR_ROADMAP.md` with sync markers (copy from `GATE_AUTONOMY_ROADMAP.md`).
4. Run `make roadmap-sync` and `make roadmap`.

Sync markers look like:

```markdown
<!-- roadmap:gate-autonomy:phase1-backlog:start -->
…generated…
<!-- roadmap:gate-autonomy:phase1-backlog:end -->
```

**Do not** edit text between markers by hand — change `registry.yaml` and run `make roadmap-sync`.
