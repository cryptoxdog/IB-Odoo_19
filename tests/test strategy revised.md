create a consolidated test_module_contracts_MODULE NAME.py for each module
follow this structure 
Minimal High-Value Test Set
Master registry invariant (you already have)
All master models reject duplicate code.
Required fields invariant (single loop test)
For same 8 master models: missing name fails, missing code fails.
Material profile unique business key
One partner + polymer + form can only have one profile.
Range validation logic
density_min <= density_max and mfi_min <= mfi_max (valid passes, invalid fails).
Partner-level domain rule
Material profiles only attach to facility-level partners; parent-level partner assignment fails.
Core onchange/compute smoke test
Create a profile, trigger onchange/compute paths, assert derived fields update (at least one representative check for display/summary field behavior).
Module wiring smoke test
Registry/models load, key security/access entries exist, and basic create/search on core models does not crash.


implement module-wide contract checks,
match the tests to real field/constraint behavior
