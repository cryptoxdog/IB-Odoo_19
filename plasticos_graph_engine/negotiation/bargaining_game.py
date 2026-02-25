class BargainingGame:
    @staticmethod
    def weighted_nash(supplier_offer, facility_offer, structural_score):
        weight = 0.5 + (structural_score - 0.5)
        return supplier_offer * weight + facility_offer * (1 - weight)

    @staticmethod
    def acceptance_probability(price, band, belief):
        if price < band[0] or price > band[1]:
            return 0.0
        center = (band[0] + band[1]) / 2
        alignment = 1 - abs(price - center) / center
        return max(0.0, min(1.0, alignment * belief))
