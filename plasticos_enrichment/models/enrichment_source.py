from odoo import fields, models


class EnrichmentSource(models.Model):
    _name = "plasticos.enrichment.source"
    _description = "Enrichment Crawl Source"
    _order = "last_crawled_at desc"

    partner_id = fields.Many2one(
        "res.partner",
        required=True,
        index=True,
        ondelete="cascade",
    )
    source_type = fields.Selection(
        [
            ("website", "Company Website"),
            ("article", "Industry Article"),
            ("pdf", "PDF Document"),
        ],
        required=True,
        default="website",
    )
    url = fields.Char(required=True)
    last_crawled_at = fields.Datetime(readonly=True)
    last_hash = fields.Char(
        readonly=True,
        help="SHA-256 of last crawled content for change detection",
    )
    active = fields.Boolean(default=True)
    crawl_status = fields.Selection(
        [
            ("pending", "Pending"),
            ("success", "Success"),
            ("failed", "Failed"),
            ("blocked", "Blocked"),
        ],
        default="pending",
        readonly=True,
    )
    raw_content = fields.Text(
        readonly=True,
        help="Cached page text — purged after extraction",
    )
    error_message = fields.Text(readonly=True)
