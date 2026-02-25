class IdempotencyRegistry:
    def __init__(self):
        self._seen = set()

    def seen(self, event_id):
        return event_id in self._seen

    def mark(self, event_id):
        self._seen.add(event_id)
