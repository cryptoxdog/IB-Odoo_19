"""CRM sync orchestrator — DTO → ORM write path with watermarks and orphans."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from ..adapters.base import CanonicalCall, CanonicalLead, CrmAdapterError, CrmAdapterStubError
from ..adapters.registry import ensure_live_or_raise, get_adapter

_logger = logging.getLogger(__name__)

CRM_LEAD = "crm.lead"
CONTACT_PAGE_SIZE = 200
CALL_BATCH_SIZE = 500


def _parse_utc(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value.strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _dt_naive_utc(value: str | None) -> datetime | None:
    dt = _parse_utc(value)
    return dt.replace(tzinfo=None) if dt else None


def _iso_z(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


class SyncOrchestrator:
    def __init__(self, env):
        self.env = env

    def run_connection(self, connection) -> Any:
        connection.ensure_one()
        Run = self.env["plasticos.crm.sync.run"]
        run = Run.create(
            {
                "connection_id": connection.id,
                "status": "running",
                "started_at": datetime.now(UTC).replace(tzinfo=None),
            }
        )
        try:
            adapter = self._build_adapter(connection)
            ensure_live_or_raise(adapter)
            adapter.healthcheck()
            contacts_n = self._sync_contacts(connection, adapter, run)
            calls_n = self._sync_calls(connection, adapter, run)
            resolved = self._resolve_orphans(connection, adapter, run)
            run.write(
                {
                    "status": "success",
                    "finished_at": datetime.now(UTC).replace(tzinfo=None),
                    "contacts_upserted": contacts_n,
                    "calls_upserted": calls_n,
                    "orphans_resolved": resolved,
                }
            )
            connection.write(
                {
                    "last_error": False,
                    "last_success_at": datetime.now(UTC).replace(tzinfo=None),
                }
            )
        except (CrmAdapterStubError, CrmAdapterError, Exception) as exc:
            excerpt = str(exc)[:2000]
            _logger.exception("CRM sync failed connection=%s", connection.id)
            # Prior page loops may have cr.commit()'d watermarks; persist failure
            # outside the current request txn so UserError rollback cannot erase it.
            self._persist_sync_failure(connection, run, excerpt)
            raise
        return run

    def _persist_sync_failure(self, connection, run, excerpt: str) -> None:
        """Write failed run + last_error in a separate cursor (survives UserError)."""
        from odoo import api

        finished = datetime.now(UTC).replace(tzinfo=None)
        with self.env.registry.cursor() as cr:
            env = api.Environment(cr, self.env.uid, dict(self.env.context))
            if run:
                env["plasticos.crm.sync.run"].browse(run.ids).write(
                    {
                        "status": "failed",
                        "finished_at": finished,
                        "error_excerpt": excerpt,
                    }
                )
            env["plasticos.crm.connection"].browse(connection.ids).write({"last_error": excerpt})

    def upsert_contact_external_id(self, connection, external_id: str) -> Any:
        """Single-contact path: contact + call history + custom tables."""
        adapter = self._build_adapter(connection)
        ensure_live_or_raise(adapter)
        lead_dto = adapter.get_contact(str(external_id))
        if not lead_dto:
            raise CrmAdapterError(f"Contact {external_id} not found")
        lead = self._upsert_lead(connection, lead_dto)
        calls_n = 0
        if hasattr(adapter, "iter_calls_for_contact"):
            for batch in adapter.iter_calls_for_contact(str(external_id)):
                calls_n += self._upsert_calls(connection, batch, None)
        self._sync_tables_for_lead(connection, adapter, lead_dto.external_id, lead)
        self._resolve_orphans(connection, adapter, None)
        _logger.info(
            "Single-contact sync done external_id=%s lead_id=%s calls=%s",
            external_id,
            lead.id,
            calls_n,
        )
        return lead

    def _build_adapter(self, connection):
        icp = self.env["ir.config_parameter"].sudo()
        api_key = (icp.get_param("plasticos_crm_sync.vanillasoft_api_key") or "").strip()
        root = (
            icp.get_param("plasticos_crm_sync.vanillasoft_root_endpoint") or ""
        ).strip() or "https://vanillasoft.net"
        project = (connection.project_id or icp.get_param("plasticos_crm_sync.vanillasoft_project_id") or "").strip()
        return get_adapter(
            connection.provider,
            api_key=api_key,
            root_endpoint=root,
            project_id=int(project or 0),
        )

    def _sync_contacts(self, connection, adapter, run) -> int:
        modified_after = connection.default_contact_modified_after()
        # Clamp to 31-day API max
        floor = datetime.now(UTC) - timedelta(days=30)
        parsed = _parse_utc(modified_after)
        if parsed and parsed < floor:
            modified_after = _iso_z(floor)

        upserted = 0
        last_batch_end = None
        for leads, batch_end, _partial in adapter.iter_contacts(
            modified_after=modified_after,
            limit=CONTACT_PAGE_SIZE,
        ):
            for dto in leads:
                lead = self._upsert_lead(connection, dto)
                if not dto.deleted:
                    self._sync_tables_for_lead(connection, adapter, dto.external_id, lead)
                upserted += 1
            if batch_end:
                last_batch_end = batch_end
                connection.contact_watermark_utc = batch_end
                self.env.cr.commit()  # watermark after successful page
        if last_batch_end:
            connection.contact_watermark_utc = last_batch_end
        if run:
            run.contacts_upserted = upserted
        return upserted

    def _sync_calls(self, connection, adapter, run) -> int:
        now = datetime.now(UTC)
        end = now
        if connection.call_watermark_utc:
            start = _parse_utc(connection.call_watermark_utc) or (now - timedelta(days=7))
        elif connection.call_backfill_floor_utc:
            start = _parse_utc(connection.call_backfill_floor_utc) or (now - timedelta(days=30))
        else:
            start = now - timedelta(days=7)

        # Window size: 1 day chunks to keep batches manageable
        upserted = 0
        cursor = start
        while cursor < end:
            window_end = min(cursor + timedelta(days=1), end)
            for batch in adapter.iter_calls(
                start=_iso_z(cursor),
                end=_iso_z(window_end),
                limit=CALL_BATCH_SIZE,
            ):
                upserted += self._upsert_calls(connection, batch, run)
                self.env.cr.commit()  # batch commit
            connection.call_watermark_utc = _iso_z(window_end)
            self.env.cr.commit()  # watermark advance
            cursor = window_end
        if run:
            run.calls_upserted = upserted
        return upserted

    def _upsert_lead(self, connection, dto: CanonicalLead):
        Lead = self.env[CRM_LEAD]
        Ref = self.env["plasticos.crm.external.ref"]
        ref = Ref.search(
            [
                ("provider", "=", dto.provider),
                ("external_id", "=", dto.external_id),
                ("res_model", "=", CRM_LEAD),
            ],
            limit=1,
        )
        lead = Lead.browse(ref.res_id) if ref else Lead.browse()
        if not lead:
            lead = Lead.search([("vanillasoft_id", "=", dto.external_id)], limit=1)

        vals = self._lead_vals_from_dto(dto)
        if dto.deleted:
            vals["active"] = False

        if lead:
            lead.write(vals)
        else:
            lead = Lead.create(vals)

        if not ref:
            Ref.create(
                {
                    "provider": dto.provider,
                    "external_id": dto.external_id,
                    "res_model": CRM_LEAD,
                    "res_id": lead.id,
                    "lead_id": lead.id,
                }
            )
        elif ref.res_id != lead.id or ref.lead_id.id != lead.id:
            ref.write({"res_id": lead.id, "lead_id": lead.id})
        return lead

    def _lead_vals_from_dto(self, dto: CanonicalLead) -> dict[str, Any]:
        # Lazy import mapping SSOT from crm_bridge
        from odoo.addons.plasticos_crm_bridge.models.crm_mapping import STAGE_MAPPING
        from odoo.addons.plasticos_facility_profile.models.lead_source import LEAD_SOURCE_MAPPING

        contact_name = " ".join(filter(None, [dto.first_name, dto.last_name])).strip()
        company = (dto.company or "").strip()
        name = f"{company} — {contact_name}" if company and contact_name else (company or contact_name or "Unknown")

        stage_id = False
        xml_id = STAGE_MAPPING.get(dto.lead_status_raw)
        if xml_id:
            stage = self.env.ref(xml_id, raise_if_not_found=False)
            stage_id = stage.id if stage else False
        if not stage_id:
            stage = self.env.ref("plasticos_crm_bridge.stage_new", raise_if_not_found=False)
            stage_id = stage.id if stage else False

        source_id = False
        if dto.lead_source_raw:
            utm_name = LEAD_SOURCE_MAPPING.get(dto.lead_source_raw.strip(), "Other")
            source = self.env["utm.source"].search([("name", "=", utm_name)], limit=1)
            source_id = source.id if source else False

        country_id = False
        if dto.country_code:
            country = self.env["res.country"].search(
                [
                    "|",
                    ("code", "=", dto.country_code.strip().upper()[:2]),
                    ("name", "ilike", dto.country_code.strip()),
                ],
                limit=1,
            )
            country_id = country.id if country else False

        state_id = False
        if dto.state_code:
            domain = [("code", "=", dto.state_code.strip().upper())]
            if country_id:
                domain.append(("country_id", "=", country_id))
            state = self.env["res.country.state"].search(domain, limit=1)
            state_id = state.id if state else False

        user_id = False
        if dto.owner_name and dto.owner_name.strip() not in ("FALSE", ""):
            user = self.env["res.users"].search([("name", "ilike", dto.owner_name.strip())], limit=1)
            user_id = user.id if user else False

        return {
            "name": name,
            "type": "lead",
            "partner_name": company or False,
            "contact_name": contact_name or False,
            "email_from": dto.email or False,
            "phone": dto.phone or False,
            "mobile": dto.mobile or False,
            "street": dto.street or False,
            "street2": dto.street2 or False,
            "city": dto.city or False,
            "state_id": state_id,
            "zip": dto.zip or False,
            "country_id": country_id,
            "stage_id": stage_id,
            "source_id": source_id,
            "user_id": user_id,
            "vanillasoft_id": dto.external_id,
        }

    def _upsert_calls(self, connection, batch: list[CanonicalCall], run) -> int:
        Call = self.env["plasticos.crm.call.event"]
        Orphan = self.env["plasticos.crm.sync.orphan"]
        Ref = self.env["plasticos.crm.external.ref"]
        created = 0
        orphans = 0
        for dto in batch:
            existing = Call.search(
                [("provider", "=", dto.provider), ("external_id", "=", dto.external_id)],
                limit=1,
            )
            lead = self._find_lead(dto.provider, dto.contact_external_id, Ref)
            vals = {
                "provider": dto.provider,
                "external_id": dto.external_id,
                "contact_external_id": dto.contact_external_id,
                "call_datetime_utc": _dt_naive_utc(dto.call_datetime_utc),
                "duration_seconds": dto.duration_seconds,
                "user_name": dto.user_name or False,
                "result_code": dto.result_code or False,
                "comment": dto.comment or False,
                "lead_id": lead.id if lead else False,
            }
            if existing:
                existing.write(vals)
            elif not lead:
                Orphan.create(
                    {
                        "connection_id": connection.id,
                        "provider": dto.provider,
                        "kind": "call",
                        "contact_external_id": dto.contact_external_id,
                        "external_id": dto.external_id,
                        "payload_json": {
                            "provider": dto.provider,
                            "external_id": dto.external_id,
                            "contact_external_id": dto.contact_external_id,
                            "call_datetime_utc": dto.call_datetime_utc,
                            "duration_seconds": dto.duration_seconds,
                            "user_name": dto.user_name,
                            "result_code": dto.result_code,
                            "comment": dto.comment,
                        },
                    }
                )
                orphans += 1
            else:
                Call.create(vals)
                created += 1
        if run and orphans:
            run.orphans_buffered = (run.orphans_buffered or 0) + orphans
        return created

    def _sync_tables_for_lead(self, connection, adapter, contact_external_id: str, lead=None):
        Ref = self.env["plasticos.crm.external.ref"]
        Row = self.env["plasticos.crm.external.table.row"]
        Orphan = self.env["plasticos.crm.sync.orphan"]
        if lead is None:
            lead = self._find_lead(connection.provider, contact_external_id, Ref)
        for dto in adapter.iter_table_rows(contact_external_id):
            if not lead:
                Orphan.create(
                    {
                        "connection_id": connection.id,
                        "provider": dto.provider,
                        "kind": "table_row",
                        "contact_external_id": dto.contact_external_id,
                        "external_id": dto.external_row_id,
                        "payload_json": {
                            "provider": dto.provider,
                            "contact_external_id": dto.contact_external_id,
                            "table_id": dto.table_id,
                            "table_name": dto.table_name,
                            "external_row_id": dto.external_row_id,
                            "fields": dto.fields,
                        },
                    }
                )
                continue
            existing = Row.search(
                [
                    ("provider", "=", dto.provider),
                    ("table_id", "=", dto.table_id),
                    ("external_row_id", "=", dto.external_row_id),
                ],
                limit=1,
            )
            vals = {
                "provider": dto.provider,
                "lead_id": lead.id,
                "contact_external_id": dto.contact_external_id,
                "table_id": dto.table_id,
                "table_name": dto.table_name or False,
                "external_row_id": dto.external_row_id,
                "fields_json": dto.fields,
            }
            if existing:
                existing.write(vals)
            else:
                Row.create(vals)

    def _resolve_orphans(self, connection, adapter, run) -> int:
        Orphan = self.env["plasticos.crm.sync.orphan"]
        Call = self.env["plasticos.crm.call.event"]
        Row = self.env["plasticos.crm.external.table.row"]
        Ref = self.env["plasticos.crm.external.ref"]
        orphans = Orphan.search(
            [
                ("connection_id", "=", connection.id),
                ("resolved", "=", False),
            ]
        )
        resolved = 0
        for orphan in orphans:
            lead = self._find_lead(orphan.provider, orphan.contact_external_id, Ref)
            if not lead:
                continue
            payload = orphan.payload_json or {}
            if orphan.kind == "call":
                existing = Call.search(
                    [
                        ("provider", "=", payload.get("provider")),
                        ("external_id", "=", payload.get("external_id")),
                    ],
                    limit=1,
                )
                vals = {
                    "provider": payload.get("provider"),
                    "external_id": payload.get("external_id"),
                    "contact_external_id": payload.get("contact_external_id"),
                    "call_datetime_utc": _dt_naive_utc(payload.get("call_datetime_utc")),
                    "duration_seconds": int(payload.get("duration_seconds") or 0),
                    "user_name": payload.get("user_name") or False,
                    "result_code": payload.get("result_code") or False,
                    "comment": payload.get("comment") or False,
                    "lead_id": lead.id,
                }
                if existing:
                    existing.write(vals)
                else:
                    Call.create(vals)
            elif orphan.kind == "table_row":
                existing = Row.search(
                    [
                        ("provider", "=", payload.get("provider")),
                        ("table_id", "=", payload.get("table_id")),
                        ("external_row_id", "=", payload.get("external_row_id")),
                    ],
                    limit=1,
                )
                vals = {
                    "provider": payload.get("provider"),
                    "lead_id": lead.id,
                    "contact_external_id": payload.get("contact_external_id"),
                    "table_id": payload.get("table_id"),
                    "table_name": payload.get("table_name") or False,
                    "external_row_id": payload.get("external_row_id"),
                    "fields_json": payload.get("fields") or {},
                }
                if existing:
                    existing.write(vals)
                else:
                    Row.create(vals)
            orphan.resolved = True
            resolved += 1
        if run:
            run.orphans_resolved = resolved
        return resolved

    def _find_lead(self, provider: str, contact_external_id: str, Ref):
        ref = Ref.search(
            [
                ("provider", "=", provider),
                ("external_id", "=", contact_external_id),
                ("res_model", "=", CRM_LEAD),
            ],
            limit=1,
        )
        if ref:
            lead = self.env[CRM_LEAD].browse(ref.res_id)
            if lead.exists():
                return lead
        return self.env[CRM_LEAD].search([("vanillasoft_id", "=", contact_external_id)], limit=1)
