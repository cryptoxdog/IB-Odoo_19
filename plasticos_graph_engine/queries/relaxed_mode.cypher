MATCH (i:Intake {intake_id:$id})-[:HAS_PROFILE]->(mp)
MATCH (mp)-[:QUALIFIES_FOR]->(g)

OPTIONAL MATCH (g)-[s:SIMILAR_TO]->(g2)
WHERE s.score_structural > 0.75

WITH mp, g, g2
MATCH (candidate:Grade)
WHERE candidate IN [g, g2]

MATCH (candidate)<-[:CAN_RUN]-(cp)<-[:HAS_CAPABILITY]-(f)

WHERE
  mp.measured_contamination_pct <= cp.max_contamination_pct * 1.15
  AND mp.measured_filler_pct <= cp.max_filler_pct * 1.10

RETURN DISTINCT f, candidate
LIMIT 50;
