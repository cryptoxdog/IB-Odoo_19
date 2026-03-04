from odoo import api, fields, models

# Mapping from raw VanillaSoft values to canonical codes
# Used by partner import wizard to normalize lead sources
LEAD_SOURCE_MAPPING = {
    # Internal team research
    "Igor/Fiver": "internal",
    "Igor": "internal",
    "Igor Beylin": "internal",
    "Igor HOT": "internal",
    "Igor Outook": "internal",
    "FIVERR/Google": "internal",
    "Fiverr": "internal",
    "Fivver": "internal",
    "Arthur": "internal",
    "Adam GM": "internal",
    "Manuela": "internal",
    "NC Assistant": "internal",
    "NC (MK)": "internal",
    "Outlook": "internal",
    "AB iCloud": "internal",
    # SICCODE
    "SICCODE.com": "siccode",
    "SICCODE": "siccode",
    "SICCODE.COM": "siccode",
    "SIC": "siccode",
    "TOP 100 Growers (SICCODE)": "siccode",
    # Plastics News
    "PNEWS Rankings": "pnews",
    "PNEWS Recycler": "pnews",
    "PNEWS Compounders": "pnews",
    # Referral
    "Referral": "referral",
    # Google
    "Google": "google",
    "Google - Jaime": "google",
    # LinkedIn
    "LinkedIn": "linkedin",
    "AI-Seamless/Linked In": "linkedin",
    "Seamless": "linkedin",
    # Manta
    "Manta": "manta",
    "Manta (Surplus)": "manta",
    # ThomasNet
    "www.thomasnet.com": "thomasnet",
    # ENF and databases
    "ENF Database": "enf",
    "IndustrySelect Database": "enf",
    # Data providers
    "DataAxle": "data_provider",
    "Data Axle": "data_provider",
    "List Giant": "data_provider",
    # Recycle.net
    "recycle.net": "recycle_net",
    "plasticfilmrecycling.org": "recycle_net",
    "www.recyclingcenters.org": "recycle_net",
    "www.recyclingplasticwaste.com": "recycle_net",
    # Trade shows
    "SERC 2019": "trade_show",
    "Attendee List - OH 2022": "trade_show",
    "Attendee List": "trade_show",
    # State facility lists
    "GA Licensed SW Facilities list": "state_list",
    "OH Licensed SW Facilities List": "state_list",
    "WI Licensed SW Facilities List": "state_list",
    "SW Facility List": "state_list",
    "Solid Waste Facility List": "state_list",
    "DEP/DEQ": "state_list",
    # Associations
    "R2": "association",
    "RIPA Association": "association",
    "Vinyl Institute": "association",
    # Web research
    "Web Database": "web_research",
    "Web Research": "web_research",
    "www.dexknows.com": "web_research",
    "www.geosource.com": "web_research",
    "www.iqsdirectory.com": "web_research",
    "www.plasticwaste.com": "web_research",
    "www.in.gov": "web_research",
    "www.butlercountyrecycles.org": "web_research",
    "www.ncsod.org/directories/growers": "web_research",
    "epa.ohio.gov": "web_research",
    "Internet": "web_research",
    "Directory": "web_research",
    "MFG Directory": "web_research",
    "CieTrade": "web_research",
    "Stericycle.com": "web_research",
    "YP": "web_research",
    # Other/misc
    "Ricardo Research": "other",
    "Ricardo": "other",
    "Ricardo Pereira": "other",
    "Public Records": "other",
    "Green Resource Index": "other",
    "Source SC": "other",
    "NY Master List": "other",
    "MA Master List": "other",
    "AA NY List": "other",
    "Old List": "other",
    "WC Old Leads": "other",
    "IN (WC)": "other",
    "Ohio (JG)": "other",
    "San Antonio Recyclers": "other",
    "Pallet Central": "other",
    "rf@scrapmanagement.com": "other",
}


class PlasticosLeadSource(models.Model):
    """Master registry of lead sources for tracking how partners/intakes were acquired."""

    _name = "plasticos.lead.source"
    _description = "Lead Source"
    _order = "sequence, name"

    name = fields.Char(string="Lead Source", required=True, index=True)
    code = fields.Char(
        string="Code",
        required=True,
        index=True,
        help="Internal code for programmatic reference (e.g., 'web_lead', 'internal').",
    )
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    description = fields.Text(
        string="Description",
        help="Optional description of this lead source.",
    )

    _unique_code = models.Constraint(
        "unique(code)",
        "Lead source code must be unique.",
    )

    @api.model
    def get_by_code(self, code):
        """Get lead source record by code, or None if not found."""
        return self.search([("code", "=", code)], limit=1)

    @api.model
    def normalize_raw_source(self, raw_value):
        """Convert raw lead source string to canonical code.

        Args:
            raw_value: Raw lead source from import (e.g., "Igor/Fiver")

        Returns:
            Lead source record, or False if not mapped
        """
        if not raw_value:
            return False
        code = LEAD_SOURCE_MAPPING.get(raw_value.strip(), "other")
        return self.get_by_code(code)
