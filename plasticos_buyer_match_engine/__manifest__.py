{
    "name": "PlasticOS Buyer Match Engine",
    "version": "19.0.1.0.0",
    "category": "Plasticos/Matching",
    "summary": "Deterministic buyer matching: capability lanes, quality/volume/geo gates, intake-driven; Neo4j graph traversal.",
    "author": "Plasticos Dev",
    "depends": [
        "plasticos_intake",
        "plasticos_material_profile",
        "plasticos_matching",
        "plasticos_facility_profile",
        "plasticos_transaction",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/buyer_capability_views.xml",
        "views/intake_button_views.xml",
    ],
    "external_dependencies": {
        "python": ["neo4j"],
    },
    "installable": True,
    "application": False,
    "license": "LGPL-3",
}
