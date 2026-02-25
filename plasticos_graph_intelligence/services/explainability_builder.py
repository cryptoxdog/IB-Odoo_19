def build_explanation(record):
    return {
        "intake": record["intake"],
        "facility": record["facility"],
        "score": record["S_total"],
        "components": {
            "structural": 1.0,
            "quality": record.get("S_contam"),
            "geo": record.get("S_geo"),
            "reinforcement": record.get("S_reinf"),
        },
    }
