"""Structural sensitive-log scanner regressions."""

from __future__ import annotations

import sys
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "audit"))

from security_audit import SecurityAudit  # noqa: E402


def _findings(tmp_path: Path, source: str):
    sample = tmp_path / "sample.py"
    sample.write_text(textwrap.dedent(source), encoding="utf-8")
    return SecurityAudit(tmp_path).check_sensitive_logging()


def test_static_api_key_prose_is_not_a_finding(tmp_path):
    findings = _findings(tmp_path, '_logger = None\ndef run():\n    _logger.info("api_key not configured")\n')
    assert findings == []


def test_static_token_prose_is_not_a_finding(tmp_path):
    findings = _findings(tmp_path, '_logger = None\ndef run():\n    _logger.info("token rotation required")\n')
    assert findings == []


def test_positional_secret_argument_is_high(tmp_path):
    findings = _findings(tmp_path, '_logger = None\ndef run(api_key):\n    _logger.info("api_key=%s", api_key)\n')
    assert len(findings) == 1
    assert findings[0]["type"] == "SENSITIVE_DATA_LOGGED"
    assert findings[0]["severity"] == "HIGH"


def test_fstring_secret_is_high(tmp_path):
    findings = _findings(tmp_path, '_logger = None\ndef run(token):\n    _logger.info(f"token={token}")\n')
    assert len(findings) == 1
    assert findings[0]["severity"] == "HIGH"


def test_percent_interpolation_secret_is_high(tmp_path):
    findings = _findings(tmp_path, '_logger = None\ndef run(secret):\n    _logger.info("secret=%s" % secret)\n')
    assert len(findings) == 1
    assert findings[0]["severity"] == "HIGH"


def test_format_call_secret_is_high(tmp_path):
    findings = _findings(tmp_path, '_logger = None\ndef run(secret):\n    _logger.info("secret={}".format(secret))\n')
    assert len(findings) == 1
    assert findings[0]["severity"] == "HIGH"


def test_token_word_in_prose_with_unrelated_value_is_not_a_finding(tmp_path):
    findings = _findings(
        tmp_path,
        '_logger = None\ndef run(user_name):\n    _logger.info("token rotation for %s", user_name)\n',
    )
    assert findings == []


def test_sensitive_mapping_key_is_high(tmp_path):
    findings = _findings(
        tmp_path, '_logger = None\ndef run(payload):\n    _logger.info("value=%s", payload["api_key"])\n'
    )
    assert len(findings) == 1
    assert findings[0]["type"] == "SENSITIVE_DATA_LOGGED"
    assert findings[0]["severity"] == "HIGH"


def test_sensitive_mapping_key_in_fstring_is_high(tmp_path):
    findings = _findings(
        tmp_path, "_logger = None\ndef run(payload):\n    _logger.info(f\"value={payload['token']}\")\n"
    )
    assert len(findings) == 1
    assert findings[0]["severity"] == "HIGH"


def test_non_sensitive_mapping_key_is_not_a_finding(tmp_path):
    findings = _findings(
        tmp_path, '_logger = None\ndef run(payload):\n    _logger.info("user=%s", payload["user_name"])\n'
    )
    assert findings == []
