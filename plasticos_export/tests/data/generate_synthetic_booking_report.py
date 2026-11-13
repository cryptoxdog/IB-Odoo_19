"""Write the synthetic legacy booking report fixture (BRS-EXP-14-R011).

Run from the repository root to regenerate both fixture files byte-stably:

    python3 plasticos_export/tests/data/generate_synthetic_booking_report.py

How the data was made: the 43 headings are the legacy column names in source
order (the operator's heading inventory). Every row value below is invented
here: booking numbers start ``SYN``, container numbers ``SYNU``, partners are
``Synthetic ...`` and ports are ``Port Alpha``/``Port Beta``. No value comes
from the private original workbook, which this script never opens.

Rows deliberately leave POD, ETS or Customer empty so the conformance test can
prove the projection shows those as explicit missing or unknown values.
"""

import csv
import datetime
import pathlib
import sys
import zipfile

HEADINGS = (
    "Container No",
    "Booking No",
    "Seal No",
    "Cutoff",
    "POL",
    "POD",
    "PDLV",
    "Carrier",
    "Vessel",
    "Voyage No",
    "ETS",
    "ETA",
    "Grade",
    "Weight LBS",
    "Supplier",
    "Location",
    "PO No",
    "Source Wks",
    "Customer",
    "SO No",
    "Invoice No",
    "Units",
    "PRVC",
    "Rcv Dt",
    "Release No",
    "Pickup No",
    "Shipping Notes",
    "Wt (MT)",
    "Ship Dt",
    "Ship Time",
    "Rcvd Wt",
    "User",
    "PRA Status",
    "PRA Sent Date",
    "VGM",
    "Eq Tare Wt",
    "BL No",
    "Invoice-User",
    "Container-Ref",
    "Customer-Loc",
    "PO-Ref",
    "UDF-Date",
    "Doc-Cutoff",
)

# (booking, container, pod, ets, customer); every other cell is synthetic filler.
# POD and ETS are booking terms, so every row of one booking states the same ones.
ROWS = (
    ("SYN-BKG-0001", "SYNU0000011", "Port Beta", "2030-01-10", "Synthetic Buyer One"),
    ("SYN-BKG-0001", "SYNU0000022", "Port Beta", "2030-01-10", "Synthetic Buyer One"),
    ("SYN-BKG-0001", "SYNU0000033", "Port Beta", "2030-01-10", ""),
    ("SYN-BKG-0002", "SYNU0000044", "", "2030-02-14", "Synthetic Buyer Two"),
    ("SYN-BKG-0002", "SYNU0000055", "", "2030-02-14", "Synthetic Buyer Two"),
    ("SYN-BKG-0003", "SYNU0000066", "Port Beta", "", "Synthetic Buyer Three"),
    ("SYN-BKG-0004", "SYNU0000077", "", "", ""),
    ("SYN-BKG-0004", "SYNU0000088", "", "", "Synthetic Buyer Four"),
)


def synthetic_row(index, booking, container, pod, ets, customer):
    row = dict.fromkeys(HEADINGS, "")
    row.update(
        {
            "Container No": container,
            "Booking No": booking,
            "Seal No": f"SYNSEAL{index:04d}",
            "Cutoff": "2030-01-05",
            "POL": "Port Alpha",
            "POD": pod,
            "Carrier": "Synthetic Line",
            "Vessel": "Synthetic Vessel",
            "Voyage No": f"SV{index:03d}",
            "ETS": ets,
            "Grade": "Synthetic Grade",
            "Supplier": f"Synthetic Supplier {index}",
            "PO No": f"SYNPO{index:04d}",
            "Customer": customer,
            "SO No": f"SYNSO{index:04d}" if customer else "",
            "User": "synthetic.user",
        }
    )
    return [row[heading] for heading in HEADINGS]


def _cell_ref(col, row):
    letters = ""
    col += 1
    while col:
        col, rem = divmod(col - 1, 26)
        letters = chr(65 + rem) + letters
    return f"{letters}{row}"


def _xml_text(value):
    return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _sheet_xml(rows):
    out = [
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>',
    ]
    for r, values in enumerate(rows, start=1):
        cells = "".join(
            f'<c r="{_cell_ref(c, r)}" t="inlineStr"><is><t>{_xml_text(v)}</t></is></c>'
            for c, v in enumerate(values)
            if v
        )
        out.append(f'<row r="{r}">{cells}</row>')
    out.append("</sheetData></worksheet>")
    return "".join(out)


_STATIC = {
    "[Content_Types].xml": (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/worksheets/sheet1.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        "</Types>"
    ),
    "_rels/.rels": (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="xl/workbook.xml"/></Relationships>'
    ),
    "xl/workbook.xml": (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<sheets><sheet name="Sheet1" sheetId="1" r:id="rId1"/></sheets></workbook>'
    ),
    "xl/_rels/workbook.xml.rels": (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
        'Target="worksheets/sheet1.xml"/></Relationships>'
    ),
}


def write_workbook(path):
    """A minimal standard .xlsx with fixed zip timestamps, so regeneration is byte-stable."""
    rows = [list(HEADINGS)] + [synthetic_row(i, *values) for i, values in enumerate(ROWS, start=1)]
    stamp = datetime.datetime(2030, 1, 1).timetuple()[:6]
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, body in [*_STATIC.items(), ("xl/worksheets/sheet1.xml", _sheet_xml(rows))]:
            info = zipfile.ZipInfo(name, date_time=stamp)
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, body)


def write_inventory(path):
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(["column_index", "legacy_heading"])
        for index, heading in enumerate(HEADINGS, start=1):
            writer.writerow([index, heading])


def main():
    here = pathlib.Path(__file__).resolve().parent
    write_workbook(here / "synthetic_booking_report.xlsx")
    write_inventory(here / "booking_report_heading_inventory.csv")
    return 0


if __name__ == "__main__":
    sys.exit(main())
