"""Lead Source enum for tracking how partners/intakes were acquired.

This module provides a Selection field definition (not a database model)
for lead sources. Values are derived from VanillaSoft import data.
"""

LEAD_SOURCE_SELECTION = [
    ("internal", "Internal Research (Igor/Team)"),
    ("siccode", "SICCODE.com Database"),
    ("pnews", "Plastics News"),
    ("referral", "Referral"),
    ("google", "Google Search"),
    ("linkedin", "LinkedIn"),
    ("manta", "Manta Directory"),
    ("thomasnet", "ThomasNet"),
    ("enf", "ENF/Industry Database"),
    ("recycle_net", "Recycle.net"),
    ("trade_show", "Trade Show/Conference"),
    ("state_list", "State Licensed Facility List"),
    ("web_research", "Web Research"),
    ("data_provider", "Data Provider (List Giant, DataAxle)"),
    ("association", "Industry Association (R2, RIPA, Vinyl Institute)"),
    ("web_lead", "Web Lead Form"),
    ("other", "Other"),
]

# Mapping from raw VanillaSoft values to canonical enum codes
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
    # ThomasNet and web directories
    "www.thomasnet.com": "thomasnet",
    # ENF and databases
    "ENF Database": "enf",
    "IndustrySelect Database": "enf",
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


def normalize_lead_source(raw_value: str) -> str:
    """Convert a raw lead source string to canonical enum code.

    Args:
        raw_value: Raw lead source from import (e.g., "Igor/Fiver")

    Returns:
        Canonical enum code (e.g., "internal"), or "other" if not mapped
    """
    if not raw_value:
        return ""
    return LEAD_SOURCE_MAPPING.get(raw_value.strip(), "other")
