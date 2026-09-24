"""Pure component tests for durable attachment and reconciliation evidence."""

from __future__ import annotations

import hashlib
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = ROOT / "plasticos_web_leads"

package = sys.modules.setdefault("plasticos_web_leads", types.ModuleType("plasticos_web_leads"))
package.__path__ = [str(PACKAGE_ROOT)]
models_package = sys.modules.setdefault("plasticos_web_leads.models", types.ModuleType("plasticos_web_leads.models"))
models_package.__path__ = [str(PACKAGE_ROOT / "models")]

from plasticos_web_leads.models.attachment_processor import (  # noqa: E402
    AttachmentDestinationError,
    copy_images_to_commercial_record,
    copy_successful_attachments_to_intake,
    fetch_attachment_bytes,
    host_is_allowed,
    process_attachments,
    validate_destination,
)
from plasticos_web_leads.models.evidence_reconciler import (  # noqa: E402
    EVIDENCE_SCHEMA_VERSION,
    reconcile_evidence,
)
from plasticos_web_leads.models.quantity_normalizer import normalize_quantity_evidence  # noqa: E402


class _StoredAttachment:
    def __init__(self, attachment_id, values, model):
        self.id = attachment_id
        self._model = model
        self.name = values["name"]
        self.datas = values["datas"]
        self.mimetype = values["mimetype"]
        self.res_model = values.get("res_model")
        self.res_id = values.get("res_id")
        self.description = values.get("description")
        self.checksum = values.get("checksum") or hashlib.sha1(str(self.datas).encode()).hexdigest()

    def exists(self):
        return True

    def copy(self, values):
        copied_values = {
            "name": self.name,
            "datas": self.datas,
            "mimetype": self.mimetype,
            "res_model": self.res_model,
            "res_id": self.res_id,
            "description": self.description,
            "checksum": self.checksum,
        }
        copied_values.update(values)
        return self._model.create(copied_values)

    def write(self, values):
        for key, value in values.items():
            setattr(self, key, value)
        return True


