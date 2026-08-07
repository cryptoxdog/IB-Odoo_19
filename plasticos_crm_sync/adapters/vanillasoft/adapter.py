"""Live VanillaSoft CrmAdapter — maps API JSON to canonical DTOs."""

from __future__ import annotations

import logging
from collections.abc import Iterator
from typing import Any

from ..base import CanonicalCall, CanonicalLead, CanonicalTableRow, CrmAdapterError
from .client import VanillaSoftClient

_logger = logging.getLogger(__name__)

PROVIDER = "vanillasoft"


def _cf_map(raw: Any) -> dict[str, str]:
    out: dict[str, str] = {}
    if not raw:
        return out
    if isinstance(raw, dict):
        for k, v in raw.items():
            if v is not None:
                out[str(k)] = str(v)
        return out
    if isinstance(raw, list):
        for item in raw:
            if not isinstance(item, dict):
                continue
            name = item.get("name") or item.get("Name") or item.get("field_name")
            value = item.get("value")
            if value is None:
                value = item.get("Value")
            if name is not None and value is not None:
                out[str(name)] = str(value)
    return out


def _phone_from_list(phones: Any, preferred: tuple[str, ...]) -> str:
    if not phones or not isinstance(phones, list):
        return ""
    by_name: dict[str, str] = {}
    first = ""
    for p in phones:
        if not isinstance(p, dict):
            continue
        if p.get("disabled"):
            continue
        name = str(p.get("name") or "").strip().lower()
        number = str(p.get("number") or "").strip()
        if not number:
            continue
        if not first:
            first = number
        by_name[name] = number
    for key in preferred:
        if key in by_name:
            return by_name[key]
    return first


def contact_to_canonical(raw: dict[str, Any]) -> CanonicalLead:
    custom = _cf_map(raw.get("custom_fields"))
    phones = raw.get("phone_numbers")
    contact_id = raw.get("contact_id") or raw.get("ContactID") or raw.get("id")
    if contact_id is None:
        raise CrmAdapterError("Contact payload missing contact_id")

    lead_status = (
        custom.get("Lead Status")
        or custom.get("LeadStatus")
        or str(raw.get("lead_status") or raw.get("Lead Status") or "")
    )
    lead_source = (
        custom.get("Lead Source")
        or custom.get("LeadSource")
        or str(raw.get("lead_source") or raw.get("Lead Source") or "")
    )
    owner = custom.get("Contact Owner") or str(
        raw.get("user_name") or raw.get("owner") or raw.get("Contact Owner") or ""
    )

    deleted = bool(raw.get("deleted") or raw.get("Deleted") or False)
    modified = str(
        raw.get("modified_date_time_utc") or raw.get("modified_datetime_utc") or raw.get("ModifiedDateTimeUTC") or ""
    )

    return CanonicalLead(
        provider=PROVIDER,
        external_id=str(contact_id),
        company=str(raw.get("company") or raw.get("Company") or ""),
        first_name=str(raw.get("first_name") or raw.get("First Name") or ""),
        last_name=str(raw.get("last_name") or raw.get("Last Name") or ""),
        email=str(raw.get("email") or raw.get("Email") or ""),
        phone=_phone_from_list(phones, ("direct", "phone", "work", "office"))
        or str(raw.get("phone") or raw.get("Direct") or ""),
        mobile=_phone_from_list(phones, ("mobile", "mobile 1", "cell"))
        or str(raw.get("mobile") or raw.get("Mobile 1") or ""),
        street=str(raw.get("address") or raw.get("Address") or raw.get("street") or ""),
        street2=str(raw.get("address_2") or raw.get("Address 2") or raw.get("street2") or ""),
        city=str(raw.get("city") or raw.get("City") or ""),
        state_code=str(raw.get("state") or raw.get("State") or ""),
        zip=str(raw.get("zip") or raw.get("Zip") or raw.get("zip_code") or ""),
        country_code=str(raw.get("country") or raw.get("Country") or ""),
        lead_status_raw=lead_status,
        lead_source_raw=lead_source,
        owner_name=owner,
        modified_utc=modified,
        deleted=deleted,
        custom_fields=custom,
    )


