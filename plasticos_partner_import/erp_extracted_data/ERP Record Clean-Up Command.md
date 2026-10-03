python3 -c '
import re
p = "plasticos_partner_import/erp_extracted_data/bulk/Address.csv"
text = open(p).read()
for old in [
    "; ib@ucsincny.com",
    "; ib@scrapmanagement.com",
    "; abuyanovskiy@ucsincny.com",
    "; ab@scrapmanagement.com",
    "; aa@scrapmanagement.com",
    "; aakopyan@ucsincny.com",
    "; rp@scrapmanagement.com",
    "; jb@scrapmanagement.com",
    "; jb@scrapmanagment.com",
    "jb@scrapmanagement.com",
    ", ib@scrapmanagement.com",
    "; ibeylin@ucsincny.com",
    "; ab@ucsincny.com",
    "; yklevtsov@ucsincny.com",
    "yklevtsov@ucsincny.com",
    "; jb@ucsincny.com",
    "jb@ucsincny.com",
    "; sales2@scrapmanagement.com",
    "sales2@scrapmanagement.com",
    "; sale2@scrapmanagement.com",
    "; sa@scrapmanagement.com",
    "sa@scrapmanagement.com",
    ";wcarabano@ucsincny.com",
    "; wcarabano@ucsincny.com",
    "wcarabano@ucsincny.com",
    "; aa@ucsincny.com",
    ";aakopyan@ucsincny.com",
    "; rpereira@ucsincny.com",
    "; yk@ucsincny.com",
    "yk@ucsincny.com",
    "; rp@ucsincny.com",
    "; IB@UCSINCNY.COM",
    "; wc@ucsincny.com",
    ";ibeylin@ucsincny.com",
    ";  rpereira@ucsincny.com",
    "; jbyers@ucsincny.com",
    ";  ibeylin@ucsincny.com",
    ";ib@ucsincny.com",
    "; rpereria@ucsincny.com",
    "; ab@ussmrecycle.com",
]:
    text = text.replace(old, "")
staff = "[A-Za-z0-9._%+\\-]+@(?:scrapmanagement|ucsincny)\\.com"
text = re.sub("(?i);\\s*" + staff, "", text)
text = re.sub("(?i)" + staff + "\\s*;\\s*", "", text)
text = re.sub("(?i)" + staff, "", text)
open(p, "w").write(text)
'
