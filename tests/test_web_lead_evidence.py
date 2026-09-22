"""Pure component tests for durable attachment and reconciliation evidence."""

from __future__ import annotations

import hashlib
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = ROOT / "plasticos_web_leads"

package = sys.modules.setdefault("plasticos_web_leads", types.ModuleType("plasticos_web_leads"))
package.__path__ = [str(PACKAGE_ROOT)]
models_package = sys.modules.setdefault("plasticos_web_leads.models", types.ModuleType("plasticos_web_leads.models"))
models_package.__path__ = [str(PACKAGE_ROOT / "models")]

from plasticos_web_leads.models.attachment_processor import (  # noqa: E402
    copy_successful_attachments_to_intake,
    process_attachments,
)
from plasticos_web_leads.models.evidence_reconciler import (  # noqa: E402
    EVIDENCE_SCHEMA_VERSION,
    reconcile_evidence,
)
from plasticos_web_leads.models.quantity_normalizer import normalize_quantity_evidence  # noqa: E402


class _StoredAttachment:
    def __init__(self, attachment_id, values):
        self.id = attachment_id
        self.name = values["name"]
        self.datas = values["datas"]
        self.mimetype = values["mimetype"]
        self.res_model = values.get("res_model")
        self.res_id = values.get("res_id")
        self.description = values.get("description")

    def exists(self):
        return True


class _AttachmentModel:
    def __init__(self):
        self.created = []

    def create(self, values):
        stored = _StoredAttachment(len(self.created) + 1, values)
        self.created.append(stored)
        return stored

    def browse(self, attachment_id):
        return self.created[attachment_id - 1]

    def search_count(self, _domain):
        return 0

    def search(self, domain):
        filters = dict((term[0], term[2]) for term in domain if len(term) == 3 and term[1] == "=")
        return _RecordSet(
            [
                item
                for item in self.created
                if all(getattr(item, field) == expected for field, expected in filters.items())
            ]
        )


class _RecordSet(list):
    def mapped(self, field_name):
        return [getattr(item, field_name) for item in self]


class _Lead:
    def __init__(self):
        self.id = 17
        self.attachments = _AttachmentModel()
        self.env = {"ir.attachment": self.attachments}


class _Intake:
    def __init__(self, intake_id):
        self.id = intake_id


class _Response:
    def __init__(self, content, content_type="image/jpeg"):
        self.content = content
        self.headers = {"Content-Type": content_type}

    def raise_for_status(self):
        return None

    def iter_content(self, chunk_size):
        del chunk_size
        yield self.content


def _attachment(source_id="source-1", content_type="image/jpeg", size=4):
    return {
        "source_id": source_id,
        "attachment_index": 0,
        "filename": "evidence.bin",
        "content_type": content_type,
        "size_bytes": size,
        "source_url": "https://files.example.test/evidence.bin",
    }


def test_image_evidence_stores_hash_and_preserves_analysis_failure():
    lead = _Lead()
    content = b"abcd"

    results = process_attachments(
        lead=lead,
        attachments=[_attachment()],
        analyzer=lambda _bytes, _mimetype: (_ for _ in ()).throw(RuntimeError("vision down")),
        http_get=lambda *_args, **_kwargs: _Response(content),
    )

    row = results[0]
    assert row["acquisition_status"] == "success"
    assert row["content_sha256"] == hashlib.sha256(content).hexdigest()
    assert row["ir_attachment_id"] == 1
    assert row["analysis_status"] == "failed"
    assert row["error"]["code"] == "image_analysis_failed"
    assert len(lead.attachments.created) == 1


def test_pdf_is_stored_and_explicitly_unsupported_for_text_analysis():
    lead = _Lead()
    content = b"%PDF"

    results = process_attachments(
        lead=lead,
        attachments=[_attachment(content_type="application/pdf")],
        http_get=lambda *_args, **_kwargs: _Response(content, "application/pdf"),
    )

    row = results[0]
    assert row["acquisition_status"] == "success"
    assert row["analysis_type"] == "document"
    assert row["analysis_status"] == "unsupported"
    assert row["error"]["code"] == "document_text_extraction_not_enabled"


def test_provider_mime_remains_authoritative_over_response_header():
    lead = _Lead()
    content = b"%PDF"

    results = process_attachments(
        lead=lead,
        attachments=[_attachment(content_type="application/pdf")],
        http_get=lambda *_args, **_kwargs: _Response(content, "image/jpeg"),
    )

    row = results[0]
    assert row["content_type"] == "application/pdf"
    assert row["analysis_type"] == "document"
    assert row["analysis_status"] == "unsupported"
    assert lead.attachments.created[0].mimetype == "application/pdf"


