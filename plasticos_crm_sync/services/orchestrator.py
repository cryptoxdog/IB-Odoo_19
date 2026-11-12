"""CRM sync orchestrator — DTO → ORM write path with watermarks and orphans."""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime, timedelta
from typing import Any

from ..adapters.base import (
    CanonicalCall,
    CanonicalLead,
    CrmAdapterError,
    is_excluded_source_field,
    omit_excluded_source_fields,
)
from ..adapters.registry import get_adapter
from .approved_identity import (
    XMLID_MODULE,
    CrosswalkError,
    comment_holds,
    comment_with_note,
    load_crosswalk_map,
    phone_identity_key,
    without_excluded_source_paragraphs,
    xmlid_name,
)
from .import_summary import (
    OPTIONAL_CONTEXT,
    REQUIRED_MAPPING,
    _public_message,
    informational_notices,
    required_mapping_errors,
)
from .owner_crosswalk import OwnerResolutionError, resolve_salesperson

_logger = logging.getLogger(__name__)

CRM_LEAD = "crm.lead"
CONTACT_PAGE_SIZE = 200
CALL_BATCH_SIZE = 500

# VanillaSoft custom fields with no approved native lead target. Each is kept
# as one source-labelled paragraph of ``crm.lead.description`` when the payload
# carries it; none becomes a partner relationship, tag, facility, call or
# activity. Names are the exact source fields of the approved census.
LEAD_CONTEXT_FIELDS = (
    "Buyer/Supplier",
    "Company Type",
    "Location Type",
    "Location",
    "Last Result Code",
    "Last Call Date",
)

# Contact-owned notes whose approved destination is the lead description or the
# ERP person's comment. ``Notes (PPS)`` belongs on a material profile and is
# intentionally absent: a contact note must not count as that import.
CONTACT_SECTION_NOTE_FIELDS = (
    "Notes (MRP)",
    "Notes (LDPE)",
    "Notes (HDPE)",
    "Notes (PP)",
)
CONTACT_PROVENANCE_FIELDS = ("Notes", "Last Result Code", "Last Call Date", *CONTACT_SECTION_NOTE_FIELDS)

# The Contacts list endpoint accepts `modified_after` only within this lookback.
# Incremental runs clamp to it. The full import deliberately does not, and
# instead verifies at runtime that the older floor it asked for was actually
# honoured — see `run_full_import`.
CONTACT_LOOKBACK_MAX_DAYS = 31
INCREMENTAL_CONTACT_LOOKBACK_DAYS = 30

# Bootstrap and catch-up overlap on the call timeline rather than abutting, so a
# call written while the bootstrap was running cannot fall through a seam left
# by clock skew between Odoo and VanillaSoft. Calls carry a provider-stable
# `call_history_id`, so the re-read is idempotent.
CATCHUP_OVERLAP = timedelta(minutes=5)


class CrmSyncLockedError(CrmAdapterError):
    """Another synchronization already holds this connection's advisory lock."""


class CrmFullImportArgumentError(CrmAdapterError):
    """`run_full_import` was given a missing or unusable historical bound."""


def advisory_lock_key(connection_id: int) -> str:
    """Session advisory-lock key for one connection (shared by cron and UI)."""
    return f"plasticos_crm_sync.connection.{connection_id}"


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


def completion_notice(run) -> tuple[str, str]:
    """``(notification type, message)`` for a run that finished without raising.

    A manual caller that treats every normal return as success would turn the
    ``failed`` / ``partial`` status this module now computes back into a green
    toast. The run row is the fact; this names it for the operator.
    """
    status = getattr(run, "status", None) or "unknown"
    if status == "success":
        return "success", "Sync finished"
    excerpt = str(getattr(run, "error_excerpt", "") or "").strip().splitlines()
    detail = excerpt[0] if excerpt else "see the run's error excerpt"
    if status == "failed":
        return "danger", f"Sync finished with failures: {detail}"
    return "warning", f"Sync finished {status}: {detail}"


def _forward_only(current: str | None, candidate: str) -> str | None:
    """Return `candidate`, or None when writing it would rewind `current`.

    A full import replays history the incremental path already consumed, so its
    per-page watermark writes are older than what the connection already holds.
    Letting them land would reset a valid watermark and make the next
    `run_connection` re-read months of source data. Unparseable values fall
    through to the caller's write, preserving the pre-existing behaviour.
    """
    cur = _parse_utc(current)
    new_dt = _parse_utc(candidate)
    if cur and new_dt and new_dt <= cur:
        return None
    return candidate


# Per-record outcome classification (odoo-intent-1 ingestion milestone).
# Every source record is deterministically classified; failures are recorded
# per record (never silent loss) and persisted on plasticos.crm.sync.run.
# ``deferred`` is the call-only outcome for a row buffered as an orphan (its
# lead is not imported yet): the durable orphan record keeps the row, the
# run's ``orphans_buffered`` counter persists the count, and the shared
# summary reports it as not-yet-landed — so every seen row is accounted
# exactly once and never mistaken for a successful write.
OUTCOME_FIELDS = ("created", "updated", "unchanged", "duplicate_rejected", "failed", "deferred")
# Outcomes after which a lead is admitted: identity resolved without conflict
# and the row landed (or already matched). Only these may receive dependent
# writes (custom-table rows, calls). ``duplicate_rejected`` and ``failed``
# must produce zero child-table side effects.
ADMITTED_OUTCOMES = ("created", "updated", "unchanged")

# Exact tokens only. "USA" must not match "USA Minor Outlying Islands" by substring.
_US_COUNTRY_ALIASES = frozenset(
    {
        "us",
        "usa",
        "united states",
        "united states of america",
    }
)


def _collapse_ws(value: str | None) -> str:
    return " ".join(str(value or "").split())


def _split_material_values(value) -> list[str]:
    text = str(value or "").replace("|", "\n").replace(";", "\n")
    return [part for part in (_collapse_ws(piece) for piece in text.splitlines()) if part]


def _material_field_kind(label: str) -> str:
    if label in {"materials", "material"} or label.startswith("material ("):
        return "phrase"
    if label in {"material form", "material type", "form"} or label.startswith("form ("):
        return "hint"
    return ""


def _material_inputs(*field_maps):
    phrases = []
    hints = {}
    weak = []
    for fields in field_maps:
        for key, value in omit_excluded_source_fields(fields).items():
            label = _collapse_ws(key).casefold()
            parts = _split_material_values(value)
            kind = _material_field_kind(label)
            if kind == "phrase":
                phrases.extend(_split_commas(parts))
            elif kind == "hint":
                if parts:
                    hints[label] = parts[0]
                weak.extend(parts)
    return _dedupe_phrases(phrases), hints, _dedupe_phrases(weak)


def _split_commas(parts) -> list[str]:
    """Split phrase pieces on ASCII commas. Hint values never reach this."""
    pieces = []
    for part in parts:
        for piece in part.split(","):
            collapsed = _collapse_ws(piece)
            if collapsed:
                pieces.append(collapsed)
    return pieces


def _dedupe_phrases(phrases) -> list[str]:
    seen = set()
    kept = []
    for phrase in phrases:
        key = phrase.casefold()
        if key in seen:
            continue
        seen.add(key)
        kept.append(phrase)
    return kept


_POUNDS_RE = re.compile(r"^([0-9][0-9,]*(?:\.[0-9]+)?)\s*(?:lbs?|pounds?)?$", re.IGNORECASE)
_SECTION_ALIASES = {
    "mrf": "mrf",
    "mrfs": "mrf",
    "mrp": "mrp",
    "pps": "pps",
    "ldpe": "ldpe",
    "hdpe": "hdpe",
    "pp": "pp",
}


def _section_key(label: str) -> str:
    if "(" not in label or ")" not in label:
        return ""
    token = label.split("(", 1)[1].split(")", 1)[0].replace("'s", "").replace("'", "").strip()
    return _SECTION_ALIASES.get(token, token)


def _material_slot(label: str) -> str:
    if label in {"materials", "material"} or label.startswith("material (") or label.startswith("materials ("):
        return "phrase"
    if label in {"material form", "material type", "form", "type"} or label.startswith(("form (", "type (")):
        return "hint"
    base = label.split("(", 1)[0].strip()
    if base == "weight":
        return "weight"
    if base in {"loads/month", "loads per month"}:
        return "loads"
    if base == "color":
        return "color"
    if base in {"notes", "previous content", "size"}:
        return "note"
    return ""


def _parse_material_sections(*field_maps) -> dict[str, dict]:
    """Group material evidence by source section. Hints never leave their section."""
    sections: dict[str, dict] = {}

    def bucket(key: str) -> dict:
        return sections.setdefault(
            key,
            {"phrases": [], "hints": [], "weights": [], "loads": [], "colors": [], "notes": []},
        )

    for fields in field_maps:
        if not isinstance(fields, dict):
            continue
        for key, value in omit_excluded_source_fields(fields).items():
            label = _collapse_ws(key).casefold()
            kind = _material_slot(label)
            if not kind:
                continue
            text = _collapse_ws(value)
            if not text:
                continue
            slot = bucket(_section_key(label))
            parts = _split_material_values(value)
            if kind == "phrase":
                slot["phrases"].extend(_split_commas(parts))
            elif kind == "hint":
                slot["hints"].append(parts[0] if parts else text)
            elif kind == "weight":
                slot["weights"].append(text)
            elif kind == "loads":
                slot["loads"].append(text)
            elif kind == "color":
                slot["colors"].extend(parts or [text])
            elif kind == "note":
                slot["notes"].append((str(key), text))
    for slot in sections.values():
        slot["phrases"] = _dedupe_phrases(slot["phrases"])
    return sections


def _pounds(value: str):
    match = _POUNDS_RE.fullmatch(_collapse_ws(value))
    if not match:
        return None
    number = float(match.group(1).replace(",", ""))
    if number <= 0:
        return None
    return number


def _loads_count(value: str):
    text = _collapse_ws(value)
    if not text.isdigit():
        return None
    return int(text)


def _facility_partner_for_person(partner):
    """An existing facility linked to this person. Nothing is created."""
    if not partner:
        return None, "facility unresolved"
    if partner.is_facility:
        return partner, ""
    parent = partner.parent_id
    if parent and parent.is_facility:
        return parent, ""
    children = partner.child_ids.filtered(lambda child: child.is_facility)
    if len(children) == 1:
        return children, ""
    if len(children) > 1:
        return None, "facility unresolved: ambiguous child facilities"
    return None, "facility unresolved"


def _selection_label(record, field_name: str) -> str:
    if field_name not in record._fields:
        return ""
    value = record[field_name]
    if not value:
        return ""
    selection = record._fields[field_name].selection
    if callable(selection):
        selection = selection(record)
    return str(dict(selection).get(value, ""))


def _company_type_overlaps(company, category_name: str) -> bool:
    """True when the descriptive category repeats an ERP role already stored."""
    target = _collapse_ws(category_name).casefold()
    if not target:
        return False
    for field_name in ("company_role", "facility_role"):
        label = _selection_label(company, field_name)
        if label and label.casefold() == target:
            return True
    partner_type = getattr(company, "partner_type_id", False)
    type_name = _collapse_ws(getattr(partner_type, "name", "") if partner_type else "")
    return bool(type_name) and type_name.casefold() == target


def _notes_only_sections(*field_maps) -> bool:
    sections = _parse_material_sections(*field_maps)
    if not sections:
        return False
    return not any(section["phrases"] or section["hints"] for section in sections.values())


def _verified_company(lead, partner):
    """The one company this source may classify, or None."""
    found = []
    if lead and getattr(lead, "id", False) and lead.partner_id:
        company = lead.partner_id if lead.partner_id.is_company else lead.partner_id.parent_id
        if company and company.is_company:
            found.append(company)
    if partner:
        company = partner if partner.is_company else partner.parent_id
        if company and company.is_company and all(company.id != item.id for item in found):
            found.append(company)
    if len(found) == 1:
        return found[0]
    return None


def _facility_for_material(lead):
    """Existing facility only. A missing or ambiguous facility is not created.

    A standalone company is a facility when the partner model says so. A parent
    with one child facility resolves to that child. Several children stay unresolved.
    """
    partner = lead.partner_id
    if not partner:
        return None, "facility unresolved"
    if partner.is_facility:
        return partner, ""
    parent = partner.parent_id
    if parent and parent.is_company and parent.parent_id:
        return parent, ""
    children = partner.child_ids.filtered(lambda child: child.is_company)
    if len(children) == 1:
        return children, ""
    if len(children) > 1:
        return None, "facility unresolved: ambiguous child facilities"
    return None, "facility unresolved"


def _country_token(value: str) -> str:
    return _collapse_ws(value).casefold()


def _us_mobile(number: str | None) -> bool:
    """True when ``number`` passes the crm.lead mobile rule (10-digit US, optional leading 1)."""
    digits = "".join(ch for ch in str(number or "") if ch.isdigit())
    if digits.startswith("1") and len(digits) == 11:
        digits = digits[1:]
    return len(digits) == 10


def _phone_line(kind: str, number: str | None) -> tuple[str, str]:
    """A classified line: ``(mobile|fax|other, number with extension, normalized)``."""
    return kind, phone_identity_key(number or "")


