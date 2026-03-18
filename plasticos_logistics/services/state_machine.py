import uuid


def new_correlation_id():
    """Generate correlation ID for tracing state transitions."""
    return str(uuid.uuid4())


VALID_TRANSITIONS = {
    "draft": ["awaiting_ready"],
    "awaiting_ready": ["ready_confirmed", "exception"],
    "ready_confirmed": ["rate_confirmed", "exception"],
    "rate_confirmed": ["scheduled", "exception"],
    "scheduled": ["dispatched", "exception"],
    "dispatched": ["picked_up", "exception"],
    "picked_up": ["delivered", "exception"],
    "delivered": ["closed", "exception"],
    "closed": [],
    "exception": ["draft"],
}


ALLOWED_TRANSITIONS = {
    "quoted": ["dispatched"],
    "dispatched": ["picked_up"],
    "picked_up": ["delivered"],
    "delivered": ["closed"],
    "closed": [],
}