def test_size_mismatch_produces_evidence_without_storing_bytes():
    lead = _Lead()

    results = process_attachments(
        lead=lead,
        attachments=[_attachment(size=5)],
        http_get=lambda *_args, **_kwargs: _Response(b"abcd"),
    )

    assert results[0]["acquisition_status"] == "failed"
    assert results[0]["error"]["code"] == "size_mismatch"
    assert lead.attachments.created == []


def test_network_failure_preserves_one_failed_result_after_bounded_retries():
    lead = _Lead()
    calls = 0

    def _failing_get(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        raise RuntimeError("network unavailable")

    results = process_attachments(
        lead=lead,
        attachments=[_attachment()],
        http_get=_failing_get,
    )

    assert calls == 3
    assert len(results) == 1
    assert results[0]["acquisition_status"] == "failed"
    assert results[0]["error"]["code"] == "acquisition_failed"
    assert lead.attachments.created == []


def test_unsupported_binary_is_stored_with_explicit_evidence():
    lead = _Lead()
    content = b"binary"

    results = process_attachments(
        lead=lead,
        attachments=[_attachment(content_type="application/octet-stream", size=len(content))],
        http_get=lambda *_args, **_kwargs: _Response(content, "application/octet-stream"),
    )

    row = results[0]
    assert row["acquisition_status"] == "success"
    assert row["analysis_type"] == "unsupported"
    assert row["analysis_status"] == "unsupported"
    assert row["error"]["code"] == "document_text_extraction_not_enabled"
    assert len(lead.attachments.created) == 1


def test_same_content_can_remain_distinct_provider_evidence():
    lead = _Lead()
    content = b"same"
    first = _attachment(source_id="provider-a")
    second = _attachment(source_id="provider-b")
    second["attachment_index"] = 1

    results = process_attachments(
        lead=lead,
        attachments=[first, second],
        http_get=lambda *_args, **_kwargs: _Response(content),
    )

    assert [row["source_id"] for row in results] == ["provider-a", "provider-b"]
    assert results[0]["content_sha256"] == results[1]["content_sha256"]
    assert len(lead.attachments.created) == 2


def test_intake_copy_is_idempotent_by_provider_source_id_not_filename():
    lead = _Lead()
    intake = _Intake(44)
    first = _attachment(source_id="provider-a")
    second = _attachment(source_id="provider-b")
    second["attachment_index"] = 1

    rows = process_attachments(
        lead=lead,
        attachments=[first, second],
        http_get=lambda *_args, **_kwargs: _Response(b"same"),
    )
    evidence = {"attachments": rows}

    copy_successful_attachments_to_intake(lead=lead, intake=intake, evidence_bundle=evidence)
    copy_successful_attachments_to_intake(lead=lead, intake=intake, evidence_bundle=evidence)

    copied = [item for item in lead.attachments.created if item.res_model == "plasticos.intake"]
    assert len(copied) == 2
    assert {item.description for item in copied} == {
        "[web-lead-source-id:provider-a]",
        "[web-lead-source-id:provider-b]",
    }


def test_successful_attachment_evidence_is_reused_without_redownload():
    lead = _Lead()
    previous = {
        "attachments": [
            {
                "source_id": "source-1",
                "actual_size_bytes": 4,
                "acquisition_status": "success",
                "ir_attachment_id": 99,
            }
        ]
    }

    results = process_attachments(
        lead=lead,
        attachments=[_attachment()],
        evidence_bundle=previous,
        http_get=lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("must not redownload")),
    )

    assert results == previous["attachments"]
    assert lead.attachments.created == []


def test_reconciliation_preserves_seller_vision_conflict_and_unknown_weight():
    quantity = normalize_quantity_evidence(quantity_text="3 loads", weight_per_load_text="", frequency_text="")
    bundle = reconcile_evidence(
        canonical_payload={"contaminants_text": "none", "material_description": "HDPE regrind"},
        quantity=quantity,
        ai_normalized={"polymer": "HDPE", "is_plastic": True},
        attachments=[
            {
                "analysis_type": "image",
                "analysis_status": "success",
                "analysis": {"contamination_visible": True, "material_form_observed": "Loose"},
            }
        ],
        run_id="run-123",
    )

    assert bundle["schema_version"] == EVIDENCE_SCHEMA_VERSION
    assert bundle["run_id"] == "run-123"
    assert bundle["conflicts"][0]["field"] == "contamination"
    assert bundle["seller"]["contaminants_text"] == "none"
    assert any("per-load weight" in item for item in bundle["clarification_requests"])
