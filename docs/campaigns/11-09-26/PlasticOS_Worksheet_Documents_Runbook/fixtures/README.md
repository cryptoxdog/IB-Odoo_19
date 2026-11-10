# Fixtures

The read-only reconciler's `tools/test_reconcile_cohort.py` generates **synthetic** images, CSV files and SHA-256 values in disposable temporary folders for each test. It deliberately creates no customer documents or static copies of private source extracts. Run from the pack root:

```sh
python3 -m unittest discover -s tools -p 'test_*.py' -v
```

Do not use generated test samples as live hosted Enterprise/Odoo.sh proof.
