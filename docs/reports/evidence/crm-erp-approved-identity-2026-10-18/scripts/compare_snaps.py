import json
import sys

sys.path.insert(0, ".")
from plasticos_crm_sync.services.approved_identity import comment_blocks

a, b = (json.load(open(p)) for p in sys.argv[1:3])
r = {
    "persons": len(b),
    "same_people": set(a) == set(b),
    "partner_id_changed": 0,
    "phone_changed": 0,
    "mobile_set_where_empty": 0,
    "mobile_overwritten": 0,
    "comment_unchanged": 0,
    "comment_appended": 0,
    "comment_erp_blocks_lost": 0,
    "persons_with_erp_note_kept": 0,
    "appended_blocks": 0,
    "duplicate_blocks": 0,
}
for ct, x in a.items():
    y = b[ct]
    r["partner_id_changed"] += x["partner_id"] != y["partner_id"]
    r["phone_changed"] += x["phone"] != y["phone"]
    if x["mobile"] != y["mobile"]:
        r["mobile_set_where_empty" if not x["mobile"] else "mobile_overwritten"] += 1
    xb, yb = comment_blocks(x["comment"]), comment_blocks(y["comment"])
    if x["comment"] == y["comment"]:
        r["comment_unchanged"] += 1
    elif yb[: len(xb)] == xb:
        r["comment_appended"] += 1
        r["appended_blocks"] += len(yb) - len(xb)
    else:
        r["comment_erp_blocks_lost"] += 1
    if xb and yb[: len(xb)] == xb:
        r["persons_with_erp_note_kept"] += 1
    r["duplicate_blocks"] += len(yb) - len(set(yb)) - (len(xb) - len(set(xb)))
print(json.dumps(r, indent=1))
