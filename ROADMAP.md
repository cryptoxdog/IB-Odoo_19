# Roadmap Index

PlasticOS planning docs are split by concern (industry norm: **ADRs** for decisions, **roadmaps** for phased delivery, **ARCHITECTURE.md** for structure).

| Document | Use when |
|----------|----------|
<!-- roadmap:index:domains:start -->
| [docs/GATE_AUTONOMY_ROADMAP.md](docs/GATE_AUTONOMY_ROADMAP.md) | Gate → CEG matching, human-in-loop phases, autonomy graduation, implementation scope |
| [docs/adr/ADR-002-gate-hub-phased-autonomy.md](docs/adr/ADR-002-gate-hub-phased-autonomy.md) | Why Gate is the hub, why Odoo local is fallback, what agents must not ship in Phase 1 |
<!-- roadmap:index:domains:end -->
| [ARCHITECTURE.md](ARCHITECTURE.md) | Layer map, module index, Gate boundary summary |
| [docs/README_INDEX.md](docs/README_INDEX.md) | Module README bundle, go-live gates, config params |
| [docs/roadmap/README.md](docs/roadmap/README.md) | How to add roadmap items (`make roadmap-add`, `make roadmap-sync`) |

**Do not** duplicate phase tables in domain roadmaps — edit `docs/roadmap/registry.yaml` and run `make roadmap-sync`.
