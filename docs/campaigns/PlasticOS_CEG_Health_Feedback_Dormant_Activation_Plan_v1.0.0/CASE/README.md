# Supplied kernel case schema specialization

`case.json` uses the **same JSON schema** from the preserved PlasticOS Addon Strategic Development Kernel v0.2.0 as an evidence/planning shape. Its `target.repository` is CEG, while the original kernel's `validate_case.py` hardcodes the Odoo constitutional manifest and 30-addon DAG. Therefore that exact original plan gate is **not a valid cross-repository authority checker** for CEG; do not force it to PASS with a fake Odoo repository or blob.

- JSON Schema validation using the supplied unmodified `schema_errors` is valid and is executed in `ASSURANCE/`.
- Cross-repository effect, proof, dependency and activation assertions are executed by the package-only validator.
- The original kernel files and source lock remain preserved byte-identical in `PLANNING_KERNEL/`.
- The CEG constitution field is intentionally `UNKNOWN`: `docs/FEATURE_GATES.md` is a documented feature-policy owner, not claimed as a sovereign constitution.
- All Odoo-specific active rules are marked not applicable with evidence. The operator's POS-INV-26 blast-radius methodology is applied but does not claim that Odoo constitutional rules govern CEG/Gate/EIE.

All product tests, independent source-owner acceptance, live Gate integration and operator activation remain NOT_RUN/NOT_GRANTED.