class _AttachmentModel:
    def __init__(self):
        self.created = []

    def create(self, values):
        stored = _StoredAttachment(len(self.created) + 1, values, self)
        self.created.append(stored)
        return stored

    def browse(self, attachment_id):
        return self.created[attachment_id - 1]

    def search_count(self, _domain):
        return 0

    def search(self, domain):
        filters = dict((term[0], term[2]) for term in domain if len(term) == 3 and term[1] == "=")
        mimetype_prefixes = [
            term[2] for term in domain if len(term) == 3 and term[0] == "mimetype" and term[1] == "like"
        ]
        return _RecordSet(
            [
                item
                for item in self.created
                if all(getattr(item, field) == expected for field, expected in filters.items())
                and all((item.mimetype or "").startswith(prefix.rstrip("%")) for prefix in mimetype_prefixes)
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
    def __init__(self, content, content_type="image/jpeg", status_code=200, headers=None):
        self.content = content
        self.status_code = status_code
        self.headers = {"Content-Type": content_type}
        self.headers.update(headers or {})

    def raise_for_status(self):
        return None

    def iter_content(self, chunk_size):
        del chunk_size
        yield self.content

    def close(self):
        return None


# Provider destination policy fixture: the test host is allowlisted and resolves
# to a public address. DNS is injected so no test touches the network.
_ALLOWED_HOSTS = ("files.example.test",)
_PUBLIC_IP = "93.184.216.34"


def _public_resolver(_host):
    return [_PUBLIC_IP]


def _attachment(source_id="source-1", content_type="image/jpeg", size=4, source_url=None):
    return {
        "source_id": source_id,
        "attachment_index": 0,
        "filename": "evidence.bin",
        "content_type": content_type,
        "size_bytes": size,
        "source_url": "https://files.example.test/evidence.bin" if source_url is None else source_url,
    }


def test_image_evidence_stores_hash_and_preserves_analysis_failure():
    lead = _Lead()
    content = b"abcd"

    results = process_attachments(
        lead=lead,
        allowed_hosts=_ALLOWED_HOSTS,
        resolver=_public_resolver,
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
        allowed_hosts=_ALLOWED_HOSTS,
        resolver=_public_resolver,
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
        allowed_hosts=_ALLOWED_HOSTS,
        resolver=_public_resolver,
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
        allowed_hosts=_ALLOWED_HOSTS,
        resolver=_public_resolver,
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
        allowed_hosts=_ALLOWED_HOSTS,
        resolver=_public_resolver,
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
        allowed_hosts=_ALLOWED_HOSTS,
        resolver=_public_resolver,
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
        allowed_hosts=_ALLOWED_HOSTS,
        resolver=_public_resolver,
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
        allowed_hosts=_ALLOWED_HOSTS,
        resolver=_public_resolver,
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


def _stored_image(model, *, source_model, source_id, description=None, datas="c2FtZQ=="):
    return model.create(
        {
            "name": "material.jpg",
            "datas": datas,
            "mimetype": "image/jpeg",
            "res_model": source_model,
            "res_id": source_id,
            "description": description,
        }
    )


def test_commercial_copy_preserves_distinct_provider_sources_with_same_bytes():
    lead = _Lead()
    attachments = lead.attachments
    _stored_image(attachments, source_model="plasticos.web.lead", source_id=17)
    _stored_image(
        attachments,
        source_model="plasticos.intake",
        source_id=44,
        description="[web-lead-source-id:provider-a]",
    )
    _stored_image(
        attachments,
        source_model="plasticos.intake",
        source_id=44,
        description="[web-lead-source-id:provider-b]",
    )

    sources = [("plasticos.web.lead", 17), ("plasticos.intake", 44)]
    crm_copied = copy_images_to_commercial_record(
        env=lead.env,
        target_model="crm.lead",
        target_id=88,
        sources=sources,
    )
    profile_copied = copy_images_to_commercial_record(
        env=lead.env,
        target_model="plasticos.material.profile",
        target_id=99,
        sources=sources + [("crm.lead", 88)],
    )

    assert crm_copied == 2
    assert profile_copied == 2
    assert (
        copy_images_to_commercial_record(
            env=lead.env,
            target_model="crm.lead",
            target_id=88,
            sources=sources,
        )
        == 0
    )
    crm_images = [item for item in attachments.created if item.res_model == "crm.lead"]
    profile_images = [item for item in attachments.created if item.res_model == "plasticos.material.profile"]
    assert {item.description for item in crm_images} == {
        "[web-lead-source-id:provider-a]",
        "[web-lead-source-id:provider-b]",
    }
    assert {item.description for item in profile_images} == {
        "[web-lead-source-id:provider-a]",
        "[web-lead-source-id:provider-b]",
    }


def test_commercial_copy_deduplicates_legacy_images_by_checksum():
    lead = _Lead()
    attachments = lead.attachments
    _stored_image(attachments, source_model="plasticos.web.lead", source_id=17)
    _stored_image(attachments, source_model="plasticos.intake", source_id=44)

    copied = copy_images_to_commercial_record(
        env=lead.env,
        target_model="crm.lead",
        target_id=88,
        sources=[("plasticos.web.lead", 17), ("plasticos.intake", 44)],
    )

    crm_images = [item for item in attachments.created if item.res_model == "crm.lead"]
    assert copied == 1
    assert len(crm_images) == 1
    assert "[commercial-image-checksum:" in crm_images[0].description


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
        allowed_hosts=_ALLOWED_HOSTS,
        resolver=_public_resolver,
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


# ═══════════════════════════════════════════════════════════════════════════════
# F187-02 — destination policy (SSRF containment)
# ═══════════════════════════════════════════════════════════════════════════════


def test_host_allowlist_matches_exact_and_subdomains_only():
    assert host_is_allowed("files.cognitoforms.com", ("cognitoforms.com",))
    assert host_is_allowed("COGNITOFORMS.COM.", ("*.cognitoforms.com",))
    assert not host_is_allowed("cognitoforms.com.evil.test", ("cognitoforms.com",))
    assert not host_is_allowed("evilcognitoforms.com", ("cognitoforms.com",))
    assert not host_is_allowed("anything.test", ())


@pytest.mark.parametrize(
    "url, code",
    [
        ("https://10.0.0.8/secret", "destination_host_not_allowed"),
        ("http://files.example.test/evidence.bin", "invalid_source_url"),
        ("https://user:pw@files.example.test/evidence.bin", "invalid_source_url"),
        ("https://files.example.test:8443/evidence.bin", "destination_port_rejected"),
        ("https://other.example.test/evidence.bin", "destination_host_not_allowed"),
    ],
)
def test_validate_destination_rejects_scheme_credentials_port_and_unlisted_hosts(url, code):
    with pytest.raises(AttachmentDestinationError) as excinfo:
        validate_destination(url, allowed_hosts=_ALLOWED_HOSTS, resolver=_public_resolver)
    assert excinfo.value.code == code


@pytest.mark.parametrize(
    "address",
    ["127.0.0.1", "10.1.2.3", "172.16.5.5", "192.168.1.9", "169.254.169.254", "::1", "fe80::1", "224.0.0.1", "0.0.0.0"],
)
def test_direct_private_ip_literal_is_rejected_even_when_allowlisted(address):
    host = f"[{address}]" if ":" in address else address
    with pytest.raises(AttachmentDestinationError) as excinfo:
        validate_destination(f"https://{host}/evidence.bin", allowed_hosts=(address,), resolver=_public_resolver)
    assert excinfo.value.code == "destination_address_rejected"


def test_dns_resolved_private_target_is_rejected():
    lead = _Lead()
    calls = 0

    def _never_called(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        return _Response(b"abcd")

    results = process_attachments(
        lead=lead,
        allowed_hosts=_ALLOWED_HOSTS,
        resolver=lambda _host: ["93.184.216.34", "10.0.0.5"],
        attachments=[_attachment()],
        http_get=_never_called,
    )

    assert calls == 0, "a destination that resolves to a private address must never be fetched"
    assert results[0]["acquisition_status"] == "failed"
    assert results[0]["error"]["code"] == "destination_address_rejected"
    assert lead.attachments.created == []


def test_public_url_redirecting_to_private_target_is_rejected():
    lead = _Lead()
    fetched = []

    def _redirecting_get(url, **_kwargs):
        fetched.append(url)
        return _Response(b"", status_code=302, headers={"Location": "https://169.254.169.254/latest/meta-data"})

    results = process_attachments(
        lead=lead,
        allowed_hosts=_ALLOWED_HOSTS,
        resolver=_public_resolver,
        attachments=[_attachment()],
        http_get=_redirecting_get,
    )

    assert fetched == ["https://files.example.test/evidence.bin"]
    assert results[0]["acquisition_status"] == "failed"
    assert results[0]["error"]["code"] == "destination_host_not_allowed"
    assert lead.attachments.created == []


def test_redirect_to_allowlisted_public_target_is_followed_with_bounded_hops():
    hops = []

    def _get(url, **kwargs):
        hops.append((url, kwargs.get("allow_redirects")))
        if len(hops) == 1:
            return _Response(b"", status_code=301, headers={"Location": "/cdn/evidence.bin"})
        return _Response(b"abcd")

    content = fetch_attachment_bytes(
        "https://files.example.test/evidence.bin",
        allowed_hosts=_ALLOWED_HOSTS,
        http_get=_get,
        remaining_bytes=1024,
        resolver=_public_resolver,
    )

    assert content == b"abcd"
    assert hops == [
        ("https://files.example.test/evidence.bin", False),
        ("https://files.example.test/cdn/evidence.bin", False),
    ]


def test_redirect_loop_is_bounded():
    def _loop(url, **_kwargs):
        return _Response(b"", status_code=307, headers={"Location": url})

    with pytest.raises(AttachmentDestinationError) as excinfo:
        fetch_attachment_bytes(
            "https://files.example.test/evidence.bin",
            allowed_hosts=_ALLOWED_HOSTS,
            http_get=_loop,
            remaining_bytes=1024,
            resolver=_public_resolver,
        )
    assert excinfo.value.code == "redirect_limit_exceeded"


def test_allowlisted_public_host_is_accepted_and_policy_rejection_is_not_retried():
    lead = _Lead()
    calls = 0

    def _get(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        return _Response(b"abcd")

    accepted = process_attachments(
        lead=lead,
        allowed_hosts=_ALLOWED_HOSTS,
        resolver=_public_resolver,
        attachments=[_attachment()],
        http_get=_get,
    )
    rejected = process_attachments(
        lead=lead,
        allowed_hosts=_ALLOWED_HOSTS,
        resolver=_public_resolver,
        attachments=[_attachment(source_id="source-2", source_url="https://not-allowed.example.test/x.bin")],
        http_get=_get,
    )

    assert accepted[0]["acquisition_status"] == "success"
    assert rejected[0]["error"]["code"] == "destination_host_not_allowed"
    assert calls == 1, "a deterministic policy rejection is not retried"


def test_no_allowlist_fails_closed():
    lead = _Lead()
    results = process_attachments(
        lead=lead,
        attachments=[_attachment()],
        http_get=lambda *_args, **_kwargs: _Response(b"abcd"),
        resolver=_public_resolver,
    )
    assert results[0]["error"]["code"] == "destination_host_not_allowed"


# ═══════════════════════════════════════════════════════════════════════════════
# F187-03 — acquisition URL is transient, never evidence
# ═══════════════════════════════════════════════════════════════════════════════


def test_result_rows_never_carry_the_acquisition_url():
    lead = _Lead()
    results = process_attachments(
        lead=lead,
        allowed_hosts=_ALLOWED_HOSTS,
        resolver=_public_resolver,
        attachments=[_attachment(), _attachment(source_id="missing", source_url="")],
        http_get=lambda *_args, **_kwargs: _Response(b"abcd"),
    )
    assert all("source_url" not in row for row in results)


def test_retriage_without_acquisition_url_reuses_success_and_marks_rest_unavailable():
    lead = _Lead()
    previous = {
        "attachments": [
            {"source_id": "source-1", "actual_size_bytes": 4, "acquisition_status": "success", "ir_attachment_id": 9}
        ]
    }
    second = _attachment(source_id="source-2", source_url="")
    second["attachment_index"] = 1

    results = process_attachments(
        lead=lead,
        allowed_hosts=_ALLOWED_HOSTS,
        resolver=_public_resolver,
        attachments=[_attachment(source_url=""), second],
        evidence_bundle=previous,
        http_get=lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("must not fetch")),
    )

    assert results[0] == previous["attachments"][0]
    assert results[1]["acquisition_status"] == "failed"
    assert results[1]["error"]["code"] == "acquisition_source_unavailable"


# ═══════════════════════════════════════════════════════════════════════════════
# F187-05 — error-shaped vision results are failures, not evidence
# ═══════════════════════════════════════════════════════════════════════════════


def test_error_shaped_analysis_result_is_failed_evidence_that_requests_review():
    lead = _Lead()
    content = b"abcd"

    results = process_attachments(
        lead=lead,
        allowed_hosts=_ALLOWED_HOSTS,
        resolver=_public_resolver,
        attachments=[_attachment()],
        analyzer=lambda _bytes, _mimetype: {"error": "provider_inference_failed", "provider": {"provider": "openai"}},
        http_get=lambda *_args, **_kwargs: _Response(content),
    )

    row = results[0]
    assert row["acquisition_status"] == "success", "the stored attachment is preserved"
    assert row["ir_attachment_id"] == 1
    assert row["analysis_status"] == "failed"
    assert row["analysis"] is None
    assert row["error"]["code"] == "image_analysis_error"
    assert "provider_inference_failed" in row["error"]["message"]

    quantity = normalize_quantity_evidence(quantity_text="", weight_per_load_text="40000 lbs", frequency_text="")
    bundle = reconcile_evidence(
        canonical_payload={"contaminants_text": "none"},
        quantity=quantity,
        ai_normalized={},
        attachments=results,
    )
    assert bundle["vision"] == []
    assert any("no visual analysis succeeded" in item for item in bundle["clarification_requests"])


def test_non_mapping_analysis_result_is_failed_evidence():
    lead = _Lead()
    results = process_attachments(
        lead=lead,
        allowed_hosts=_ALLOWED_HOSTS,
        resolver=_public_resolver,
        attachments=[_attachment()],
        analyzer=lambda _bytes, _mimetype: "not a mapping",
        http_get=lambda *_args, **_kwargs: _Response(b"abcd"),
    )
    assert results[0]["analysis_status"] == "failed"
    assert results[0]["error"]["code"] == "image_analysis_error"
