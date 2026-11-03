# PlasticOS complete configured material mapping

Source: `https://github.com/cryptoxdog/IB-Odoo_19/blob/fba54b28168d870e9b0f67a196e10e7f7a36ac08/plasticos_material_profile/models/material_normalizer.py` at commit `fba54b28168d870e9b0f67a196e10e7f7a36ac08` (Staging observed October 30, 2026).

- 159 configured rules: 23 `_SPECS` shared ERP/CRM, 23 `_CRM_EXACT`, 113 approved `_CRM_ALIASES`.
- 157 distinct effective phrases: two CRM aliases (ldpe film, pp supersacs) are superseded by `_SPECS`.
- The Excel file includes source phrases, computed Odoo profile display names, polymer/form/source master names, attribute codes/names, grade, scope, mapping tier, source link and review flags.
- The CSV files contain all 159 configured rows and only the 157 effective entries, respectively.

## Meaning and limits

Mappings are exact-match source text rules after whitespace normalization and case-folding. The normalizer does not create an Odoo material profile. The profile display name shown is the Odoo computed polymer name plus optional form name; runtime linkage is not demonstrated by this workbook. Blank source types and attributes mean unspecified, not absent in reality.

The 2026-10-30 approval claim on the CRM aliases is a comment in the committed source; the operator workbook was not independently reconciled here.

This is not a live Odoo database reconciliation or proof that every historical CRM material value has a mapping. Unknown or conflicted values remain unresolved.
