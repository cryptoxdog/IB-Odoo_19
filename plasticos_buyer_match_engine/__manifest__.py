{
    "name": "PlasticOS Buyer Match Engine",
    "version": "19.0.2.0.0",
    "category": "Plasticos/Matching",
    "summary": "Buyer matching v2.0: facility.profile-based, 10-gate filtering, Neo4j graph scoring with gate_mode.",
    "description": """
        Buyer Matching Engine v2.0

        Matches suppliers to buyers based on:
        - Material specifications (10-gate filtering)
        - Geographic proximity (Neo4j scoring)
        - Historical relationship data

        Features:
        - facility.profile-based matching (direct queries)
        - Neo4j graph integration for scoring
        - Null-safe 10-gate checks
        - Company-type aware scoring (strict/flexible/optimistic)
    """,
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
        "views/intake_button_views.xml",
        "views/match_exclusion_views.xml",
    ],
    "external_dependencies": {
        "python": ["neo4j"],
    },
    "installable": True,
    "application": False,
    "license": "LGPL-3",
}