def _source_phones(dto: CanonicalLead) -> list[tuple[str, str, str]]:
    """``(source label, mobile|fax|other, number)`` for every source line, in source order.

    Typed entries carry the source classification. A DTO built without them
    falls back to the number tuples. The native primaries are added when the
    entries do not already hold them as the same classified line.
    """
    if dto.phone_entries:
        lines = [(entry.label or entry.kind, entry.kind, entry.number) for entry in dto.phone_entries]
    else:
        mobiles = {phone_identity_key(number) for number in (dto.mobile_numbers or ())}
        lines = []
        for number in dto.phone_numbers or ():
            kind = "mobile" if phone_identity_key(number) in mobiles else "other"
            lines.append((kind, kind, number))
    seen = {_phone_line(kind, number) for _label, kind, number in lines}
    for label, kind, number in (("Phone", "other", dto.phone), ("Mobile", "mobile", dto.mobile)):
        line = _phone_line(kind, number)
        if line[1] and line not in seen:
            lines.append((label, kind, number))
            seen.add(line)
    return lines


def _lead_mobile(dto: CanonicalLead) -> str | bool:
    """The first source mobile ``crm.lead.mobile`` accepts: the primary, then any other mobile."""
    candidates = [dto.mobile] + [entry.number for entry in dto.phone_entries if entry.kind == "mobile"]
    return next((number for number in candidates if number and _us_mobile(number)), False)


def provenance_line(external_id: str, field_name: str, value: str) -> str:
    """One source paragraph naming the ContactID and the exact source field."""
    return f"VanillaSoft ContactID {external_id} {field_name}: {value}"


# Exact lines this importer appends from the approved "pp supersacs" phrase.
# They are not prior identity. A longer preexisting supersac note still is.
_IMPORTER_SUPERSAC_LINES = frozenset({"pp supersacs"})
_HINT_STATUS_UNSUPPORTED = "unsupported"


def _preexisting_supersac_profile(profile) -> bool:
    """True when supersac identity was already on the profile, not written by this importer."""
    for raw in (profile.freeform_notes or "").splitlines():
        line = " ".join(raw.split())
        folded = line.casefold()
        if "supersac" not in folded:
            continue
        if folded in _IMPORTER_SUPERSAC_LINES or folded.startswith("vanillasoft contactid "):
            continue
        return True
    return False


def provenance_already_recorded(
    current, external_id: str, field_name: str, value: str, *, shared_owner: bool = False
) -> bool:
    """True only when this ContactID already has its own provenance line.

    Text equality is not an import. An ERP paragraph, or another contact's
    unlabelled ``VanillaSoft {field}:`` line, stays in the comment and does not
    count as this ContactID. A lead has one source contact, so its historic
    unlabelled predecessor is left as written instead of being copied again
    under a ContactID label.
    """
    text = str(value or "").strip()
    if not text:
        return True
    if comment_holds(current, provenance_line(external_id, field_name, text)):
        return True
    if shared_owner:
        return False
    return comment_holds(current, f"VanillaSoft {field_name}: {text}")


def _queue_provenance(
    lines: list[str], current, external_id: str, field_name: str, value: str, *, shared_owner: bool = False
) -> None:
    text = str(value or "").strip()
    if not text or provenance_already_recorded(current, external_id, field_name, text, shared_owner=shared_owner):
        return
    lines.append(provenance_line(external_id, field_name, text))


def _approved_context_lines(dto: CanonicalLead, current=None) -> list[str]:
    """Context paragraphs for an approved ERP person, each naming its VanillaSoft ContactID.

    Several ContactIDs can share one ERP person, so every line says which
    source contact it came from. Only fields the payload carries are kept.
    ``Notes`` is queued by the binder. A raw or unlabelled paragraph on this
    shared person is kept and is not this ContactID's import.
    """
    custom = dto.custom_fields or {}
    lines: list[str] = []
    for name in (*LEAD_CONTEXT_FIELDS, *CONTACT_SECTION_NOTE_FIELDS):
        if is_excluded_source_field(name):
            continue
        value = _collapse_ws(custom.get(name))
        if not value:
            continue
        if name in CONTACT_PROVENANCE_FIELDS:
            _queue_provenance(lines, current, dto.external_id, name, value, shared_owner=True)
        else:
            lines.append(provenance_line(dto.external_id, name, value))
    # Issue #299: Website and Title stay labelled source text on the ERP person;
    # its native website/function fields are not written until a mapping is approved.
    _queue_provenance(lines, current, dto.external_id, "Website", dto.website, shared_owner=True)
    _queue_provenance(lines, current, dto.external_id, "Title", dto.job_title, shared_owner=True)
    return lines


def _description_with(current, lines: list[str]):
    """``current`` with each line appended once as its own paragraph. ``None`` means no write."""
    description = current
    wrote = False
    for line in lines:
        merged = comment_with_note(description, line)
        if merged is not None:
            description = merged
            wrote = True
    return description if wrote else None


def _new_outcomes() -> dict[str, int]:
    return {"seen": 0, "table_rows": 0, **{key: 0 for key in OUTCOME_FIELDS}}


def _merge_outcomes(target: dict[str, int], source: dict[str, int] | None) -> dict[str, int]:
    if not source:
        return target
    for key, value in source.items():
        if isinstance(value, int):
            target[key] = target.get(key, 0) + value
    return target


def _write_contact_counters(run, seen: int, outcomes: dict[str, int], base: dict[str, int] | None = None) -> None:
    """Persist contact classification counters (called inside the page
    transaction, so a page rollback reverts these writes with the records)."""
    run.contacts_seen = (base.get("seen", 0) if base else 0) + seen
    run.contacts_created = (base.get("created", 0) if base else 0) + outcomes["created"]
    run.contacts_updated = (base.get("updated", 0) if base else 0) + outcomes["updated"]
    run.contacts_unchanged = (base.get("unchanged", 0) if base else 0) + outcomes["unchanged"]
    run.contacts_duplicate_rejected = (base.get("duplicate_rejected", 0) if base else 0) + outcomes[
        "duplicate_rejected"
    ]
    run.contacts_failed = (base.get("failed", 0) if base else 0) + outcomes["failed"]
    run.table_rows_upserted = (base.get("table_rows", 0) if base else 0) + outcomes["table_rows"]


def _write_call_counters(run, seen: int, outcomes: dict[str, int], base: dict[str, int] | None = None) -> None:
    run.calls_seen = (base.get("seen", 0) if base else 0) + seen
    run.calls_created = (base.get("created", 0) if base else 0) + outcomes["created"]
    run.calls_updated = (base.get("updated", 0) if base else 0) + outcomes["updated"]
    run.calls_unchanged = (base.get("unchanged", 0) if base else 0) + outcomes["unchanged"]
    run.calls_failed = (base.get("failed", 0) if base else 0) + outcomes["failed"]


def retained_table_orphan_payload(payload):
    """The same orphan payload with excluded source keys removed from ``fields`` only.

    A call payload, a non-dict, or a payload whose ``fields`` are already clean
    is returned unchanged. Other keys, including a call comment, are not read.
    """
    if not isinstance(payload, dict):
        return payload
    fields = payload.get("fields")
    if not isinstance(fields, dict):
        return payload
    cleaned = omit_excluded_source_fields(fields)
    if cleaned == fields:
        return payload
    updated = dict(payload)
    updated["fields"] = cleaned
    return updated


def _write_html_without_excluded_paragraphs(record, field_name: str) -> bool:
    current = record[field_name] or ""
    cleaned = without_excluded_source_paragraphs(current)
    if cleaned == str(current or ""):
        return False
    record.write({field_name: cleaned or False})
    return True


def purge_legacy_excluded_persistence(env) -> dict[str, int]:
    """Remove importer-owned excluded data already stored by an older sync.

    Leads are limited to those carrying a VanillaSoft id. Partner comments are
    limited to partners named by a VanillaSoft external ref. Table rows and
    table-row orphans are limited to provider ``vanillasoft``. Material and
    facility notes are not touched: they have no importer field label to prove
    the text was an excluded column.

    Archived records stay archived. A second call changes nothing.
    """
    counts = {
        "lead_rows": 0,
        "partner_rows": 0,
        "table_rows": 0,
        "orphan_rows": 0,
        "skipped_non_dict": 0,
    }
    leads = env["crm.lead"].with_context(active_test=False).search([("vanillasoft_id", "!=", False)])
    for lead in leads:
        if _write_html_without_excluded_paragraphs(lead, "description"):
            counts["lead_rows"] += 1
    refs = env["plasticos.crm.external.ref"].search(
        [("provider", "=", "vanillasoft"), ("res_model", "=", "res.partner")]
    )
    partners = env["res.partner"].with_context(active_test=False).browse(refs.mapped("res_id")).exists()
    for partner in partners:
        if _write_html_without_excluded_paragraphs(partner, "comment"):
            counts["partner_rows"] += 1
    rows = env["plasticos.crm.external.table.row"].search([("provider", "=", "vanillasoft")])
    for row in rows:
        raw = row.fields_json
        if not isinstance(raw, dict):
            if raw:
                counts["skipped_non_dict"] += 1
            continue
        cleaned = omit_excluded_source_fields(raw)
        if cleaned != raw:
            row.write({"fields_json": cleaned})
            counts["table_rows"] += 1
    orphans = env["plasticos.crm.sync.orphan"].search([("provider", "=", "vanillasoft"), ("kind", "=", "table_row")])
    for orphan in orphans:
        payload = orphan.payload_json
        if not isinstance(payload, dict):
            if payload:
                counts["skipped_non_dict"] += 1
            continue
        cleaned = retained_table_orphan_payload(payload)
        if cleaned is not payload:
            orphan.write({"payload_json": cleaned})
            counts["orphan_rows"] += 1
    return counts


def _differs(record, field_name: str, value) -> bool:
    """True when writing ``value`` would actually change ``record``.

    Tolerant of plain-object fakes in the pure-python tier: records without a
    ``_fields`` registry are compared attribute-wise.
    """
    fields = getattr(record, "_fields", None) or None
    if fields is not None and field_name not in fields:
        return False
    try:
        current = record[field_name]
    except (KeyError, TypeError):
        current = getattr(record, field_name, None)
    if hasattr(current, "id"):
        current = current.id or False
    return current != (value if value is not None else False)


