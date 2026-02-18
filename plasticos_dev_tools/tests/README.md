# Test Scripts

These test scripts were extracted from the original `scripts.zip` pack. They are designed to run in an Odoo shell context and validate integration with models that may not yet exist in the current repo (`plastic_ai.kb_config`, `mack.buyer.card`).

## Status

These tests reference models from the legacy `mack.*` namespace that have not been migrated to the `plasticos.*` namespace. They are preserved here for reference and will need to be updated when the corresponding models are implemented.

## Usage

```bash
odoo shell -d <database> --addons-path=<path>
>>> exec(open('plasticos_dev_tools/tests/test_kb_integration.py').read())
>>> run_kb_integration_tests(env)
```
