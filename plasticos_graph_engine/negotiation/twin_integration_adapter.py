class TwinIntegrationAdapter:
    @staticmethod
    def load_modifier(facility_load):
        if facility_load > 0.9:
            return 0.85
        if facility_load < 0.5:
            return 1.15
        return 1.0
