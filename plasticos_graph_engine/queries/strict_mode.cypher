MATCH (i:Intake {intake_id:$id})-[:HAS_PROFILE]->(mp)
MATCH (mp)-[:QUALIFIES_FOR]->(g)
MATCH (g)<-[:CAN_RUN]-(cp)<-[:HAS_CAPABILITY]-(f)

WHERE
  mp.measured_mfi >= cp.min_mfi AND
  mp.measured_mfi <= cp.max_mfi AND
  mp.measured_filler_pct <= cp.max_filler_pct AND
  mp.measured_contamination_pct <= cp.max_contamination_pct

RETURN f, g;
