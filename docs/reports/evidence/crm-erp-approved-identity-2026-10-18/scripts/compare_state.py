"""Compare approved-contact state before and after the ERP replay.

Usage: compare_state.py <before_crm_snapshot> <state_before_erp> <state_after_erp>
CRM-owned paragraphs are the comment paragraphs that were not there before the first CRM run.
"""

import json
import sys

sys.path.insert(0, ".")
from plasticos_crm_sync.services.approved_identity import comment_blocks  # noqa: E402

pre_crm = json.load(open(sys.argv[1]))
before, after = (json.load(open(p)) for p in sys.argv[2:4])
fail = []
r = {
    "counts_before": before["counts"],
    "counts_after": after["counts"],
    "counts_equal": before["counts"] == after["counts"],
}
if not r["counts_equal"]:
    fail.append("counts differ")

persons = {
    "checked": 0,
    "identical": 0,
    "crm_paragraphs": 0,
    "crm_paragraphs_kept_once": 0,
    "erp_paragraphs": 0,
    "erp_paragraphs_kept_once": 0,
    "phone_lines": 0,
    "phone_lines_identical_people": 0,
}
for ct, b in before["persons"].items():
    a = after["persons"][ct]
    if b.get("marker_rows") != 1:
        if a != b:
            fail.append(f"CT {ct}: unmarked person state changed")
        continue
    persons["checked"] += 1
    persons["identical"] += a == b
    for key in sorted(set(a) | set(b)):
        if a.get(key) != b.get(key) and key != "comment":
            fail.append(f"CT {ct} partner {b['partner_id']}: {key} changed")
    erp = comment_blocks(pre_crm.get(ct, {}).get("comment", ""))
    blocks_b, blocks_a = comment_blocks(b["comment"]), comment_blocks(a["comment"])
    crm = [x for x in blocks_b if x not in erp]
    persons["crm_paragraphs"] += len(crm)
    persons["erp_paragraphs"] += len(erp)
    for x in crm:
        n = blocks_a.count(x)
        persons["crm_paragraphs_kept_once"] += n == 1
        if n != 1:
            fail.append(f"CT {ct} partner {b['partner_id']}: CRM paragraph present {n} times after ERP replay")
    for x in erp:
        n = blocks_a.count(x)
        persons["erp_paragraphs_kept_once"] += n == 1
        if n != 1:
            fail.append(f"CT {ct} partner {b['partner_id']}: ERP paragraph present {n} times after ERP replay")
    if a["comment"] != b["comment"]:
        fail.append(f"CT {ct} partner {b['partner_id']}: comment changed")
    persons["phone_lines"] += len(b["phone_lines"])
    persons["phone_lines_identical_people"] += a["phone_lines"] == b["phone_lines"]

contacts = {"checked": 0, "identical": 0, "refs": 0, "calls": 0}
for vs, b in before["contacts"].items():
    a = after["contacts"][vs]
    contacts["checked"] += 1
    contacts["identical"] += a == b
    contacts["refs"] += len(b["refs"])
    contacts["calls"] += len(b["calls"])
    if a["refs"] != b["refs"]:
        fail.append(f"VS {vs}: external refs changed")
    if a["calls"] != b["calls"]:
        fail.append(f"VS {vs}: call events changed")

r.update({"persons": persons, "contacts": contacts, "failure_count": len(fail), "failures": fail[:50]})
print(json.dumps(r, indent=1))
sys.exit(1 if fail else 0)
