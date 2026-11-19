"""Seeded res.users records must not carry a login password.

Issue #508: a password field on a data record is written at install and stays
in git. Accounts are created without one and receive a password through the
Odoo reset flow. The assertion names the file, xmlid, and field only.
"""

import xml.etree.ElementTree as ET
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
FORBIDDEN = frozenset({"password", "new_password"})


def _seeded_password_fields():
    offenders = []
    for path in sorted(REPO.glob("plasticos_*/**/*.xml")):
        if not path.is_file():
            continue
        root = ET.parse(path).getroot()
        for record in root.iter("record"):
            if record.get("model") != "res.users":
                continue
            xmlid = record.get("id") or "(no xmlid)"
            for field in record.findall("field"):
                name = field.get("name") or ""
                if name in FORBIDDEN:
                    offenders.append(f"{path.relative_to(REPO)}:{xmlid}:{name}")
    return offenders


def test_seeded_users_have_no_password_field():
    offenders = _seeded_password_fields()
    assert not offenders, "res.users seed records must not set a password:\n" + "\n".join(offenders)
