from odoo import api, models

# Mapping from raw VanillaSoft values to canonical UTM source names.
# Used by partner import wizard to normalize lead sources.
# Keys = raw VanillaSoft strings, Values = utm.source name to search by.


WEB_RESEARCH = "Web Research"
INDUSTRY_ASSOCIATION = "Industry Association"
STATE_FACILITY_LIST = "State Facility List"
TRADE_SHOW = "Trade Show"
RECYCLE_NET = "Recycle.net"
DATA_PROVIDER = "Data Provider"
PLASTICS_NEWS = "Plastics News"
INTERNAL_RESEARCH = "Internal Research"
LEAD_SOURCE_MAPPING = {
    # Internal team research
    "Igor/Fiver": INTERNAL_RESEARCH,
    "Igor": INTERNAL_RESEARCH,
    "Igor Beylin": INTERNAL_RESEARCH,
    "Igor HOT": INTERNAL_RESEARCH,
    "Igor Outook": INTERNAL_RESEARCH,
    "FIVERR/Google": INTERNAL_RESEARCH,
    "Fiverr": INTERNAL_RESEARCH,
    "Fivver": INTERNAL_RESEARCH,
    "Arthur": INTERNAL_RESEARCH,
    "Adam GM": INTERNAL_RESEARCH,
    "Manuela": INTERNAL_RESEARCH,
    "NC Assistant": INTERNAL_RESEARCH,
    "NC (MK)": INTERNAL_RESEARCH,
    "Outlook": INTERNAL_RESEARCH,
    "AB iCloud": INTERNAL_RESEARCH,
    # SICCODE
    "SICCODE.com": "SICCODE",
    "SICCODE": "SICCODE",
    "SICCODE.COM": "SICCODE",
    "SIC": "SICCODE",
    "TOP 100 Growers (SICCODE)": "SICCODE",
    # Plastics News
    "PNEWS Rankings": PLASTICS_NEWS,
    "PNEWS Recycler": PLASTICS_NEWS,
    "PNEWS Compounders": PLASTICS_NEWS,
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
    "DataAxle": DATA_PROVIDER,
    "Data Axle": DATA_PROVIDER,
    "List Giant": DATA_PROVIDER,
    # Recycle.net
    "recycle.net": RECYCLE_NET,
    "plasticfilmrecycling.org": RECYCLE_NET,
    "www.recyclingcenters.org": RECYCLE_NET,
    "www.recyclingplasticwaste.com": RECYCLE_NET,
    # Trade shows
    "SERC 2019": TRADE_SHOW,
    "Attendee List - OH 2022": TRADE_SHOW,
    "Attendee List": TRADE_SHOW,
    # State facility lists
    "GA Licensed SW Facilities list": STATE_FACILITY_LIST,
    "OH Licensed SW Facilities List": STATE_FACILITY_LIST,
    "WI Licensed SW Facilities List": STATE_FACILITY_LIST,
    "SW Facility List": STATE_FACILITY_LIST,
    "Solid Waste Facility List": STATE_FACILITY_LIST,
    "DEP/DEQ": STATE_FACILITY_LIST,
    # Associations
    "R2": INDUSTRY_ASSOCIATION,
    "RIPA Association": INDUSTRY_ASSOCIATION,
    "Vinyl Institute": INDUSTRY_ASSOCIATION,
    # Web research
    "Web Database": WEB_RESEARCH,
    WEB_RESEARCH: WEB_RESEARCH,
    "www.dexknows.com": WEB_RESEARCH,
    "www.geosource.com": WEB_RESEARCH,
    "www.iqsdirectory.com": WEB_RESEARCH,
    "www.plasticwaste.com": WEB_RESEARCH,
    "www.in.gov": WEB_RESEARCH,
    "www.butlercountyrecycles.org": WEB_RESEARCH,
    "www.ncsod.org/directories/growers": WEB_RESEARCH,
    "epa.ohio.gov": WEB_RESEARCH,
    "Internet": WEB_RESEARCH,
    "Directory": WEB_RESEARCH,
    "MFG Directory": WEB_RESEARCH,
    "CieTrade": WEB_RESEARCH,
    "Stericycle.com": WEB_RESEARCH,
    "YP": WEB_RESEARCH,
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
