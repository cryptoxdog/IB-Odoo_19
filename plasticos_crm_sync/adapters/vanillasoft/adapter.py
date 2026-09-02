"""Live VanillaSoft CrmAdapter — maps API JSON to canonical DTOs."""

from __future__ import annotations

import logging
from collections.abc import Iterator
from typing import Any

from ..base import CanonicalCall, CanonicalLead, CanonicalTableRow, CrmAdapterError
from .client import VanillaSoftClient

_logger = logging.getLogger(__name__)

PROVIDER = "vanillasoft"

# Explicit launch classification for VanillaSoft custom-table rows.
#
# There is no third state where custom-table data is operationally required but
# the implementation treats a fetch failure as optional. For launch these rows
# are supplementary enrichment attached to a contact — the CRM record itself is
# already complete without them — so they are OPTIONAL: a fetch failure is
# logged and the contact page still acknowledges (I15). Flip this to True the
# moment product treats a custom table as required launch CRM data; the fetch
# failure then propagates and the page's watermark does not advance (I1).
CUSTOM_TABLES_REQUIRED = False


# VanillaSoft renders JSON booleans inconsistently across endpoints: a native
# JSON boolean on some payloads, the integers 1/0 on others, and the quoted
# strings "true"/"false"/"1"/"0" on form-style posts. Python truthiness reads
# the string "false" as True, which silently inverts every negative flag — a
# live contact archived as deleted, an enabled phone number dropped as
# disabled. The accepted spellings below are exactly those representations;
# nothing is added on speculation, so an unrecognised value fails loudly rather
# than defaulting to True.
_VS_TRUE = frozenset({"true", "1"})
_VS_FALSE = frozenset({"false", "0", ""})


def vs_bool(value: Any, *, field: str) -> bool:
    """Coerce a VanillaSoft payload boolean strictly.

    Absent (``None``) is False — the provider omits a flag it does not set.
    An unknown non-empty representation raises: guessing True there is the
    exact silent corruption this parser exists to prevent.
    """
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        if value in (0, 1):
            return bool(value)
        raise CrmAdapterError(f"VanillaSoft {field}: unsupported boolean integer {value!r}")
    if isinstance(value, str):
        text = value.strip().lower()
        if text in _VS_TRUE:
            return True
        if text in _VS_FALSE:
            return False
        raise CrmAdapterError(f"VanillaSoft {field}: unsupported boolean string {value!r}")
    raise CrmAdapterError(f"VanillaSoft {field}: unsupported boolean type {type(value).__name__}")


def _first_present(raw: dict[str, Any], *keys: str) -> Any:
    """First key actually present in the payload — absence, not falsiness."""
    for key in keys:
        if key in raw:
            return raw[key]
    return None


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
        if vs_bool(_first_present(p, "disabled", "Disabled"), field="phone_numbers[].disabled"):
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

    deleted = vs_bool(_first_present(raw, "deleted", "Deleted"), field="deleted")
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


