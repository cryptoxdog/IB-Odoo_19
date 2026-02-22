schema_version: "kb_schema.v7.0r"
file_name: "kb_<polymer>_<topic>_<year>.yaml"

- id: <ATOM_ID>
 s meta:
    domain: "<domain>"
    evidence: "<citation>"
    embedding_key: "<semantic_id>"
    keywords: ["<keyword1>", "<keyword2>", ...]      # type: list[str]
    source_url: "<optional DOI or web link>"
    peer_reviewed: true
  when:
    - <parameter>_eq: <value>
    - <parameter>_ge: <value>
    - <parameter>_le: <value>
  infer:
    <property>: {delta: <value>}
    process_fit: ["<process1>", "<process2>"]        # type: list[str]
    buyer_target: ["<buyer1>", "<buyer2>"]           # type: list[str]
    reasoning: "<concise, quantitative engineering logic>"
  confidence: <0-1 float>
  performance:
    auto_update: true
    use_count: 0
    success_rate: 0.0
    last_updated: "<YYYY-MM-DD>"
  related_atoms: ["<id1>", "<id2>"]                  # type: list[str]
