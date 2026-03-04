# PlasticOS TODO

## Pending Integration

### Intake → Buyer Matching → Offers Pipeline

**Status:** Intake UI complete, matching engine stub in place

**When buyer matching engine is integrated:**

1. **Wire `action_match_to_buyers()` to matching engine**
   - File: `plasticos_intake/models/intake.py`
   - Currently returns empty `matches = []`
   - Engine should return: `[{"buyer_id": int, "match_score": float, "match_reason": str, "typical_price": float}]`

2. **Populate `typical_price` from buyer data**
   - File: `plasticos_intake/models/intake_match.py`
   - Options:
     - Pull from buyer's historical purchases for similar materials
     - Pull from buyer profile preferences
     - Compute from market data
   - Consider making it a computed field vs engine-populated

3. **Wire `action_send_offers()` to offer module**
   - File: `plasticos_intake/models/intake.py`
   - Currently raises placeholder error
   - Should create `plasticos.offer` records for each selected buyer
   - Pre-fill offer with intake material details

4. **Add "View Offers" button after offers sent**
   - Show link to created offers from intake form
   - Track offer status back on intake (pending/accepted/rejected)

---

## Future Enhancements

- [ ] Buyer profile module with material preferences and typical prices
- [ ] Market price data integration
- [ ] Offer acceptance workflow
- [ ] Automated follow-up reminders
- [ ] **Link product.template to material_profile** (patch 011)
  - Add `material_profile_id` M2O field to `product.template`
  - Add related fields: `material_polymer`, `material_form`, `material_resin_grade`
  - Enables filtering products by material type in sales workflows
  - Requires adding `product` to `plasticos_material_profile` depends
  - Patch file: `docs/03-01-2026/011-link-product-to-material-profile.patch`
