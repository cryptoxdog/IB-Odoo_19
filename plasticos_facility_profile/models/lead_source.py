from odoo import api, models

# Mapping from raw VanillaSoft values to canonical UTM source names.
# Used by partner import wizard to normalize lead sources.
# Keys = raw VanillaSoft strings, Values = utm.source name to search by.
LEAD_SOURCE_MAPPING = {
    # Internal team research
    "Igor/Fiver": "Internal Research",
    "Igor": "Internal Research",
    "Igor Beylin": "Internal Research",
    "Igor HOT": "Internal Research",
    "Igor Outook": "Internal Research",
    "FIVERR/Google": "Internal Research",
    "Fiverr": "Internal Research",
    "Fivver": "Internal Research",
    "Arthur": "Internal Research",
    "Adam GM": "Internal Research",
    "Manuela": "Internal Research",
    "NC Assistant": "Internal Research",
    "NC (MK)": "Internal Research",
    "Outlook": "Internal Research",
    "AB iCloud": "Internal Research",
    # SICCODE
    "SICCODE.com": "SICCODE",
    "SICCODE": "SICCODE",
    "SICCODE.COM": "SICCODE",
    "SIC": "SICCODE",
    "TOP 100 Growers (SICCODE)": "SICCODE",
    # Plastics News
    "PNEWS Rankings": "Plastics News",
    "PNEWS Recycler": "Plastics News",
    "PNEWS Compounders": "Plastics News",
    # Referral
    "Referral": "Referral",
    # Google
    "Google": "Google Search",
    "Google - Jaime": "Google Search",
    # LinkedIn
    "LinkedIn": "LinkedIn",
    "AI-Seamless/Linked In": "LinkedIn",
    "Seamless": "LinkedIn",
    # Manta
    "Manta": "Manta Directory",
    "Manta (Surplus)": "Manta Directory",
    # ThomasNet
    "www.thomasnet.com": "ThomasNet",
    # ENF and databases
    "ENF Database": "ENF / Industry Database",
    "IndustrySelect Database": "ENF / Industry Database",
    # Data providers
    "DataAxle": "Data Provider",
    "Data Axle": "Data Provider",
    "List Giant": "Data Provider",
    # Recycle.net
    "recycle.net": "Recycle.net",
    "plasticfilmrecycling.org": "Recycle.net",
    "www.recyclingcenters.org": "Recycle.net",
    "www.recyclingplasticwaste.com": "Recycle.net",
    # Trade shows
    "SERC 2019": "Trade Show",
    "Attendee List - OH 2022": "Trade Show",
    "Attendee List": "Trade Show",
    # State facility lists
    "GA Licensed SW Facilities list": "State Facility List",
    "OH Licensed SW Facilities List": "State Facility List",
    "WI Licensed SW Facilities List": "State Facility List",
    "SW Facility List": "State Facility List",
    "Solid Waste Facility List": "State Facility List",
    "DEP/DEQ": "State Facility List",
    # Associations
    "R2": "Industry Association",
    "RIPA Association": "Industry Association",
    "Vinyl Institute": "Industry Association",
    # Web research
    "Web Database": "Web Research",
    "Web Research": "Web Research",
    "www.dexknows.com": "Web Research",
    "www.geosource.com": "Web Research",
    "www.iqsdirectory.com": "Web Research",
    "www.plasticwaste.com": "Web Research",
    "www.in.gov": "Web Research",
    "www.butlercountyrecycles.org": "Web Research",
    "www.ncsod.org/directories/growers": "Web Research",
    "epa.ohio.gov": "Web Research",
    "Internet": "Web Research",
    "Directory": "Web Research",
    "MFG Directory": "Web Research",
    "CieTrade": "Web Research",
    "Stericycle.com": "Web Research",
    "YP": "Web Research",
    # Other/misc
    "Ricardo Research": "Other",
    "Ricardo": "Other",
    "Ricardo Pereira": "Other",
    "Public Records": "Other",
    "Green Resource Index": "Other",
    "Source SC": "Other",
    "NY Master List": "Other",
    "MA Master List": "Other",
    "AA NY List": "Other",
    "Old List": "Other",
    "WC Old Leads": "Other",
    "IN (WC)": "Other",
    "Ohio (JG)": "Other",
    "San Antonio Recyclers": "Other",
    "Pallet Central": "Other",
    "rf@scrapmanagement.com": "Other",
}


class LeadSourceUtils(models.AbstractModel):
    """Utility methods for lead source normalization.

    The original plasticos.lead.source model is DEPRECATED.
    All lead source tracking now uses utm.source (Odoo native).
    This abstract model provides the VanillaSoft mapping logic
    for use during partner/CRM import.
    """

    _name = "plasticos.lead.source.utils"
    _description = "Lead Source Normalization Utilities (UTM)"

    @api.model
    def normalize_raw_source(self, raw_value):
        """Convert raw lead source string to utm.source record.

        Args:
            raw_value: Raw lead source from VanillaSoft (e.g., "Igor/Fiver")

        Returns:
            utm.source record, or False if not mapped
        """
        if not raw_value:
            return False
        utm_name = LEAD_SOURCE_MAPPING.get(raw_value.strip(), "Other")
        return self.env["utm.source"].search([("name", "=", utm_name)], limit=1)

    @api.model
    def get_utm_source_by_name(self, name):
        """Get utm.source record by exact name match."""
        return self.env["utm.source"].search([("name", "=", name)], limit=1)
