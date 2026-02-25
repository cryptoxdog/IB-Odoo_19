{
    "name": "PlasticOS Graph Engine",
    "version": "19.0.1.0.0",
    "summary": "Neo4j Enterprise Industrial Intelligence Engine",
    "author": "PlasticOS",
    "depends": [
        "base",
        "plasticos_graph_integration",
    ],
    "external_dependencies": {
        "python": ["neo4j"],
    },
    "data": [
        "security/ir.model.access.csv",
        "data/ir_cron_graph_engine.xml",
        "data/ir_cron_autonomous_discovery.xml",
        "data/ir_cron_stream_consumer.xml",
        "adaptive_tier/adaptive_tier_cron.xml",
        "anomaly/anomaly_cron.xml",
        "shard_rebalancing/shard_rebalance_cron.xml",
    ],
    "installable": True,
    "application": False,
}