def call_to_canonical(raw: dict[str, Any]) -> CanonicalCall | None:
    call_id = raw.get("call_history_id") or raw.get("CallHistoryID") or raw.get("id")
    contact_id = raw.get("contact_id") or raw.get("ContactID")
    if call_id is None or contact_id is None:
        return None
    return CanonicalCall(
        provider=PROVIDER,
        external_id=str(call_id),
        contact_external_id=str(contact_id),
        call_datetime_utc=str(raw.get("call_date_time_utc") or raw.get("CallDateTimeUTC") or ""),
        duration_seconds=int(raw.get("duration_seconds") or raw.get("DurationSeconds") or 0),
        user_name=str(raw.get("user_name") or raw.get("UserName") or ""),
        result_code=str(raw.get("result_code") or raw.get("ResultCode") or ""),
        comment=str(raw.get("comment") or raw.get("comments") or raw.get("Comment") or ""),
    )


def _extract_list(payload: Any, *keys: str) -> list:
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict):
        return []
    for key in keys:
        val = payload.get(key)
        if isinstance(val, list):
            return val
    return []


class VanillaSoftAdapter:
    provider = PROVIDER
    live = True

    def __init__(self, client: VanillaSoftClient, project_id: int):
        self.client = client
        self.project_id = project_id

    def healthcheck(self) -> dict[str, Any]:
        data = self.client.verify_key()
        projects = data.get("projects") or data.get("Projects") or []
        project_ids = set()
        for p in projects if isinstance(projects, list) else []:
            if isinstance(p, dict):
                pid = p.get("project_id") or p.get("ProjectID") or p.get("id")
                if pid is not None:
                    project_ids.add(int(pid))
            elif isinstance(p, (int, str)):
                project_ids.add(int(p))
        if project_ids and self.project_id not in project_ids:
            raise CrmAdapterError(f"Project {self.project_id} not in VerifyKey projects {sorted(project_ids)}")
        return data if isinstance(data, dict) else {"raw": data}

    def iter_contacts(
        self,
        *,
        modified_after: str,
        limit: int = 200,
    ) -> Iterator[tuple[list[CanonicalLead], str | None, bool]]:
        """Yield (leads, batch_end, partial_fulfillment) pages until exhausted."""
        cursor = modified_after
        while True:
            payload = self.client.get_contacts(
                self.project_id,
                cursor,
                limit=limit,
                custom_fields=True,
                phone_numbers=True,
            )
            rows = _extract_list(payload, "contacts", "Contacts", "data", "results")
            leads: list[CanonicalLead] = []
            for row in rows:
                if isinstance(row, dict):
                    try:
                        leads.append(contact_to_canonical(row))
                    except CrmAdapterError:
                        _logger.warning("Skipping malformed VanillaSoft contact", exc_info=True)
            batch_end = None
            partial = False
            if isinstance(payload, dict):
                batch_end = payload.get("batch_end") or payload.get("BatchEnd")
                partial = bool(payload.get("partial_fulfillment") or payload.get("PartialFulfillment"))
            if not batch_end and leads:
                batch_end = leads[-1].modified_utc or None
            yield leads, str(batch_end) if batch_end else None, partial
            if not rows or not partial:
                break
            if not batch_end:
                break
            cursor = str(batch_end)

    def get_contact(self, external_id: str) -> CanonicalLead | None:
        payload = self.client.get_contact(external_id, custom_fields=True, phone_numbers=True)
        if not payload:
            return None
        raw = payload
        if isinstance(payload, dict):
            nested = payload.get("contact") or payload.get("Contact")
            if isinstance(nested, dict):
                raw = nested
        if not isinstance(raw, dict):
            return None
        return contact_to_canonical(raw)

    def iter_calls(
        self,
        *,
        start: str,
        end: str,
        limit: int = 500,
    ) -> Iterator[list[CanonicalCall]]:
        """Yield call batches until the window is exhausted.

        VanillaSoft ``GetCallHistory`` is limit-capped; when a page fills the
        limit we advance ``start`` past the last call timestamp so later pages
        in the same window are not skipped when the orchestrator advances the
        watermark.
        """
        cursor_start = start
        page_limit = min(max(limit, 1), 20000)
        while True:
            payload = self.client.get_call_history_batch(
                cursor_start,
                end,
                project_id=self.project_id,
                limit=page_limit,
            )
            rows = _extract_list(payload, "call_histories", "call_history", "CallHistory", "calls", "data", "results")
            batch: list[CanonicalCall] = []
            for row in rows:
                if not isinstance(row, dict):
                    continue
                call = call_to_canonical(row)
                if call:
                    batch.append(call)
            if batch:
                yield batch
            if not rows or len(rows) < page_limit:
                break
            # Advance cursor past the latest call in this page (ISO Z timestamps).
            last_ts = None
            for call in batch:
                ts = call.call_datetime_utc
                if ts and (last_ts is None or str(ts) > str(last_ts)):
                    last_ts = ts
            if not last_ts or str(last_ts) <= str(cursor_start):
                break
            cursor_start = str(last_ts)

    def iter_calls_for_contact(self, contact_external_id: str) -> Iterator[list[CanonicalCall]]:
        """Per-contact call history (E2E / webhook enrichment path)."""
        payload = self.client.get_call_history_by_contact(contact_external_id)
        rows = _extract_list(payload, "call_histories", "call_history", "CallHistory", "calls", "data", "results")
        if isinstance(payload, list):
            rows = payload
        batch: list[CanonicalCall] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            call = call_to_canonical(row)
            if call:
                batch.append(call)
        if batch:
            yield batch

    def iter_table_rows(self, contact_external_id: str) -> Iterator[CanonicalTableRow]:
        try:
            tables_payload = self.client.get_custom_tables_list(self.project_id)
        except CrmAdapterError:
            _logger.warning("Custom tables list failed for project %s", self.project_id)
            return
        tables = _extract_list(tables_payload, "custom_tables", "CustomTables", "tables", "data")
        if not tables:
            # Attempt catch-all fetch without table id
            try:
                data = self.client.get_custom_table_data(contact_external_id)
            except CrmAdapterError:
                return
            yield from self._rows_from_payload(contact_external_id, "0", "default", data)
            return
        for table in tables:
            if not isinstance(table, dict):
                continue
            tid = table.get("table_id") or table.get("TableID") or table.get("id")
            tname = str(table.get("name") or table.get("Name") or tid or "")
            if tid is None:
                continue
            try:
                data = self.client.get_custom_table_data(contact_external_id, table_id=tid)
            except CrmAdapterError:
                _logger.warning(
                    "Custom table fetch failed contact=%s table=%s",
                    contact_external_id,
                    tid,
                )
                continue
            yield from self._rows_from_payload(contact_external_id, str(tid), tname, data)

    def _rows_from_payload(
        self,
        contact_external_id: str,
        table_id: str,
        table_name: str,
        payload: Any,
    ) -> Iterator[CanonicalTableRow]:
        rows = _extract_list(payload, "rows", "data", "results", "custom_table_data")
        if isinstance(payload, dict) and not rows:
            # Single row object
            if payload.get("data_id") or payload.get("id"):
                rows = [payload]
        for idx, row in enumerate(rows):
            if not isinstance(row, dict):
                continue
            rid = row.get("data_id") or row.get("id") or row.get("DataID") or idx
            fields = {k: str(v) for k, v in row.items() if v is not None and k not in ("data_id", "id")}
            yield CanonicalTableRow(
                provider=PROVIDER,
                contact_external_id=str(contact_external_id),
                table_id=str(table_id),
                table_name=table_name,
                external_row_id=str(rid),
                fields=fields,
            )
