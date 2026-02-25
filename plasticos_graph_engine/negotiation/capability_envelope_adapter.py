class CapabilityEnvelopeAdapter:
    @staticmethod
    def adjust_belief(reinforcement, capability_width):
        return reinforcement * capability_width