def call_to_canonical(raw: dict[str, Any]) -> CanonicalCall:
    """Map a raw call row to a canonical DTO.

    I1 — a call without a stable identity cannot be persisted or de-duplicated,
    so it fails the current call window rather than being dropped while the
    window watermark advances past it.
    """
    call_id = raw.get("call_history_id") or raw.get("CallHistoryID") or raw.get("id")
    contact_id = raw.get("contact_id") or raw.get("ContactID")
    if call_id is None:
        raise CrmAdapterError("Call payload missing call_history_id")
    if contact_id is None:
        raise CrmAdapterError(f"Call {call_id} payload missing contact_id")
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
            # I1 — every required row is transformed or the page fails. A
            # malformed contact must never be logged-and-skipped while the
            # watermark advances past it: that is permanent silent omission.
            leads: list[CanonicalLead] = []
            for index, row in enumerate(rows):
                if not isinstance(row, dict):
                    raise CrmAdapterError(f"Contact row {index} is {type(row).__name__}, expected object")
                leads.append(contact_to_canonical(row))
            api_cursor = None
            partial = False
            if isinstance(payload, dict):
                raw_cursor = payload.get("batch_end") or payload.get("BatchEnd")
                api_cursor = str(raw_cursor) if raw_cursor else None
                partial = bool(payload.get("partial_fulfillment") or payload.get("PartialFulfillment"))
            # A partial response promises more contacts than it returned. Only an
            # API-supplied `batch_end` is a trustworthy place to resume from: the
            # last row's `modified_date_time_utc` is not documented as a lossless
            # cursor, and contacts sharing one timestamp would be skipped by it.
            # Raise before yielding, so nothing on this page is acknowledged.
            if partial and api_cursor is None:
                raise CrmAdapterError(
                    f"VanillaSoft reported partial contact fulfillment without a batch_end "
                    f"cursor at {cursor!r}; refusing to infer one from row timestamps"
                )
            # On a complete page the synthesized value is a watermark, not a
            # continuation cursor: it names the last contact actually persisted.
            batch_end = api_cursor
            if batch_end is None and leads:
                batch_end = leads[-1].modified_utc or None
            yield leads, str(batch_end) if batch_end else None, partial
            if not rows or not partial:
                break
            # `api_cursor` is an ordered ISO-8601 UTC timestamp, so forward
            # progress is checkable directly; a non-advancing partial page would
            # otherwise loop forever re-reading the same rows.
            if api_cursor <= str(cursor):
                raise CrmAdapterError(f"Contact pagination failed to advance: {cursor!r} -> {api_cursor!r}")
            cursor = api_cursor

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
            for index, row in enumerate(rows):
                if not isinstance(row, dict):
                    raise CrmAdapterError(f"Call row {index} is {type(row).__name__}, expected object")
                batch.append(call_to_canonical(row))
            if batch:
                yield batch
            if not rows or len(rows) < page_limit:
                # Short page — the window is genuinely exhausted. This is the
                # only exit that lets `_sync_calls` advance the window
                # watermark, because normal iterator completion is exactly what
                # it reads as "the whole window was consumed".
                break
            # A full page means more calls may exist past it, so ending here
            # would let the caller acknowledge the entire window on the strength
            # of a page we could not paginate past (I1). Fail the window instead.
            last_ts = None
            for call in batch:
                ts = call.call_datetime_utc
                if ts and (last_ts is None or str(ts) > str(last_ts)):
                    last_ts = ts
            if not last_ts:
                raise CrmAdapterError(
                    f"Full call-history page ({len(rows)} rows) has no usable pagination "
                    f"timestamp; cannot prove the window from {cursor_start!r} was consumed"
                )
            if str(last_ts) <= str(cursor_start):
                # Deliberately no epsilon: calls share timestamps, so nudging the
                # cursor forward would skip every other call at that instant.
                raise CrmAdapterError(
                    f"Call pagination failed to advance: {cursor_start!r} -> {last_ts!r} "
                    f"({len(rows)} rows at the page limit)"
                )
            cursor_start = str(last_ts)

    def iter_calls_for_contact(self, contact_external_id: str) -> Iterator[list[CanonicalCall]]:
        """Per-contact call history (E2E / webhook enrichment path)."""
        payload = self.client.get_call_history_by_contact(contact_external_id)
        rows = _extract_list(payload, "call_histories", "call_history", "CallHistory", "calls", "data", "results")
        if isinstance(payload, list):
            rows = payload
        batch: list[CanonicalCall] = []
        for index, row in enumerate(rows):
            if not isinstance(row, dict):
                raise CrmAdapterError(f"Call row {index} is {type(row).__name__}, expected object")
            batch.append(call_to_canonical(row))
        if batch:
            yield batch

    def iter_table_rows(self, contact_external_id: str) -> Iterator[CanonicalTableRow]:
        try:
            tables_payload = self.client.get_custom_tables_list(self.project_id)
        except CrmAdapterError:
            if CUSTOM_TABLES_REQUIRED:
                raise
            _logger.warning("Custom tables list failed for project %s", self.project_id)
            return
        tables = _extract_list(tables_payload, "custom_tables", "CustomTables", "tables", "data")
        if not tables:
            # Attempt catch-all fetch without table id
            try:
                data = self.client.get_custom_table_data(contact_external_id)
            except CrmAdapterError:
                if CUSTOM_TABLES_REQUIRED:
                    raise
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
                if CUSTOM_TABLES_REQUIRED:
                    raise
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
            # The row's canonical identity is `(provider, table_id,
            # external_row_id)` and it is persisted under a unique constraint.
            # Falling back to `idx` manufactured that identity from list
            # position, so row 0 of contact A and row 0 of contact B collided on
            # one durable key and each import overwrote the other's enrichment.
            # Custom-table rows are OPTIONAL launch data (CUSTOM_TABLES_REQUIRED
            # above): skipping one loses nothing the CRM record needs, whereas
            # persisting it under an invented key corrupts a different contact.
            rid = _first_present(row, "data_id", "id", "DataID")
            if rid is None or not str(rid).strip():
                _logger.warning(
                    "Skipping custom-table row without a stable source id: contact=%s table=%s position=%s keys=%s",
                    contact_external_id,
                    table_id,
                    idx,
                    sorted(row.keys()),
                )
                continue
            fields = {k: str(v) for k, v in row.items() if v is not None and k not in ("data_id", "id", "DataID")}
            yield CanonicalTableRow(
                provider=PROVIDER,
                contact_external_id=str(contact_external_id),
                table_id=str(table_id),
                table_name=table_name,
                external_row_id=str(rid),
                fields=fields,
            )
