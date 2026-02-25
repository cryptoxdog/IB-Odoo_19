// Deterministic structural scoring
MATCH (i:Intake {intake_id:$intake_id})-[:HAS_PROFILE]->(mp)
MATCH (mp)-[:QUALIFIES_FOR]->(g:Grade)

MATCH (g)<-[:CAN_RUN]-(cp:CapabilityProfile)<-[:HAS_CAPABILITY]-(f:Facility)

// Structural dimensions
WITH i, mp, g, cp, f,

// Polymer match (binary)
CASE WHEN (mp)-[:HAS_POLYMER]->()<-[:USES_POLYMER]-(g) THEN 1 ELSE 0 END AS polymer_score,

// Tier proximity
abs(g.tier_level - cp.max_tier_level) AS tier_distance,

// MFI distance normalized
CASE
  WHEN mp.measured_mfi IS NULL THEN 0
  WHEN mp.measured_mfi >= g.mfi_min AND mp.measured_mfi <= g.mfi_max THEN 1
  ELSE 1 - abs(mp.measured_mfi - ((g.mfi_min + g.mfi_max)/2)) / ((g.mfi_max - g.mfi_min)/2)
END AS mfi_score,

// Filler tolerance
CASE
  WHEN mp.measured_filler_pct <= g.max_filler_pct THEN 1
  ELSE 0
END AS filler_score,

// Contamination tolerance
CASE
  WHEN mp.measured_contamination_pct <= g.max_contamination_pct THEN 1
  ELSE 0
END AS contamination_score

WITH f,g,
     polymer_score,
     (1.0/(1+tier_distance)) AS tier_score,
     mfi_score,
     filler_score,
     contamination_score

WITH f,g,
     (0.30*polymer_score +
      0.20*tier_score +
      0.20*mfi_score +
      0.15*filler_score +
      0.15*contamination_score) AS structural_score

RETURN f.facility_id AS facility,
       g.grade_id AS grade,
       structural_score
ORDER BY structural_score DESC
LIMIT 50;
