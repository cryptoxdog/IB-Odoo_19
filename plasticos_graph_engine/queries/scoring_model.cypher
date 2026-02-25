// ============================================================
// MATCH SCORING MODEL (DETERMINISTIC)
// ============================================================

WITH $weights AS w, $intake_id AS intake_id

MATCH (i:Intake {intake_id:intake_id})-[:HAS_PROFILE]->(mp)
MATCH (f:Facility)
WHERE f.status = 'active'

// Structural Gate
MATCH (mp)-[:HAS_POLYMER]->(p)
MATCH (f)-[:ACCEPTS_POLYMER]->(p)

// MFI Gate
WHERE mp.mfi >= f.min_mfi AND mp.mfi <= f.max_mfi

// Contamination Score
WITH i, mp, f, w,
CASE
  WHEN mp.contamination_pct <= f.max_contamination_pct
  THEN 1 - (mp.contamination_pct / f.max_contamination_pct)
  ELSE -1
END AS S_contam

WHERE S_contam >= 0

// Geo Score
WITH i, mp, f, w, S_contam,
distance(point(i.geo_point), point(f.geo_point)) AS d_km

WITH i, mp, f, w, S_contam,
exp(-d_km / 500.0) AS S_geo

// Reinforcement
OPTIONAL MATCH (f)-[r:SUCCESS_WITH]->(g:Grade)
WITH i, mp, f, w, S_contam, S_geo,
coalesce(log(1 + r.score) * r.recency_weight, 0) AS S_reinf

WITH i, f,
(w.W_structural * 1.0 +
 w.W_quality    * S_contam +
 w.W_geo        * S_geo +
 w.W_reinf      * S_reinf) AS S_total

RETURN i.intake_id AS intake,
       f.facility_id AS facility,
       S_total
ORDER BY S_total DESC
LIMIT 50;
