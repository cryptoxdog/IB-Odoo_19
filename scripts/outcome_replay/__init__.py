"""Odoo outcome-replay input producer (TASK-057). Offline / no Gate mutation."""

from .schema import SCHEMA_ID, SCHEMA_VERSION, build_replay_document, content_hash

__all__ = [
    "SCHEMA_ID",
    "SCHEMA_VERSION",
    "build_replay_document",
    "content_hash",
]
