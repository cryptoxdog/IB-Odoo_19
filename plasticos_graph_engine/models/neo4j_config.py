from odoo import fields, models


class Neo4jConfig(models.Model):
    _name = "plasticos.neo4j.config"
    _description = "Neo4j Enterprise Connection"

    uri = fields.Char(required=True)
    username = fields.Char(required=True)
    password = fields.Char(required=True)
    encrypted = fields.Boolean(default=True)