class SyncOrchestrator:
    def __init__(self, env):
        self.env = env
        # Reset by every `_sync_contacts` pass; read by `run_full_import` as the
        # evidence that the requested historical floor was actually served.
        self.oldest_contact_modified_seen: datetime | None = None
        # Per-record classification accumulator, open only while a sync pass is
        # processing a page; per-record duplicate/failed details collected
        # during a run feed the shared import-run-summary errors.
        self.outcomes: dict[str, int] | None = None
        self.error_rows: list[dict[str, str]] = []
        # Classification of the most recent `_upsert_lead` call. `_upsert_lead`
        # returns a lead recordset for admitted AND rejected outcomes (pinned
        # contract), so callers gate dependent writes on this, never on the
        # returned record.
        self.last_lead_outcome: str | None = None

    def run_connection(self, connection) -> Any:
        connection.ensure_one()
        connection_id = connection.id
        self._ensure_caller_state_durable()
        # I5 — session advisory lock at the single choke point, so the cron and
        # the manual `action_sync_now` button exclude each other. Session locks
        # survive the page commits below (they are not transaction-scoped) and
        # are re-entrant within one backend session, so the cron's own outer
        # lock nests harmlessly.
        lock_key = advisory_lock_key(connection_id)
        if not self._try_advisory_lock(lock_key):
            raise CrmSyncLockedError(f"CRM sync already running for connection {connection_id}")
        try:
            # Scope is fixed before the audit row exists, so the row names what
            # this run asked the provider for even when it fails on the first
            # remote call. A run must read as "the rolling window" or "the
            # operator's floors" — never as an implied historical census.
            now = datetime.now(UTC)
            contact_from, clamped_from = self._incremental_contact_scope(connection)
            call_from = self._incremental_call_start(connection, now)
            # I2 — the audit record must exist independently of the fallible
            # remote work it describes, so create it on an owned cursor that
            # commits before the first adapter call.
            run_id = self._create_sync_run_durable(
                connection_id,
                {
                    "kind": "incremental",
                    "contact_scope_from_utc": contact_from,
                    "call_scope_from_utc": _iso_z(call_from),
                    "call_scope_to_utc": _iso_z(now),
                },
            )
            # That row was created and committed on a SECOND cursor. Odoo runs
            # cursors at REPEATABLE READ, and this transaction's snapshot was
            # taken by the advisory-lock SELECT above — before the row existed.
            # Without ending the transaction here, browse(run_id) is not in this
            # snapshot: .exists() is False and every write to it is an
            # "UPDATE ... WHERE id=N" matching zero rows, silently. Committing
            # starts a new transaction whose snapshot includes the row.
            # pg_try_advisory_lock is SESSION-scoped, so the lock survives this
            # commit exactly as it survives the page commits below (I5).
            self.env.cr.commit()
            run = self.env["plasticos.crm.sync.run"].browse(run_id)
            try:
                adapter = self._build_adapter(connection)
                adapter.healthcheck()
                contacts_n = self._sync_contacts(connection, adapter, run, modified_after_override=contact_from)
                calls_n = self._sync_calls(connection, adapter, run, start_override=call_from, end_override=now)
                resolved = self._resolve_orphans(connection, adapter, run)
                notes = [self._lookback_clamp_note(clamped_from, contact_from)] if clamped_from else []
                status, excerpt = self._completion(run, notes)
                run.write(
                    {
                        "status": status,
                        "finished_at": datetime.now(UTC).replace(tzinfo=None),
                        "contacts_upserted": contacts_n,
                        "calls_upserted": calls_n,
                        "orphans_resolved": resolved,
                        "error_excerpt": excerpt,
                    }
                )
                connection_vals: dict[str, Any] = {"last_error": excerpt}
                if status == "success":
                    connection_vals["last_success_at"] = datetime.now(UTC).replace(tzinfo=None)
                connection.write(connection_vals)
                # Land this connection's outcome before the caller (cron) moves
                # to the next one: a later connection's rollback must not erase
                # a successful run that already happened.
                self.env.cr.commit()
            except (CrmAdapterError, Exception) as exc:
                # I3 — capture primitives, then release every row this
                # transaction still holds BEFORE opening the failure cursor.
                # `_sync_contacts`/`_sync_calls` may leave an uncommitted write
                # on the sync-run row; a second cursor updating that same row
                # would wait on transaction A and hang the RPC.
                excerpt = _public_message(exc)
                _logger.exception("CRM sync failed connection=%s", connection_id)
                self.env.cr.rollback()
                # Recordset state from before the rollback is not trustworthy —
                # the durable write below re-browses from primitive ids only.
                self._persist_sync_failure_durable(connection_id, run_id, excerpt)
                raise
        finally:
            self._advisory_unlock(lock_key)
        return self.env["plasticos.crm.sync.run"].browse(run_id)

    def run_full_import(
        self,
        connection,
        call_history_floor: str,
        contact_modified_floor: str | None = None,
    ) -> Any:
        """Manual one-shot bootstrap, then hand off to the incremental path.

        `run_connection` is a rolling catch-up: it clamps contacts to the list
        endpoint's 30-day lookback and calls to a 7-day window, so on an empty
        database it produces a partial CRM, not a populated one. This method is
        the explicit "populate it once" operation an operator runs from the Odoo
        shell before switching to `run_connection`.

        Three phases inside one advisory lock and one sync-run audit row:

        1. contacts from `contact_modified_floor` (defaults to the call floor),
           with no rolling clamp;
        2. call history from `call_history_floor` to a UTC boundary captured
           BEFORE phase 1 started;
        3. the ordinary incremental logic, unchanged, which closes the window
           between that boundary and now — so a contact or call mutated while
           phase 1 was running cannot fall into a gap.

        On success the connection's watermarks are left exactly where an
        immediate `run_connection(connection)` continues from, and every write
        is keyed on provider identity, so the replay creates no duplicates.

        Completeness is verified, not assumed: see `_contact_enumeration_gap`.
        """
        connection.ensure_one()
        self._ensure_caller_state_durable()
        connection_id = connection.id
        # Validate every bound BEFORE any lock, audit row or remote call — an
        # unusable floor must not leave a half-run behind to interpret.
        call_floor = self._require_utc_bound(call_history_floor, "call_history_floor")
        contact_floor_dt = (
            self._require_utc_bound(contact_modified_floor, "contact_modified_floor")
            if contact_modified_floor is not None
            else call_floor
        )
        contact_floor = _iso_z(contact_floor_dt)

        lock_key = advisory_lock_key(connection_id)
        if not self._try_advisory_lock(lock_key):
            raise CrmSyncLockedError(f"CRM sync already running for connection {connection_id}")
        try:
            # Same I2 ordering as run_connection: the audit row is durable on an
            # owned cursor before the first fallible remote call, and it names
            # the operator's floors so the ledger shows this was the bootstrap.
            run_id = self._create_sync_run_durable(
                connection_id,
                {
                    "kind": "full_import",
                    "contact_scope_from_utc": contact_floor,
                    "call_scope_from_utc": _iso_z(call_floor),
                },
            )
            self.env.cr.commit()
            run = self.env["plasticos.crm.sync.run"].browse(run_id)
            try:
                adapter = self._build_adapter(connection)
                adapter.healthcheck()

                # Captured before enumeration: everything after this instant is
                # phase 3's responsibility, so a mutation racing the bootstrap
                # is covered by one phase or the other, never by neither.
                boundary = datetime.now(UTC)

                bootstrap_contacts = self._sync_contacts(
                    connection,
                    adapter,
                    run,
                    modified_after_override=contact_floor,
                )
                gap = self._contact_enumeration_gap(contact_floor_dt, boundary)
                # Capture before the catch-up pass resets it — this is the
                # bootstrap's evidence, and the only one that means anything.
                oldest_seen = self.oldest_contact_modified_seen

                bootstrap_calls = self._sync_calls(
                    connection,
                    adapter,
                    run,
                    start_override=call_floor,
                    end_override=boundary,
                )

                catchup_contacts = self._sync_contacts(
                    connection,
                    adapter,
                    run,
                    counter_base=bootstrap_contacts,
                    outcome_base=self._contact_outcomes,
                )
                catchup_end = datetime.now(UTC)
                catchup_calls = self._sync_calls(
                    connection,
                    adapter,
                    run,
                    start_override=boundary - CATCHUP_OVERLAP,
                    end_override=catchup_end,
                    counter_base=bootstrap_calls,
                    outcome_base=self._call_outcomes,
                )
                resolved = self._resolve_orphans(connection, adapter, run)
                status, excerpt = self._completion(run, [gap] if gap else [])

                run.write(
                    {
                        "status": status,
                        "finished_at": datetime.now(UTC).replace(tzinfo=None),
                        "contacts_upserted": bootstrap_contacts + catchup_contacts,
                        "calls_upserted": bootstrap_calls + catchup_calls,
                        "orphans_resolved": resolved,
                        "error_excerpt": excerpt,
                        "call_scope_to_utc": _iso_z(catchup_end),
                    }
                )
                connection_vals: dict[str, Any] = {"last_error": excerpt}
                if status == "success":
                    connection_vals["last_success_at"] = datetime.now(UTC).replace(tzinfo=None)
                connection.write(connection_vals)
                self.env.cr.commit()
                _logger.info(
                    "CRM full import connection=%s contacts=%s calls=%s status=%s "
                    "contact_floor=%s call_floor=%s boundary=%s oldest_contact_modified=%s",
                    connection_id,
                    bootstrap_contacts + catchup_contacts,
                    bootstrap_calls + catchup_calls,
                    status,
                    contact_floor,
                    _iso_z(call_floor),
                    _iso_z(boundary),
                    _iso_z(oldest_seen) if oldest_seen else "none",
                )
            except (CrmAdapterError, Exception) as exc:
                # I3 — identical ordering to run_connection: roll back this
                # transaction's rows before the failure cursor touches them.
                excerpt = _public_message(exc)
                _logger.exception("CRM full import failed connection=%s", connection_id)
                self.env.cr.rollback()
                self._persist_sync_failure_durable(connection_id, run_id, excerpt)
                raise
        finally:
            self._advisory_unlock(lock_key)
        return self.env["plasticos.crm.sync.run"].browse(run_id)

    @staticmethod
    def _require_utc_bound(value: Any, name: str) -> datetime:
        """Parse a required historical bound, or refuse to start.

        A full import that silently fell back to the rolling default would
        report success over a fraction of the history the operator asked for,
        which is worse than not running: the watermarks would then declare that
        history consumed.
        """
        if value is None or (isinstance(value, str) and not value.strip()):
            raise CrmFullImportArgumentError(
                f"{name} is required for a full import — pass an explicit ISO-8601 UTC "
                "instant (e.g. '2019-01-01T00:00:00Z'); there is no safe default"
            )
        parsed: datetime | None
        if isinstance(value, datetime):
            parsed = value if value.tzinfo else value.replace(tzinfo=UTC)
            parsed = parsed.astimezone(UTC)
        else:
            parsed = _parse_utc(str(value))
        if parsed is None:
            raise CrmFullImportArgumentError(f"{name} is not a parseable ISO-8601 datetime: {value!r}")
        if parsed > datetime.now(UTC):
            raise CrmFullImportArgumentError(f"{name} is in the future: {value!r}")
        return parsed

    def _contact_enumeration_gap(self, contact_floor: datetime, boundary: datetime) -> str | None:
        """Return why the contact census is unproven, or None when it is proven.

        The list endpoint documents a 31-day maximum on `modified_after`.
        The full import asks for an older floor anyway, because the two failure
        modes differ sharply:

        * the provider rejects the out-of-range bound — a `CrmAdapterError`,
          the run fails, no watermark moves, nothing is claimed;
        * the provider silently clamps it — the run "succeeds" over the last
          31 days while reporting a full census. That is the one outcome
          this method exists to prevent.

        Seeing at least one contact modified before the lookback horizon proves
        the older floor was served. Seeing none is genuinely ambiguous — the
        dataset may simply have no contact that old — so the run is reported
        `partial` with the ambiguity named, never `success`.
        """
        if contact_floor >= boundary - timedelta(days=CONTACT_LOOKBACK_MAX_DAYS):
            # Floor inside the documented lookback: nothing to prove.
            return None
        oldest = self.oldest_contact_modified_seen
        horizon = boundary - timedelta(days=CONTACT_LOOKBACK_MAX_DAYS)
        if oldest is not None and oldest < horizon:
            return None
        return (
            "Contact census unproven: requested modified_after "
            f"{_iso_z(contact_floor)}, which is older than the {CONTACT_LOOKBACK_MAX_DAYS}-day "
            f"Contacts lookback (horizon {_iso_z(horizon)}), and no returned contact was modified "
            f"before that horizon (oldest seen: {_iso_z(oldest) if oldest else 'none'}). "
            "The provider may have silently clamped the floor, so contacts untouched since "
            f"{_iso_z(horizon)} may be missing. Reconcile the imported lead count against "
            "VanillaSoft's own project contact count before treating this import as complete."
        )

    def _incremental_contact_scope(self, connection) -> tuple[str, str | None]:
        """Return ``(modified_after to request, watermark it was clamped from)``.

        The Contacts endpoint accepts ``modified_after`` only inside its rolling
        lookback, so a watermark older than that is clamped forward. The clamp
        is a scope limitation the run must name: every modification between
        the watermark and the clamped bound is never requested, and the
        watermark then moves past it. The second element is ``None`` when the
        connection held no watermark — a fresh connection asks for the default
        window and drops nothing it had ever acknowledged.
        """
        requested = connection.default_contact_modified_after()
        floor = datetime.now(UTC) - timedelta(days=INCREMENTAL_CONTACT_LOOKBACK_DAYS)
        parsed = _parse_utc(requested)
        if parsed and parsed < floor:
            return _iso_z(floor), (requested if connection.contact_watermark_utc else None)
        return requested, None

    @staticmethod
    def _incremental_call_start(connection, now: datetime) -> datetime:
        """Start of the rolling call window: the watermark, else the backfill
        floor, else seven days — the pre-existing defaults, in one place so the
        audit row and the sync pass cannot disagree about what was asked."""
        if connection.call_watermark_utc:
            return _parse_utc(connection.call_watermark_utc) or (now - timedelta(days=7))
        if connection.call_backfill_floor_utc:
            return _parse_utc(connection.call_backfill_floor_utc) or (now - timedelta(days=30))
        return now - timedelta(days=7)

    @staticmethod
    def _lookback_clamp_note(clamped_from: str, requested: str) -> str:
        return (
            f"Contact scope limited: the connection's contact watermark {clamped_from} is older than the "
            f"{INCREMENTAL_CONTACT_LOOKBACK_DAYS}-day Contacts lookback, so this run requested modified_after "
            f"{requested} instead. Contacts modified between {clamped_from} and {requested} were not requested "
            "from the provider and the watermark has moved past them. Run the full import "
            "(make import-vanillasoft with explicit floors) to reconcile that range."
        )

    def _completion(self, run, notes: list[str]) -> tuple[str, str | bool]:
        """Classify a run that finished without raising, from what it recorded.

        Mirrors ``import_summary.build_run_summary``. A per-record write
        failure is ``failed``. A required mapping that did not land, including
        a material error while the contact itself persisted, is ``partial``.
        An informational notice is also ``partial``, and its excerpt does not
        claim a required mapping failed. An identity conflict, a buffered
        orphan call, or a named scope limitation is ``partial``. Only a run
        with none of those is ``success``. Contact and call counters stay as
        recorded. ``last_success_at`` advances only for ``success``.
        """

        def count(name: str) -> int:
            return getattr(run, name, 0) or 0

        def line(row: dict) -> str:
            return f"  - {row.get('record_ref')}: {_public_message(row.get('message'))[:200]}"

        failed_contacts = count("contacts_failed")
        failed_calls = count("calls_failed")
        duplicates = count("contacts_duplicate_rejected")
        deferred = count("orphans_buffered")
        mapping_errors = required_mapping_errors(self.error_rows)
        notices = informational_notices(self.error_rows)
        lines = list(notes)
        if failed_contacts or failed_calls:
            lines.append(
                f"{failed_contacts} contact(s) and {failed_calls} call(s) failed to write; "
                "each failure is counted on this run, none was dropped."
            )
            for row in self.error_rows[:5]:
                lines.append(line(row))
        else:
            if mapping_errors:
                lines.append(
                    f"{len(mapping_errors)} required mapping(s) incomplete; "
                    "the contact and call counters are unchanged."
                )
                for row in mapping_errors[:5]:
                    lines.append(line(row))
            for row in notices[:5]:
                lines.append(line(row))
        if duplicates:
            lines.append(f"{duplicates} contact(s) rejected as identity conflicts (duplicate_rejected).")
        if deferred:
            lines.append(f"{deferred} call(s) buffered as orphans awaiting their lead; not landed yet.")
        if failed_contacts or failed_calls:
            status = "failed"
        elif lines:
            status = "partial"
        else:
            status = "success"
        excerpt = "\n".join(lines)[:2000]
        return status, (excerpt or False)

    def _try_advisory_lock(self, lock_key: str) -> bool:
        self.env.cr.execute("SELECT pg_try_advisory_lock(hashtext(%s))", [lock_key])
        row = self.env.cr.fetchone()
        return bool(row and row[0])

    def _advisory_unlock(self, lock_key: str) -> None:
        self.env.cr.execute("SELECT pg_advisory_unlock(hashtext(%s))", [lock_key])

    def _ensure_caller_state_durable(self) -> None:
        """Commit the caller's transaction before this object opens its own cursor.

        I17. Every durable row these entrypoints create lives on a cursor of its
        own (`_create_sync_run_durable`), and `plasticos_crm_sync_run` carries a
        foreign key to the connection. PostgreSQL cannot see a row the caller's
        transaction has not committed, so a connection created by the caller and
        handed straight in makes that INSERT fail the foreign key — the
        first-run Settings path, where the operator's very first sync creates
        the connection and syncs it in one RPC.

        `flush()` cannot substitute: it writes the INSERT inside the caller's
        transaction, where a second connection still cannot read it. Only a
        commit makes the row visible to a transaction this process does not own.
        `Cursor.commit()` flushes first, so the pending INSERT lands.

        The precondition belongs to the code that opens the independent cursor
        rather than to each caller, so both public entrypoints assert it here.
        Callers that reach this point have finished the work they wanted
        durable: the Settings action has already run `set_values()`, and the
        cron holds nothing pending.
        """
        self.env.cr.commit()

    def _create_sync_run_durable(self, connection_id: int, vals: dict[str, Any] | None = None) -> int:
        """Create the sync-run audit row on an owned cursor and commit it.

        Committing the ambient RPC cursor is unsafe (Odoo owns it), so the
        durable audit state gets its own transaction. ``vals`` carries the
        run's kind and requested scope, durable with the row itself so a run
        that fails before its first page still says what it asked for.
        Returns the primitive id.
        """
        from odoo import api

        with self.env.registry.cursor() as cr:
            env = api.Environment(cr, self.env.uid, dict(self.env.context))
            # Before this row exists: the caller holds the connection's session
            # advisory lock, so any row still `running` belongs to a process
            # that died without recording a completion (see the helper).
            self._close_interrupted_runs(env, connection_id)
            run = env["plasticos.crm.sync.run"].create(
                {
                    "connection_id": connection_id,
                    "status": "running",
                    "started_at": datetime.now(UTC).replace(tzinfo=None),
                    **(vals or {}),
                }
            )
            run_id = run.id
            cr.commit()
        return run_id

    @staticmethod
    def _close_interrupted_runs(env, connection_id: int) -> int:
        """Close this connection's ``running`` rows that nothing is running.

        A worker kill, an OOM or a deploy restart ends the process between the
        audit row's ``running`` and any completion write, and neither
        ``_persist_sync_failure_durable`` nor the success write ever runs. The
        row then reads as in progress forever, and nothing in the ledger says
        the remainder of its scope was never consumed.

        The connection's advisory lock is session-scoped and dies with the
        backend that held it, so the next run that holds it has proof that no
        other synchronization is in flight for this connection: every row still
        ``running`` here is interrupted. It is closed as ``failed`` — the
        existing status for a run that did not complete its scope — with the
        interruption named. Counters and watermarks are left exactly as the
        interrupted run committed them, which is why the next run resumes from
        the right place; this only makes the status say so.

        Called on the owned cursor that inserts the next audit row, before that
        insert, so the new ``running`` row is never caught by its own sweep.
        """
        Run = env["plasticos.crm.sync.run"]
        finished = datetime.now(UTC).replace(tzinfo=None)
        closed = 0
        for row in Run.search([("connection_id", "=", connection_id), ("status", "=", "running")]):
            row.write(
                {
                    "status": "failed",
                    "finished_at": finished,
                    "error_excerpt": (
                        "Interrupted: this run recorded no completion and no other synchronization holds "
                        "the connection lock, so its process ended before it finished. Counters show "
                        "committed work only; the unprocessed remainder of its scope was never acknowledged "
                        "and the next run resumes from the committed watermarks."
                    ),
                }
            )
            closed += 1
        if closed:
            _logger.warning("CRM sync closed %s interrupted run(s) connection=%s", closed, connection_id)
        return closed

    def _persist_sync_failure_durable(self, connection_id: int, run_id: int | None, excerpt: str) -> None:
        """Write failed run + last_error on a clean owned cursor.

        Must be called only after the failed transaction has been rolled back —
        otherwise this cursor blocks on rows transaction A still holds.

        Writes only the fields a failure changes. The counters are deliberately
        absent: `_sync_contacts`/`_sync_calls` already committed the true
        committed-work totals inside each page transaction, and the primitives
        available here describe the attempt, not what landed. Adding a counter
        to this dict would overwrite a correct durable value with a stale or
        zero one — the exact undercount this path is meant to preserve.
        """
        from odoo import api

        finished = datetime.now(UTC).replace(tzinfo=None)
        with self.env.registry.cursor() as cr:
            env = api.Environment(cr, self.env.uid, dict(self.env.context))
            if run_id:
                run = env["plasticos.crm.sync.run"].browse(run_id).exists()
                if run:
                    run.write(
                        {
                            "status": "failed",
                            "finished_at": finished,
                            "error_excerpt": excerpt,
                        }
                    )
            connection = env["plasticos.crm.connection"].browse(connection_id).exists()
            if connection:
                connection.write({"last_error": excerpt})
            cr.commit()

    def upsert_contact_external_id(self, connection, external_id: str) -> Any:
        """Single-contact path: contact + call history + custom tables."""
        self._load_approved_crosswalk()
        adapter = self._build_adapter(connection)
        try:
            lead_dto = adapter.get_contact(str(external_id))
        except CrmAdapterError as exc:
            # A source payload the parser refuses is a reported failure of
            # this ContactID, never a skipped or half-read contact.
            self.error_rows.append({"record_ref": str(external_id), "message": f"source contact refused: {exc}"})
            raise
        if not lead_dto:
            raise CrmAdapterError(f"Contact {external_id} not found")
        lead = self._upsert_lead(connection, lead_dto, adapter)
        calls_n = 0
        if self.last_lead_outcome in ADMITTED_OUTCOMES:
            if hasattr(adapter, "iter_calls_for_contact"):
                for batch in adapter.iter_calls_for_contact(str(external_id)):
                    calls_n += self._upsert_calls(connection, batch, None)
            self._sync_tables_for_lead(connection, adapter, lead_dto.external_id, lead)
        else:
            # Identity conflict or write failure: no dependent writes may hang
            # off an unadmitted lead (they would attach to an arbitrary match).
            _logger.warning(
                "Single-contact sync skipped dependent writes external_id=%s outcome=%s",
                external_id,
                self.last_lead_outcome,
            )
        self._resolve_orphans(connection, adapter, None)
        _logger.info(
            "Single-contact sync done external_id=%s lead_id=%s calls=%s",
            external_id,
            lead.id if lead else False,
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

    def _sync_contacts(
        self,
        connection,
        adapter,
        run,
        modified_after_override: str | None = None,
        counter_base: int = 0,
        outcome_base: dict[str, int] | None = None,
    ) -> int:
        if modified_after_override:
            # An explicit bound from the caller: the full import's operator
            # floor, which the rolling clamp must not silently shorten back to
            # 30 days, or `run_connection`'s already-clamped incremental bound,
            # which is also what its audit row recorded. In both cases
            # `oldest_contact_modified_seen` is what proves afterwards whether
            # the provider honoured it (see `run_full_import`).
            modified_after = modified_after_override
        else:
            modified_after, _clamped_from = self._incremental_contact_scope(connection)
        self.oldest_contact_modified_seen = None
        self._load_approved_crosswalk()

        # `committed` counts rows this method has durably landed; `pending`
        # counts rows written into the still-open transaction. The sync-run
        # counter must describe committed work, so it is written INTO the page
        # transaction (before its commit) and `committed` only advances once
        # that commit has returned. A later page's failure rolls back `pending`
        # and the ambient counter write with it, leaving the last committed
        # value on the row — which is the number that is actually true.
        committed = 0
        pending = 0
        committed_outcomes = _new_outcomes()
        last_batch_end = None
        for leads, batch_end, _partial in adapter.iter_contacts(
            modified_after=modified_after,
            limit=CONTACT_PAGE_SIZE,
        ):
            page_n = 0
            self.outcomes = _new_outcomes()
            for dto in leads:
                lead = self._upsert_lead(connection, dto, adapter)
                # Dependent table rows only after unambiguous admission: a
                # duplicate_rejected or failed contact gets no child writes.
                if self.last_lead_outcome in ADMITTED_OUTCOMES and not dto.deleted:
                    self._sync_tables_for_lead(connection, adapter, dto.external_id, lead)
                self._observe_contact_modified(dto)
                page_n += 1
            self.outcomes["seen"] = len(leads)
            pending += page_n
            if batch_end:
                last_batch_end = batch_end
                forward = _forward_only(connection.contact_watermark_utc, batch_end)
                if forward:
                    connection.contact_watermark_utc = forward
                if run:
                    run.contacts_upserted = counter_base + committed + pending
                    totals = _merge_outcomes(_merge_outcomes(_new_outcomes(), committed_outcomes), self.outcomes)
                    _write_contact_counters(run, totals["seen"], totals, base=outcome_base)
                self.env.cr.commit()  # records + watermark + counters, one page
                committed += pending
                pending = 0
                _merge_outcomes(committed_outcomes, self.outcomes)
                self.outcomes = _new_outcomes()
        totals = _merge_outcomes(_merge_outcomes(_new_outcomes(), committed_outcomes), self.outcomes)
        self.outcomes = None
        if last_batch_end:
            forward = _forward_only(connection.contact_watermark_utc, last_batch_end)
            if forward:
                connection.contact_watermark_utc = forward
        if run:
            # Any trailing `pending` is committed by run_connection's success
            # commit; on the failure path this write is rolled back with it.
            run.contacts_upserted = counter_base + committed + pending
            _write_contact_counters(run, totals["seen"], totals, base=outcome_base)
        self._contact_outcomes = totals
        return committed + pending

    def _observe_contact_modified(self, dto: CanonicalLead) -> None:
        """Track the oldest source `modified` timestamp this pass actually saw.

        A full import claims to have reached back to its floor. That claim is
        only evidence if some contact older than the list endpoint's own
        lookback came back — see `run_full_import`.
        """
        modified = _parse_utc(dto.modified_utc)
        if not modified:
            return
        current = self.oldest_contact_modified_seen
        if current is None or modified < current:
            self.oldest_contact_modified_seen = modified

    def _sync_calls(
        self,
        connection,
        adapter,
        run,
        start_override: datetime | None = None,
        end_override: datetime | None = None,
        counter_base: int = 0,
        outcome_base: dict[str, int] | None = None,
    ) -> int:
        now = datetime.now(UTC)
        end = end_override or now
        if start_override is not None:
            # An explicit, already-validated bound from the caller: the full
            # import's historical floor, or the incremental start the audit row
            # recorded. The short rolling defaults must not silently replace it.
            start = start_override
        else:
            start = self._incremental_call_start(connection, now)

        # Window size: 1 day chunks to keep batches manageable
        # Same committed-vs-attempted split as _sync_contacts: the counter is
        # written into the batch transaction, and `committed` advances only
        # after that commit returns.
        committed = 0
        committed_outcomes = _new_outcomes()
        cursor = start
        while cursor < end:
            window_end = min(cursor + timedelta(days=1), end)
            for batch in adapter.iter_calls(
                start=_iso_z(cursor),
                end=_iso_z(window_end),
                limit=CALL_BATCH_SIZE,
            ):
                self.outcomes = _new_outcomes()
                self.outcomes["seen"] = len(batch)
                batch_n = self._upsert_calls(connection, batch, run)
                if run:
                    run.calls_upserted = counter_base + committed + batch_n
                    totals = _merge_outcomes(_merge_outcomes(_new_outcomes(), committed_outcomes), self.outcomes)
                    _write_call_counters(run, totals["seen"], totals, base=outcome_base)
                self.env.cr.commit()  # batch commit
                committed += batch_n
                _merge_outcomes(committed_outcomes, self.outcomes)
                self.outcomes = _new_outcomes()
            forward = _forward_only(connection.call_watermark_utc, _iso_z(window_end))
            if forward:
                connection.call_watermark_utc = forward
            self.env.cr.commit()  # watermark advance
            cursor = window_end
        totals = _merge_outcomes(_merge_outcomes(_new_outcomes(), committed_outcomes), self.outcomes)
        self.outcomes = None
        if run:
            run.calls_upserted = counter_base + committed
            _write_call_counters(run, totals["seen"], totals, base=outcome_base)
        self._call_outcomes = totals
        return committed

    def _load_approved_crosswalk(self) -> None:
        """Read the pinned CSV before any approved identity write.

        An empty parameter uses the crosswalk shipped with this module. A
        parameter path replaces that file. A digest mismatch aborts before
        those writes.
        """
        if getattr(self, "_crosswalk_ready", False):
            return
        try:
            self._crosswalk = load_crosswalk_map(self.env)
        except CrosswalkError as exc:
            self._crosswalk = None
            self._crosswalk_ready = False
            raise CrmAdapterError(str(exc)) from exc
        self._crosswalk_ready = True

    def _approved_ct_id(self, external_id: str) -> str | None:
        mapping = getattr(self, "_crosswalk", None) or {}
        return mapping.get(str(external_id))

    def _find_person_ref(self, provider: str, external_id: str):
        ref = self.env["plasticos.crm.external.ref"].search(
            [
                ("provider", "=", provider),
                ("external_id", "=", external_id),
                ("res_model", "=", "res.partner"),
            ],
            limit=1,
        )
        if not ref or not getattr(ref, "id", False):
            return self.env["plasticos.crm.external.ref"].browse()
        return ref

    def _erp_person_for_ct(self, ct_id: str):
        marker = f"{XMLID_MODULE}.{xmlid_name(ct_id)}"
        imd = self.env["ir.model.data"].sudo()  # XMLID rows are system data the sync user must read
        rows = imd.search(
            [
                ("module", "=", XMLID_MODULE),
                ("name", "=", xmlid_name(ct_id)),
                ("model", "=", "res.partner"),
            ]
        )
        if not rows:
            return None, (
                f"ERP marker {marker} resolved 0 rows: the approved ERP person was not imported "
                "(missing from the ERP import or excluded as an inactive contact); no lead or partner was created"
            )
        if len(rows) != 1:
            return None, f"ERP marker {marker} resolved {len(rows)} rows"
        partner = (
            self.env["res.partner"].sudo().with_context(active_test=False).browse(rows.res_id).exists()
        )  # archived ERP people are hidden by the default active test
        if len(partner) != 1:
            return None, f"ERP marker {marker} does not point at one partner"
        if partner.is_company:
            return None, f"ERP marker {marker} points at a company"
        return partner, ""

    def _add_approved_phones(self, partner, dto: CanonicalLead) -> bool:
        """Add missing CRM numbers as phone lines. Never assign phone or mobile.

        Each enabled source line keeps its classification (mobile, fax or
        other); a second distinct mobile is a mobile line too. ERP and CRM
        lines are compared on classification plus the normalized number,
        extension included: a formatting variant of a line already on the
        person adds nothing, while another extension or the same number as a
        fax is its own line. The ERP ``phone`` counts as an ``other`` line.
        """
        Phone = self.env["plasticos.partner.phone"].sudo()  # cron user has no facility-phone ACL; lines are additive
        present = {_phone_line("other", partner.phone), _phone_line("mobile", getattr(partner, "mobile", ""))}
        for line in partner.phone_line_ids:
            present.add(_phone_line(line.label, line.number))
        wrote = False
        for _label, kind, number in _source_phones(dto):
            line = _phone_line(kind, number)
            if not line[1] or line in present:
                continue
            Phone.create({"partner_id": partner.id, "label": kind, "number": number})
            present.add(line)
            wrote = True
        return wrote

    def _bind_approved_contact(self, dto: CanonicalLead, ct_id: str):
        """Bind one approved ContactID onto the existing ERP person. No new lead.

        The CRM note, then each contact-context field the payload carries
        (labelled with this ContactID), is appended to the person's ``comment``
        after the ERP notes, once. No call or activity is created from them.
        """
        outcomes = getattr(self, "outcomes", None)
        Lead = self.env[CRM_LEAD]
        partner, reason = self._erp_person_for_ct(ct_id)
        if partner is None:
            self._record_outcome(outcomes, "failed", dto.external_id, reason)
            self.last_lead_outcome = "failed"
            return Lead.browse()
        Ref = self.env["plasticos.crm.external.ref"]
        lead = self._find_lead(dto.provider, dto.external_id, Ref)
        matches = Lead.with_context(active_test=False).search([("vanillasoft_id", "=", dto.external_id)])
        if len(matches) > 1:
            self._record_outcome(outcomes, "duplicate_rejected", dto.external_id, "multiple leads carry the source id")
            self.last_lead_outcome = "duplicate_rejected"
            return lead
        if lead and lead.partner_id and lead.partner_id.id not in (False, partner.id):
            self._record_outcome(
                outcomes, "duplicate_rejected", dto.external_id, "lead partner_id is a different partner"
            )
            self.last_lead_outcome = "duplicate_rejected"
            return lead
        person_ref = self._find_person_ref(dto.provider, dto.external_id)
        if person_ref and person_ref.res_id not in (False, partner.id):
            self._record_outcome(
                outcomes, "duplicate_rejected", dto.external_id, "person external ref points at a different partner"
            )
            self.last_lead_outcome = "duplicate_rejected"
            return lead
        wrote = False
        try:
            with self.env.cr.savepoint():
                if not person_ref:
                    Ref.create(
                        {
                            "provider": dto.provider,
                            "external_id": dto.external_id,
                            "res_model": "res.partner",
                            "res_id": partner.id,
                            "lead_id": False,
                        }
                    )
                    wrote = True
                elif person_ref.lead_id:
                    person_ref.write({"lead_id": False})
                    wrote = True
                if lead and not lead.partner_id:
                    lead.write({"partner_id": partner.id})
                    wrote = True
                if lead and dto.deleted:
                    lead.write({"active": False, "vanillasoft_sync_archived": True})
                    wrote = True
                elif lead and getattr(lead, "vanillasoft_sync_archived", False) and not dto.deleted:
                    lead.write({"active": True, "vanillasoft_sync_archived": False})
                    wrote = True
                note_lines: list[str] = []
                _queue_provenance(
                    note_lines, partner.comment, dto.external_id, "Notes", dto.contact_note, shared_owner=True
                )
                comment = _description_with(
                    partner.comment, [*note_lines, *_approved_context_lines(dto, partner.comment)]
                )
                if comment is not None:
                    partner.write({"comment": comment})
                    wrote = True
                if not dto.deleted and self._add_approved_phones(partner, dto):
                    wrote = True
        except Exception as exc:  # noqa: BLE001 - per-record failure is recorded, never silent loss
            self._record_outcome(outcomes, "failed", dto.external_id, str(exc))
            self.last_lead_outcome = "failed"
            return Lead.browse() if not lead else lead
        outcome = "updated" if wrote else "unchanged"
        if outcomes is not None:
            outcomes[outcome] += 1
        self.last_lead_outcome = outcome
        if outcome in ADMITTED_OUTCOMES and not dto.deleted:
            if lead:
                self._apply_approved_materials(lead, dto.custom_fields)
                self._bind_opportunity_material(lead)
            elif "plasticos.material.profile" in self.env:
                self._apply_person_materials(partner, dto)
            if self._env_has_model("crm.tag"):
                self._apply_crm_classification(lead, dto, partner=partner)
        return lead or Lead.browse()

    def _keep_person_binding(self, dto: CanonicalLead, person_ref):
        """Honor an earlier approved bind when the crosswalk is not loaded.

        The persisted person ref is the approval record. Without the crosswalk
        nothing is enriched, and the legacy path must not mint a second lead or
        lead ref for the same source id. Conflicts are reported, never repaired.
        """
        outcomes = getattr(self, "outcomes", None)
        Lead = self.env[CRM_LEAD]
        partner = (
            self.env["res.partner"].sudo().with_context(active_test=False).browse(person_ref.res_id).exists()
        )  # archived ERP people keep their binding
        if not partner:
            self._record_outcome(outcomes, "failed", dto.external_id, "person external ref points at a missing partner")
            self.last_lead_outcome = "failed"
            return Lead.browse()
        lead = self._find_lead(dto.provider, dto.external_id, self.env["plasticos.crm.external.ref"])
        matches = Lead.with_context(active_test=False).search([("vanillasoft_id", "=", dto.external_id)])
        if len(matches) > 1:
            self._record_outcome(outcomes, "duplicate_rejected", dto.external_id, "multiple leads carry the source id")
            self.last_lead_outcome = "duplicate_rejected"
            return lead
        if lead and lead.partner_id and lead.partner_id.id not in (False, partner.id):
            self._record_outcome(
                outcomes, "duplicate_rejected", dto.external_id, "lead partner_id is a different partner"
            )
            self.last_lead_outcome = "duplicate_rejected"
            return lead
        if outcomes is not None:
            outcomes["unchanged"] += 1
        self.last_lead_outcome = "unchanged"
        return lead or Lead.browse()

    def _apply_approved_materials(self, lead, *field_maps) -> None:
        """Attach material text only when one facility profile already exists.

        Same containment as ``_apply_contact_materials``: a material failure
        rolls back its own writes and is reported. The admitted identity, the
        page commit and the watermark are not affected.
        """
        try:
            with self.env.cr.savepoint():
                self._apply_resolved_approved_materials(lead, *field_maps)
        except Exception as exc:  # noqa: BLE001 - material failure must not drop the admitted contact
            _logger.warning("Approved material normalization failed for lead %s: %s", lead.id, exc)
            self._append_classified_error(
                lead.vanillasoft_id or str(lead.id or ""),
                f"material normalization failed: {exc}",
                REQUIRED_MAPPING,
            )

    def _apply_resolved_approved_materials(self, lead, *field_maps) -> None:
        sections = _parse_material_sections(*field_maps)
        if not sections or not lead.partner_id:
            return
        if _notes_only_sections(*field_maps):
            partner, _reason = _facility_for_material(lead)
            located = (
                self.env["plasticos.facility.profile"].search([("partner_id", "=", partner.id)])
                if partner is not None
                else self.env["plasticos.facility.profile"].browse()
            )
            if partner is None or len(located) != 1:
                if sections.get("pps", {}).get("notes"):
                    self._append_classified_error(
                        lead.vanillasoft_id or str(lead.id), "BLOCKED_PPS_PROFILE_IDENTITY", REQUIRED_MAPPING
                    )
                return
        phrases = _dedupe_phrases(phrase for section in sections.values() for phrase in section["phrases"])
        detail = ", ".join(phrases) or "material evidence"
        partner, reason = _facility_for_material(lead)
        if partner is None and lead.partner_id.parent_id:
            partner = lead.partner_id
        if partner is None:
            self._append_classified_error(
                lead.vanillasoft_id or str(lead.id),
                f"{reason}: {detail}",
                REQUIRED_MAPPING,
            )
            return
        profiles = self.env["plasticos.facility.profile"].search([("partner_id", "=", partner.id)])
        self._import_section_materials(
            lead, field_maps, partner=partner, facility_profile=profiles if len(profiles) == 1 else None
        )

    def _upsert_lead(self, connection, dto: CanonicalLead, adapter=None):
        """Identity-resolved lead upsert with deterministic classification.

        Returns the lead recordset (pinned contract for direct callers). When
        the caller opened an outcome accumulator (``self.outcomes``), this
        record is classified exactly one of
        ``created | updated | unchanged | duplicate_rejected | failed`` there:

        * ``unchanged`` — the normalized values already match; nothing written.
        * ``duplicate_rejected`` — the Odoo side holds conflicting identities
          for one source id (an external ref pointing at a different lead than
          the ``vanillasoft_id`` fallback finds, or several fallback matches).
          Refusing is the only honest choice: writing either would silently
          repoint identity, and creating would duplicate.
        * ``failed`` — the lead write or the external-reference write raised.
          Both run in one savepoint, so a failure leaves no partial identity.
          The record is reported, never silently dropped, and a later replay
          is not what repairs it.

        The classification is also left in ``self.last_lead_outcome`` so a
        caller can tell an admitted lead from a rejected one: the returned
        recordset alone cannot, because a rejected identity still returns the
        (ambiguous) match it found.
        """
        outcomes = getattr(self, "outcomes", None)
        self.last_lead_outcome = None
        ct_id = self._approved_ct_id(dto.external_id)
        if ct_id:
            return self._bind_approved_contact(dto, ct_id)
        person_ref = self._find_person_ref(dto.provider, dto.external_id)
        if person_ref:
            return self._keep_person_binding(dto, person_ref)
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
        # `active_test=False`: a lead this sync archived for a provider deletion
        # is invisible to a default search, so the fallback would miss it and
        # create a duplicate the moment VanillaSoft restored the contact.
        if not lead:
            lead = Lead.with_context(active_test=False).search(
                [("vanillasoft_id", "=", dto.external_id)],
                limit=1,
            )
            # Identity-conflict detection: more than one lead carrying the same
            # source id is a duplicate to refuse, never to guess between.
            matches = Lead.with_context(active_test=False).search(
                [("vanillasoft_id", "=", dto.external_id)],
            )
            if len(matches) > 1:
                self._record_outcome(
                    outcomes, "duplicate_rejected", dto.external_id, "multiple leads carry the source id"
                )
                self.last_lead_outcome = "duplicate_rejected"
                return lead
        if ref and ref.res_id and lead.id != ref.res_id:
            self._record_outcome(outcomes, "duplicate_rejected", dto.external_id, "external ref and fallback disagree")
            self.last_lead_outcome = "duplicate_rejected"
            return lead

        prior_lead_id = lead.id if lead else False
        try:
            vals = self._lead_vals_from_dto(dto)
            self._guard_unapproved_stage(dto, lead, vals)
            # Source data with no native lead field is appended to the
            # description once; a replay finds every paragraph and adds nothing.
            current = getattr(lead, "description", False) if lead else False
            description = _description_with(current, self._lead_evidence(dto, vals, current))
            if description is not None:
                vals["description"] = description
            # Archival provenance, not a mirror of the provider flag. `active` is
            # shared state: Odoo users archive leads for their own reasons, and
            # `deleted=false` is the provider's steady state for every live contact,
            # so mirroring it would silently reopen every lead a user ever archived.
            # Reactivation is therefore conditional on THIS sync having been the one
            # that archived the lead.
            if dto.deleted:
                vals["active"] = False
                vals["vanillasoft_sync_archived"] = True
            elif lead and lead.vanillasoft_sync_archived:
                vals["active"] = True
                vals["vanillasoft_sync_archived"] = False

            with self.env.cr.savepoint():
                if lead:
                    changed = {k: v for k, v in vals.items() if _differs(lead, k, v)}
                    if changed:
                        lead.write(changed)
                        outcome = "updated"
                    else:
                        outcome = "unchanged"
                else:
                    lead = Lead.create(vals)
                    outcome = "created"
                if outcome in ADMITTED_OUTCOMES:
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
                    elif ref.res_id != lead.id or (getattr(ref.lead_id, "id", ref.lead_id) or False) != lead.id:
                        ref.write({"res_id": lead.id, "lead_id": lead.id})
        except Exception as exc:  # noqa: BLE001 - per-record failure is recorded, never silent loss
            if outcomes is not None:
                outcomes["failed"] += 1
            self.error_rows.append(
                {"record_ref": dto.external_id, "error_type": type(exc).__name__, "message": str(exc)}
            )
            self.last_lead_outcome = "failed"
            return Lead.browse(prior_lead_id) if prior_lead_id else Lead.browse()

        if outcomes is not None:
            outcomes[outcome] += 1
        self.last_lead_outcome = outcome
        if outcome in ADMITTED_OUTCOMES and not dto.deleted:
            self._apply_contact_materials(lead, dto.custom_fields)
            self._bind_opportunity_material(lead)
            if self._env_has_model("crm.tag"):
                self._apply_crm_classification(lead, dto)
        return lead

    def _bind_opportunity_material(self, lead) -> None:
        """VanillaSoft ingress converges on the native Opportunity root.

        When the lead already has a verified partner that owns exactly one
        material profile, that profile is bound so the broker can approve a lot
        and run the one Opportunity matching command. Nothing is created: no
        intake, no facility, no partner. A failure is reported and the admitted
        contact, the page commit and the watermark are not affected.
        """
        bind = getattr(lead, "_plasticos_bind_opportunity_material", None)
        if not callable(bind):
            return
        try:
            with self.env.cr.savepoint():
                bind()
        except Exception as exc:  # noqa: BLE001 - lineage binding must not drop the admitted contact
            _logger.warning("Opportunity material binding failed for lead %s: %s", getattr(lead, "id", "?"), exc)
            self._append_classified_error(
                getattr(lead, "vanillasoft_id", None) or str(getattr(lead, "id", "")),
                f"opportunity material binding failed: {exc}",
                REQUIRED_MAPPING,
            )

    def _env_has_model(self, model_name: str) -> bool:
        """True when the model is installed. A pure-Python fake env raises KeyError."""
        try:
            self.env[model_name]
        except KeyError:
            return False
        return True

    def _append_classified_error(self, record_ref: str, message: str, category: str) -> None:
        """Record one typed row. Status reads ``category``, never the message text."""
        self.error_rows.append({"record_ref": record_ref, "message": message, "category": category})

    def _record_outcome(self, outcomes: dict[str, int] | None, outcome: str, record_ref: str, message: str) -> None:
        """Record a classified outcome + error detail (duplicate/failed rows).

        The reason is kept even when no counter accumulator is open (the
        single-contact path), so a classified failure is never unexplained.
        """
        if outcomes is not None:
            outcomes[outcome] += 1
        self.error_rows.append({"record_ref": record_ref, "message": message})

    def _resolve_country_id(self, raw: str | None) -> int | bool:
        """Resolve a country by exact alias, ISO code, or exact name.

        ``USA`` is the United States. It is not a prefix of USA Minor Outlying
        Islands, and a two-letter code is never taken from the start of a longer
        name.
        """
        text = (raw or "").strip()
        if not text:
            return False
        token = _country_token(text)
        Country = self.env["res.country"]
        if token in _US_COUNTRY_ALIASES:
            country = Country.search([("code", "=", "US")], limit=1)
            return country.id if country else False
        if len(token) == 2 and token.isalpha():
            country = Country.search([("code", "=", token.upper())], limit=1)
            return country.id if country else False
        country = Country.search([("name", "=ilike", _collapse_ws(text))], limit=1)
        return country.id if country else False

    def backfill_owners(self, owner_by_external_id: dict[str, str]) -> dict[str, int]:
        """Assign ``crm.lead.user_id`` from the locked owner map.

        A missing lead is counted and skipped. An owner that does not resolve
        to exactly one eligible user is counted as failed and does not clear
        a salesperson already on the lead.
        """
        counts = {"seen": 0, "updated": 0, "unchanged": 0, "missing": 0, "failed": 0}
        leads = self.env[CRM_LEAD].with_context(active_test=False)
        for external_id, owner_raw in owner_by_external_id.items():
            counts["seen"] += 1
            lead = leads.search([("vanillasoft_id", "=", str(external_id))], limit=1)
            if not lead:
                counts["missing"] += 1
                continue
            try:
                user = resolve_salesperson(self.env, owner_raw)
            except OwnerResolutionError as exc:
                counts["failed"] += 1
                self.error_rows.append({"record_ref": str(external_id), "message": str(exc)})
                continue
            if lead.user_id.id == user.id:
                counts["unchanged"] += 1
                continue
            lead.write({"user_id": user.id})
            counts["updated"] += 1
        return counts

    def _lead_vals_from_dto(self, dto: CanonicalLead) -> dict[str, Any]:
        # Lazy import mapping SSOT from crm_bridge
        from odoo.addons.plasticos_crm_bridge.models.crm_mapping import STAGE_MAPPING

        contact_name = " ".join(part for part in (_collapse_ws(dto.first_name), _collapse_ws(dto.last_name)) if part)
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

        # The canonical resolver: a mapped source, else the seeded ``Other``.
        source = self.env["plasticos.lead.source.utils"].normalize_raw_source((dto.lead_source_raw or "").strip())
        source_id = source.id if source else False

        country_id = self._resolve_country_id(dto.country_code)

        # A supported code, else the exact state name, within the resolved
        # country only. No country is ever inferred from a state value.
        state_id = False
        state_text = _collapse_ws(dto.state_code)
        if state_text and country_id:
            State = self.env["res.country.state"]
            state = State.search([("code", "=", state_text.upper()), ("country_id", "=", country_id)], limit=1)
            if not state:
                state = State.search([("name", "=ilike", state_text), ("country_id", "=", country_id)], limit=1)
            state_id = state.id if state else False

        user_id = resolve_salesperson(self.env, dto.owner_name).id

        return {
            "name": name,
            "type": "lead",
            "partner_name": company or False,
            "contact_name": contact_name or False,
            "email_from": dto.email or False,
            "phone": dto.phone or False,
            # crm.lead.mobile accepts a 10-digit US number only: the primary
            # mobile when it qualifies, else another source mobile that does.
            # Every mobile not stored here stays, labelled, in the description.
            "mobile": _lead_mobile(dto),
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

    def _lead_evidence(self, dto: CanonicalLead, vals: dict[str, Any], current=None) -> list[str]:
        """Source-labelled paragraphs for data the lead has no native field for.

        ``Notes``, the call summaries and the contact-level section notes name
        the ContactID. Company-classification context stays on its existing
        label. Every enabled number not stored in ``phone``/``mobile``, and a
        country, state or lead source that did not resolve, is kept too. Each
        unresolved value is also reported on ``error_rows``; nothing is guessed.
        """
        ref = dto.external_id
        custom = dto.custom_fields or {}
        lines: list[str] = []
        _queue_provenance(lines, current, ref, "Notes", dto.contact_note)
        for name in (*LEAD_CONTEXT_FIELDS, *CONTACT_SECTION_NOTE_FIELDS):
            if is_excluded_source_field(name):
                continue
            value = _collapse_ws(custom.get(name))
            if not value:
                continue
            if name in CONTACT_PROVENANCE_FIELDS:
                _queue_provenance(lines, current, ref, name, value)
            else:
                lines.append(f"VanillaSoft {name}: {value}")
        stored = {_phone_line("other", vals.get("phone")), _phone_line("mobile", vals.get("mobile"))}
        for label, kind, number in _source_phones(dto):
            if _phone_line(kind, number) not in stored:
                lines.append(f"VanillaSoft phone ({label}): {number}")
        if dto.mobile and "mobile" in vals and not _us_mobile(dto.mobile):
            self._append_classified_error(
                ref,
                "primary mobile is not a 10-digit US number; kept in the lead description",
                OPTIONAL_CONTEXT,
            )
        country = _collapse_ws(dto.country_code)
        if country and "country_id" in vals and not vals["country_id"]:
            lines.append(f"VanillaSoft Country (unresolved): {country}")
            self._append_classified_error(
                ref,
                "country did not resolve; kept in the description",
                OPTIONAL_CONTEXT,
            )
        state = _collapse_ws(dto.state_code)
        if state and "state_id" in vals and not vals["state_id"]:
            lines.append(f"VanillaSoft State (unresolved): {state}")
            self._append_classified_error(
                ref,
                "state did not resolve in the country; kept in the description",
                OPTIONAL_CONTEXT,
            )
        raw_source = (dto.lead_source_raw or "").strip()
        if raw_source and "source_id" in vals and self._lead_source_is_fallback(raw_source):
            lines.append(f"VanillaSoft Lead Source: {raw_source}")
        status = _collapse_ws(dto.lead_status_raw)
        if status:
            _queue_provenance(lines, current, ref, "Lead Status", status)
        # Issue #299: Website and Title have no approved native destination yet,
        # so they are preserved as ContactID-labelled source text, never mapped.
        _queue_provenance(lines, current, ref, "Website", dto.website)
        _queue_provenance(lines, current, ref, "Title", dto.job_title)
        return lines

    def _lead_source_is_fallback(self, raw_source: str) -> bool:
        """True when the resolver maps ``raw_source`` to ``Other`` only because it is unknown."""
        from odoo.addons.plasticos_facility_profile.models.lead_source import LEAD_SOURCE_MAPPING

        return raw_source not in LEAD_SOURCE_MAPPING

    def _upsert_calls(self, connection, batch: list[CanonicalCall], run) -> int:
        """Upsert one call batch, classifying each row created|updated|unchanged|failed.

        Returns created+updated (the pinned counter contract). Classification
        is recorded into ``self.outcomes`` when the caller opened one.
        """
        outcomes = getattr(self, "outcomes", None)
        Call = self.env["plasticos.crm.call.event"]
        Orphan = self.env["plasticos.crm.sync.orphan"]
        Ref = self.env["plasticos.crm.external.ref"]
        created = 0
        updated = 0
        orphans = 0
        for dto in batch:
            existing = Call.search(
                [("provider", "=", dto.provider), ("external_id", "=", dto.external_id)],
                limit=1,
            )
            lead = self._find_lead(dto.provider, dto.contact_external_id, Ref)
            person_ref = self._find_person_ref(dto.provider, dto.contact_external_id)
            lead_id, partner_id = self._history_links(person_ref, lead)
            vals = {
                "provider": dto.provider,
                "external_id": dto.external_id,
                "contact_external_id": dto.contact_external_id,
                "call_datetime_utc": _dt_naive_utc(dto.call_datetime_utc),
                "duration_seconds": dto.duration_seconds,
                "user_name": dto.user_name or False,
                "result_code": dto.result_code or False,
                "comment": dto.comment or False,
                "lead_id": lead_id,
                "partner_id": partner_id,
            }
            try:
                if existing:
                    changed = {k: v for k, v in vals.items() if _differs(existing, k, v)}
                    if changed:
                        existing.write(changed)
                        updated += 1
                        if outcomes is not None:
                            outcomes["updated"] += 1
                    elif outcomes is not None:
                        outcomes["unchanged"] += 1
                elif not lead and not person_ref:
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
                    # Deferred: the orphan buffer is the no-loss mechanism,
                    # `orphans_buffered` persists the count, and the row is
                    # classified here so seen == sum(outcomes) holds. It is
                    # not created/updated/unchanged: nothing landed yet.
                    if outcomes is not None:
                        outcomes["deferred"] = outcomes.get("deferred", 0) + 1
                else:
                    Call.create(vals)
                    created += 1
                    if outcomes is not None:
                        outcomes["created"] += 1
            except Exception as exc:  # noqa: BLE001 - per-record failure is recorded, never silent loss
                self._record_outcome(outcomes, "failed", dto.external_id, str(exc))
        if run and orphans:
            run.orphans_buffered = (run.orphans_buffered or 0) + orphans
        return created + updated

    def _sync_tables_for_lead(self, connection, adapter, contact_external_id: str, lead=None):
        Ref = self.env["plasticos.crm.external.ref"]
        Row = self.env["plasticos.crm.external.table.row"]
        Orphan = self.env["plasticos.crm.sync.orphan"]
        outcomes = getattr(self, "outcomes", None)
        if lead is None:
            lead = self._find_lead(connection.provider, contact_external_id, Ref)
        person_ref = self._find_person_ref(connection.provider, contact_external_id)
        landed_fields = []
        for dto in adapter.iter_table_rows(contact_external_id):
            if not lead and not person_ref:
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
                            "fields": omit_excluded_source_fields(dto.fields),
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
            lead_id, partner_id = self._history_links(person_ref, lead)
            vals = {
                "provider": dto.provider,
                "lead_id": lead_id,
                "partner_id": partner_id,
                "contact_external_id": dto.contact_external_id,
                "table_id": dto.table_id,
                "table_name": dto.table_name or False,
                "external_row_id": dto.external_row_id,
                "fields_json": omit_excluded_source_fields(dto.fields),
            }
            if existing:
                changed = {k: v for k, v in vals.items() if _differs(existing, k, v)}
                if changed:
                    existing.write(changed)
                    if outcomes is not None:
                        outcomes["table_rows"] += 1
            else:
                Row.create(vals)
                if outcomes is not None:
                    outcomes["table_rows"] += 1
            landed_fields.append(omit_excluded_source_fields(dto.fields))
        if lead and landed_fields:
            if person_ref or self._approved_ct_id(contact_external_id):
                self._apply_approved_materials(lead, *landed_fields)
            else:
                self._apply_contact_materials(lead, *landed_fields)

    def _apply_contact_materials(self, lead, *field_maps) -> None:
        """Normalize each distinct material onto the lead's facility profile.

        A lead with no partner owns one facility profile and the material
        profiles on it. A lead that already has one resolvable facility partner
        keeps the partner-owned profiles. Manual sync and the scheduled cron
        both reach this through ``run_connection``. An unresolved material is
        reported and the contact is kept. Sync counters and watermarks are not
        changed.
        """
        try:
            with self.env.cr.savepoint():
                self._apply_resolved_materials(lead, *field_maps)
        except Exception as exc:  # noqa: BLE001 - material failure must not drop the admitted contact
            _logger.warning("Material normalization failed for lead %s: %s", lead.id, exc)
            self._append_classified_error(
                str(lead.id or ""),
                f"material normalization failed: {exc}",
                REQUIRED_MAPPING,
            )

    def _apply_resolved_materials(self, lead, *field_maps) -> None:
        if not _parse_material_sections(*field_maps):
            return
        if _notes_only_sections(*field_maps) and not lead.partner_id:
            owned = self.env["plasticos.facility.profile"].search([("crm_lead_id", "=", lead.id)], limit=1)
            if not owned:
                if _parse_material_sections(*field_maps).get("pps", {}).get("notes"):
                    self._append_classified_error(
                        lead.vanillasoft_id or str(lead.id), "BLOCKED_PPS_PROFILE_IDENTITY", REQUIRED_MAPPING
                    )
                return
        from odoo.exceptions import ValidationError  # noqa: PLC0415

        partner = None
        if lead.partner_id:
            partner, reason = _facility_for_material(lead)
            if partner is None:
                self._append_classified_error(
                    lead.vanillasoft_id or str(lead.id),
                    reason,
                    REQUIRED_MAPPING,
                )
                return
        owned = self.env["plasticos.facility.profile"].search([("crm_lead_id", "=", lead.id)], limit=1)
        if not owned and lead.facility_profile_id and lead.facility_profile_id.partner_id == partner:
            owned = lead.facility_profile_id
        if partner is not None and not owned:
            located = self.env["plasticos.facility.profile"].ensure_canonical_facility(partner, lead)
            self._import_section_materials(lead, field_maps, partner=partner, facility_profile=located)
            return
        if owned and partner is not None and owned.partner_id and owned.partner_id != partner:
            raise ValidationError("This lead is already associated with a different facility.")
        if owned and partner is not None and not owned.partner_id:
            owned = owned.link_verified_location(partner)
        elif not owned:
            owned = self.env["plasticos.facility.profile"].create({"crm_lead_id": lead.id})
        owned._remember_lead(lead)
        self._import_section_materials(lead, field_maps, partner=partner, facility_profile=owned)

    def _material_ref(self, lead, external_id=None) -> str:
        if external_id:
            return str(external_id)
        if lead and getattr(lead, "id", False):
            return str(lead.vanillasoft_id or lead.id)
        return ""

    def _profiles_for_material(self, partner, facility_profile):
        Profile = self.env["plasticos.material.profile"]
        if partner is not None:
            return Profile.search([("partner_id", "=", partner.id)])
        if facility_profile is not None and getattr(facility_profile, "id", False):
            return Profile.search([("facility_profile_id", "=", facility_profile.id)])
        return Profile.browse()

    def _resolve_material(self, phrase, structured=None):
        from odoo.addons.plasticos_material_profile.models.material_normalizer import (  # noqa: PLC0415
            normalize_material,
        )

        combined = normalize_material(self.env, phrase, structured=structured, crm_aliases=True)
        if "conflicting material evidence" in combined.unresolved:
            return combined, "conflict"
        hint = structured.get("type") if isinstance(structured, dict) else None
        if hint:
            hint_result = normalize_material(self.env, hint)
            if "unresolved material" in hint_result.unresolved:
                return combined, _HINT_STATUS_UNSUPPORTED
        return combined, None

    def _store_normalized_materials(
        self, lead, texts, partner=None, facility_profile=None, structured=None, external_id=None
    ) -> None:
        from odoo.exceptions import ValidationError  # noqa: PLC0415

        profiles = self.env["plasticos.material.profile"]
        ref = self._material_ref(lead, external_id)
        use_structured = structured if structured and len(texts) == 1 else None
        from odoo.addons.plasticos_material_profile.models.material_normalizer import (  # noqa: PLC0415
            is_not_material,
        )

        for text in texts:
            if is_not_material(text):
                # The mapping sheet records this text as a call note or not a material.
                continue
            normalized, hint_status = self._resolve_material(text, use_structured)
            if hint_status == "conflict" or "conflicting material evidence" in normalized.unresolved:
                self._append_classified_error(ref, f"conflicting material evidence: {text}", REQUIRED_MAPPING)
                continue
            if hint_status == _HINT_STATUS_UNSUPPORTED:
                self._append_classified_error(
                    ref, f"BLOCKED_UNRESOLVED: unsupported type hint for {text}", OPTIONAL_CONTEXT
                )
            if normalized.unresolved or not normalized.polymer:
                detail = ", ".join(normalized.unresolved) or "unresolved material"
                self._append_classified_error(
                    ref,
                    f"{detail}: {normalized.source_description}",
                    REQUIRED_MAPPING,
                )
                continue
            if facility_profile is not None and getattr(facility_profile, "id", False):
                profile = profiles.reuse_lead_facility_material(
                    facility_profile,
                    normalized.polymer,
                    normalized.form,
                    note_line=normalized.source_description,
                    grades=normalized.material_grade,
                )
            elif partner is not None:
                profile = profiles.reuse_facility_polymer_profile(
                    partner,
                    normalized.polymer,
                    normalized.form,
                    note_line=normalized.source_description,
                    grades=normalized.material_grade,
                )
            else:
                raise ValidationError("A facility profile is required.")
            self._write_profile_classification(profile, normalized)

    def _import_section_materials(
        self, lead, field_maps, partner=None, facility_profile=None, external_id=None
    ) -> None:
        """Store section phrases without broadcasting another section's type or form."""
        sections = _parse_material_sections(*field_maps)
        if not sections:
            return
        ref = self._material_ref(lead, external_id)
        existing = self._profiles_for_material(partner, facility_profile)
        distinguished_ids = set(existing.filtered(_preexisting_supersac_profile).ids)
        for _section, slot in sections.items():
            phrases = list(slot["phrases"])
            hints = list(slot["hints"])
            structured = {"type": hints[0]} if len(phrases) == 1 and len(hints) == 1 else None
            if hints and structured is None:
                detail = ", ".join(hints)
                message = (
                    f"BLOCKED_UNRESOLVED: {detail}"
                    if not phrases
                    else "BLOCKED_UNRESOLVED: type hint is not contact-unique"
                )
                category = REQUIRED_MAPPING if not phrases else OPTIONAL_CONTEXT
                self._append_classified_error(ref, message, category)
            if phrases:
                self._store_normalized_materials(
                    lead,
                    phrases,
                    partner=partner,
                    facility_profile=facility_profile,
                    structured=structured,
                    external_id=ref,
                )
        profiles = self._profiles_for_material(partner, facility_profile)
        for section, slot in sections.items():
            self._apply_section_specs(profiles, slot, ref, section)
        pps_notes = sections.get("pps", {}).get("notes") or []
        if pps_notes:
            distinguished = profiles.filtered(lambda profile: profile.id in distinguished_ids)
            if len(distinguished) == 1:
                for field_name, value in pps_notes:
                    self._append_labelled_note(distinguished, ref, field_name, value)
            else:
                self._append_classified_error(ref, "BLOCKED_PPS_PROFILE_IDENTITY", REQUIRED_MAPPING)

    def _apply_section_specs(self, profiles, slot, ref, section) -> None:
        phrases = list(slot["phrases"])
        structured = {"type": slot["hints"][0]} if len(phrases) == 1 and len(slot["hints"]) == 1 else None
        identities = []
        for phrase in phrases:
            normalized, _dropped = self._resolve_material(phrase, structured if len(phrases) == 1 else None)
            if normalized.unresolved or not normalized.polymer:
                continue
            form_id = normalized.form.id if len(normalized.form) == 1 else False
            grade = normalized.material_grade
            grade_id = grade.id if len(grade) == 1 else False
            identities.append((normalized.polymer.id, form_id, grade_id))
        chosen = profiles.browse()
        if len(set(identities)) == 1 and identities:
            polymer_id, form_id, grade_id = identities[0]
            chosen = profiles.filtered(
                lambda profile, polymer_id=polymer_id, form_id=form_id, grade_id=grade_id: (
                    profile.polymer_id.id == polymer_id
                    and (profile.form_id.id or False) == form_id
                    and (profile.material_grade_id.id or False) == grade_id
                )
            )
        if len(chosen) != 1:
            if slot["weights"] or slot["loads"] or slot["colors"] or (section != "pps" and slot["notes"]):
                self._append_classified_error(
                    ref, f"APPROVED_SKIP: {section or 'general'} spec is not profile-unique", OPTIONAL_CONTEXT
                )
            return
        self._fill_profile_specs(chosen, slot, ref)
        if section != "pps":
            for field_name, value in slot["notes"]:
                self._append_labelled_note(chosen, ref, field_name, value)

    def _fill_profile_specs(self, profile, slot, ref) -> None:
        if slot["weights"]:
            parsed = [_pounds(value) for value in slot["weights"]]
            if any(item is None for item in parsed) or len(set(parsed)) != 1:
                self._append_classified_error(ref, "APPROVED_SKIP: quantity_per_load_lbs", OPTIONAL_CONTEXT)
            elif not profile.quantity_per_load_lbs:
                profile.quantity_per_load_lbs = parsed[0]
            elif abs(profile.quantity_per_load_lbs - parsed[0]) > 0.001:
                self._append_classified_error(ref, "APPROVED_SKIP: quantity_per_load_lbs already set", OPTIONAL_CONTEXT)
        if slot["loads"]:
            parsed = [_loads_count(value) for value in slot["loads"]]
            if any(item is None for item in parsed) or len(set(parsed)) != 1:
                self._append_classified_error(ref, "APPROVED_SKIP: loads_per_month", OPTIONAL_CONTEXT)
            elif not profile.loads_per_month:
                profile.loads_per_month = parsed[0]
            elif profile.loads_per_month != parsed[0]:
                self._append_classified_error(ref, "APPROVED_SKIP: loads_per_month already set", OPTIONAL_CONTEXT)
        if slot["colors"]:
            color = self._exact_color(slot["colors"])
            if not color:
                self._append_classified_error(ref, "APPROVED_SKIP: color_ids", OPTIONAL_CONTEXT)
            elif not profile.color_ids:
                profile.color_ids = color
            elif profile.color_ids != color:
                self._append_classified_error(ref, "APPROVED_SKIP: color_ids already set", OPTIONAL_CONTEXT)

    def _exact_color(self, values):
        Color = self.env["plasticos.material.color"]
        colors = Color.search([])
        found = []
        for value in values:
            text = _collapse_ws(value)
            if not text:
                return Color.browse()
            tokens = [token.strip() for token in re.split(r"[,;]", text) if token.strip()]
            if not tokens:
                return Color.browse()
            for token in tokens:
                exact = colors.filtered(
                    lambda color, token=token: (
                        color.name.casefold() == token.casefold() or (color.code or "").casefold() == token.casefold()
                    )
                )
                if len(exact) != 1:
                    return Color.browse()
                found.append(exact.id)
        if not found:
            return Color.browse()
        return Color.browse(found)

    def _append_labelled_note(self, profile, external_id, field_name, value) -> None:
        line = provenance_line(external_id, field_name, value)
        existing = (profile.freeform_notes or "").splitlines()
        if line in existing:
            return
        notes = profile.freeform_notes or ""
        profile.freeform_notes = f"{notes}\n{line}" if notes else line

    def _apply_person_materials(self, partner, dto) -> None:
        if not _parse_material_sections(dto.custom_fields):
            return
        if _notes_only_sections(dto.custom_fields):
            facility, _reason = _facility_partner_for_person(partner)
            located = (
                self.env["plasticos.facility.profile"].search([("partner_id", "=", facility.id)])
                if facility is not None
                else self.env["plasticos.facility.profile"].browse()
            )
            if facility is None or len(located) != 1:
                if _parse_material_sections(dto.custom_fields).get("pps", {}).get("notes"):
                    self._append_classified_error(dto.external_id, "BLOCKED_PPS_PROFILE_IDENTITY", REQUIRED_MAPPING)
                return
        facility, _reason = _facility_partner_for_person(partner)
        owner = facility if facility is not None else partner
        profiles = self.env["plasticos.facility.profile"].search([("partner_id", "=", owner.id)])
        try:
            with self.env.cr.savepoint():
                self._import_section_materials(
                    self.env[CRM_LEAD].browse(),
                    (dto.custom_fields,),
                    partner=owner,
                    facility_profile=profiles if len(profiles) == 1 else None,
                    external_id=dto.external_id,
                )
        except Exception as exc:  # noqa: BLE001 - material failure must not drop the admitted person
            _logger.warning("Person material normalization failed for %s: %s", dto.external_id, exc)
            self._append_classified_error(
                dto.external_id,
                f"material normalization failed: {exc}",
                REQUIRED_MAPPING,
            )

    def _guard_unapproved_stage(self, dto, lead, vals) -> None:
        if "stage_id" not in vals:
            return
        raw = _collapse_ws(dto.lead_status_raw)
        from odoo.addons.plasticos_crm_bridge.models.crm_mapping import STAGE_MAPPING  # noqa: PLC0415

        won = lead and getattr(getattr(lead, "stage_id", None), "is_won", False)
        if won or (raw and raw not in STAGE_MAPPING and lead and getattr(lead, "id", False)):
            vals.pop("stage_id", None)
        if not raw or raw in STAGE_MAPPING:
            return
        current = getattr(lead, "description", False) if lead and getattr(lead, "id", False) else False
        if provenance_already_recorded(current, dto.external_id, "Lead Status", raw):
            return
        self._append_classified_error(dto.external_id, f"BLOCKED_STAGE_APPROVAL: {raw}", OPTIONAL_CONTEXT)

    def _apply_crm_classification(self, lead, dto, partner=None) -> None:
        """Keep a failed tag or category write inside this contact's savepoint."""
        try:
            with self.env.cr.savepoint():
                self._apply_crm_classification_body(lead, dto, partner=partner)
        except Exception as exc:  # noqa: BLE001 - classification must not drop the admitted contact
            _logger.warning("CRM classification failed for %s: %s", dto.external_id, exc)
            self._append_classified_error(dto.external_id, f"classification failed: {exc}", REQUIRED_MAPPING)

    def _apply_crm_classification_body(self, lead, dto, partner=None) -> None:
        from odoo import Command  # noqa: PLC0415 - pure-Python tests import this module without Odoo
        from odoo.addons.plasticos_crm_bridge.models.crm_mapping import (  # noqa: PLC0415
            COMPANY_TYPE_ALIASES,
            COMPANY_TYPE_MAPPING,
            CRM_ROLE_TAG_MAPPING,
        )

        custom = dto.custom_fields or {}
        self._apply_crm_role_tags(lead, dto, custom, Command, CRM_ROLE_TAG_MAPPING)
        self._apply_company_type(lead, dto, partner, custom, Command, COMPANY_TYPE_MAPPING, COMPANY_TYPE_ALIASES)

    def _apply_crm_role_tags(self, lead, dto, custom, command, mapping) -> None:
        raw = _collapse_ws(custom.get("Buyer/Supplier"))
        if not raw:
            return
        has_lead = bool(lead and getattr(lead, "id", False))
        for token in _split_material_values(raw.replace(";", ",").replace(",", "\n")):
            role = {"buyer": "Buyer", "supplier": "Supplier"}.get(token.casefold())
            if not role:
                self._append_classified_error(dto.external_id, f"BLOCKED_ROLE_TOKEN: {token}", OPTIONAL_CONTEXT)
                continue
            if not has_lead:
                self._append_classified_error(dto.external_id, "BLOCKED_NO_CRM_LEAD", OPTIONAL_CONTEXT)
                continue
            tag = self._crm_role_tag(role, mapping)
            if not tag:
                self._append_classified_error(dto.external_id, f"BLOCKED_DESTINATION: {role}", OPTIONAL_CONTEXT)
                continue
            if tag not in lead.tag_ids:
                lead.write({"tag_ids": [command.link(tag.id)]})

    def _crm_role_tag(self, role_name, mapping):
        """Return the one verified Buyer or Supplier tag, or nothing.

        A present XML id that does not name that live ``crm.tag`` is corrupt.
        Corrupt metadata does not fall through to another row of the same name,
        and this sync does not repair ``ir.model.data``. A missing XML id may
        use the one exact native tag. Any other count fails closed.
        """
        from odoo.addons.plasticos_crm_bridge.models.crm_tag_adoption import (  # noqa: PLC0415
            MISSING_ROLE_TAG_BINDING,
            role_tag_binding,
        )

        xmlid = mapping[role_name]
        found = role_tag_binding(self.env, role_name, xmlid)
        if found is None:
            return None
        if found is not MISSING_ROLE_TAG_BINDING:
            return found
        found = self.env["crm.tag"].search([("name", "=", role_name)])
        if len(found) != 1 or found._name != "crm.tag" or found.name != role_name:
            return None
        return found

    def _apply_company_type(self, lead, dto, partner, custom, command, mapping, aliases) -> None:
        raw = _collapse_ws(custom.get("Company Type"))
        if not raw:
            return
        canonical = aliases.get(raw, raw)
        xmlid = mapping.get(canonical)
        if not xmlid:
            self._append_classified_error(dto.external_id, f"BLOCKED_COMPANY_TYPE_VALUE: {raw}", OPTIONAL_CONTEXT)
            return
        company = _verified_company(lead, partner)
        if company is None:
            self._append_classified_error(dto.external_id, f"BLOCKED_COMPANY_TYPE_VALUE: {raw}", OPTIONAL_CONTEXT)
            return
        category = self.env.ref(xmlid, raise_if_not_found=False)
        if not category:
            self._append_classified_error(dto.external_id, f"BLOCKED_COMPANY_TYPE_VALUE: {raw}", OPTIONAL_CONTEXT)
            return
        if _company_type_overlaps(company, category.name):
            self._append_classified_error(
                dto.external_id, f"BLOCKED_COMPANY_TYPE_SEMANTIC_OVERLAP: {canonical}", OPTIONAL_CONTEXT
            )
            return
        if category not in company.category_id:
            company.write({"category_id": [command.link(category.id)]})

    def _write_profile_classification(self, profile, normalized) -> None:
        """Fill empty grade, source, color, packaging, filler, process, and attributes. A stored value is kept."""
        from odoo import Command  # noqa: PLC0415 - pure-Python tests import this module without Odoo

        if normalized.grade:
            from odoo.addons.plasticos_material_profile.quality_tier_codes import (  # noqa: PLC0415
                LETTER_TO_QUALITY_TIER,
            )

            code = LETTER_TO_QUALITY_TIER.get(normalized.grade)
            current = profile.quality_tier_id
            if code and current and current.code != code:
                self._append_classified_error(
                    str(profile.id),
                    (
                        f"grade {normalized.grade} conflicts with stored grade {current.code} "
                        f"on profile {profile.id}; attributes unchanged"
                    ),
                    REQUIRED_MAPPING,
                )
                return
            if code and not current:
                profile.quality_tier_id = self.env.ref(f"plasticos_material_profile.quality_tier_{code.lower()}")
        if normalized.source_type and not profile.source_type_id:
            profile.source_type_id = normalized.source_type
        elif normalized.source_type and profile.source_type_id and profile.source_type_id != normalized.source_type:
            self._append_classified_error(
                str(profile.id),
                (
                    f"source {normalized.source_type.code} conflicts with stored source "
                    f"{profile.source_type_id.code} on profile {profile.id}; source unchanged"
                ),
                REQUIRED_MAPPING,
            )
            return
        colors = getattr(normalized, "color", None)
        if colors:
            if not profile.color_ids:
                profile.color_ids = colors
            elif profile.color_ids != colors:
                self._append_classified_error(
                    str(profile.id),
                    (
                        f"colors {', '.join(colors.mapped('code'))} conflict with stored "
                        f"{', '.join(profile.color_ids.mapped('code'))} on profile {profile.id}; colors unchanged"
                    ),
                    REQUIRED_MAPPING,
                )
        for field_name, resolved in (
            ("packaging_type_id", getattr(normalized, "packaging_type", None)),
            ("filler_type_id", getattr(normalized, "filler_type", None)),
        ):
            if not resolved:
                continue
            current = profile[field_name]
            if not current:
                profile[field_name] = resolved
            elif current != resolved:
                self._append_classified_error(
                    str(profile.id),
                    (
                        f"{field_name} {resolved.code} conflicts with stored {current.code} "
                        f"on profile {profile.id}; {field_name} unchanged"
                    ),
                    REQUIRED_MAPPING,
                )
        process = getattr(normalized, "process_type", None)
        if process:
            current = profile.origin_process_type
            if not current:
                profile.origin_process_type = process
            elif current != process:
                self._append_classified_error(
                    str(profile.id),
                    (
                        f"origin_process_type {process} conflicts with stored {current} "
                        f"on profile {profile.id}; origin_process_type unchanged"
                    ),
                    REQUIRED_MAPPING,
                )
        if not normalized.attributes:
            return
        missing = normalized.attributes - profile.material_attribute_ids
        if missing:
            profile.write({"material_attribute_ids": [Command.link(attribute.id) for attribute in missing]})

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
            person_ref = self._find_person_ref(orphan.provider, orphan.contact_external_id)
            if not lead and not person_ref:
                continue
            payload = orphan.payload_json or {}
            if orphan.kind == "table_row":
                cleaned_payload = retained_table_orphan_payload(payload)
                if cleaned_payload is not payload:
                    orphan.payload_json = cleaned_payload
                    payload = cleaned_payload
            lead_id, partner_id = self._history_links(person_ref, lead)
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
                    "lead_id": lead_id,
                    "partner_id": partner_id,
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
                    "lead_id": lead_id,
                    "partner_id": partner_id,
                    "contact_external_id": payload.get("contact_external_id"),
                    "table_id": payload.get("table_id"),
                    "table_name": payload.get("table_name") or False,
                    "external_row_id": payload.get("external_row_id"),
                    "fields_json": omit_excluded_source_fields(payload.get("fields") or {}),
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

    def _history_links(self, person_ref, lead):
        """Return ``(lead_id, partner_id)`` for one call or custom-table row.

        A VanillaSoft contact bound to an ERP person keeps its history on that
        person. A contact that is still only a lead keeps its history on the lead.
        A ref whose ``res_id`` no longer names a partner is treated as unbound:
        ``res_id`` is a plain integer and ``partner_id`` is a foreign key.
        """
        partner_id = person_ref.res_id if person_ref else False
        if partner_id and self.env["res.partner"].browse(partner_id).exists():
            return False, partner_id
        return (lead.id if lead else False), False

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
        # active_test=False for the same reason as `_upsert_lead`: a call or
        # custom-table row belonging to a sync-archived lead must attach to that
        # lead, not be buffered as an orphan that never resolves.
        return (
            self.env[CRM_LEAD]
            .with_context(active_test=False)
            .search([("vanillasoft_id", "=", contact_external_id)], limit=1)
        )
