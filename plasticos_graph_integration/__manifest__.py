{
    "name": "PlasticOS Graph Integration",
    "version": "1.0.0",
    "summary": "Industrial Intelligence Graph Sync (Neo4j Enterprise + GDS)",
    "author": "PlasticOS",
    "depends": [
        "base",
        "mail",
        "plasticos_intake",
        "plasticos_material_profile",
        "plasticos_order_lines",
        "plasticos_transaction",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/ir_cron_graph_sync.xml",
        "data/scoring_weights.xml",
    ],
    "installable": True,
    "application": False,
}
