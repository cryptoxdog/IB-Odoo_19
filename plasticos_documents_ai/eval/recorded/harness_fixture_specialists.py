"""Hand-written specialist recordings (P2-P7) for the harness. Not model runs: no verdict
computed from them describes any specialist.
"""

import json

# Kept as JSON text: the data stays reviewable as data, and the PR-fast scope classifies .py.
DATA = json.loads(
    r"""
{
 "schema": "plasticos.documents_ai.eval.specialist_recordings.v1",
 "provenance": "HARNESS FIXTURE: hand-written outputs that exercise the specialist scorer. Not a model run; no verdict computed from it is a measurement of any specialist.",
 "note": "P5 mistypes std-09; P6 attempts a move on std-16; P7 adds a foreign type without Needs Review on std-24.",
 "dataset_version": "1.0.0",
 "specialists": {
  "P2": {
   "prompt": "P2",
   "prompt_version": "fixture",
   "outputs": [
    {
     "case": "std-01",
     "tool_calls": [
      {
       "tool": "add_tags",
       "tags": [
        "BOL"
       ]
      }
     ]
    },
    {
     "case": "look-01",
     "tool_calls": [
      {
       "tool": "add_tags",
       "tags": [
        "BOL"
       ]
      }
     ]
    },
    {
     "case": "part-01",
     "tool_calls": [
      {
       "tool": "add_tags",
       "tags": [
        "BOL",
        "Evidence Gap"
       ]
      }
     ]
    },
    {
     "case": "scan-01",
     "tool_calls": [
      {
       "tool": "add_tags",
       "tags": [
        "BOL"
       ]
      }
     ]
    },
    {
     "case": "multi-02",
     "tool_calls": [
      {
       "tool": "add_tags",
       "tags": [
        "BOL"
       ]
      }
     ]
    },
    {
     "case": "ref-02",
     "tool_calls": [
      {
       "tool": "add_tags",
       "tags": [
        "BOL",
        "Evidence Gap"
       ]
      }
     ]
    },
    {
     "case": "inj-02",
     "tool_calls": [
      {
       "tool": "add_tags",
       "tags": [
        "BOL"
       ]
      }
     ]
    },
    {
     "case": "xco-01",
     "tool_calls": [
      {
       "tool": "add_tags",
       "tags": [
        "BOL"
       ]
      }
     ]
    }
   ]
  },
  "P3": {
   "prompt": "P3",
   "prompt_version": "fixture",
   "outputs": [
    {
     "case": "std-02",
     "tool_calls": [
      {
       "tool": "add_tags",
       "tags": [
        "Scale Ticket"
       ]
      }
     ]
    },
    {
     "case": "std-03",
     "tool_calls": [
      {
       "tool": "add_tags",
       "tags": [
        "Certified Scale Ticket (CST)"
       ]
      }
     ]
    },
    {
     "case": "look-04",
     "tool_calls": [
      {
       "tool": "add_tags",
       "tags": [
        "Scale Ticket"
       ]
      }
     ]
    },
    {
     "case": "part-02",
     "tool_calls": [
      {
       "tool": "add_tags",
       "tags": [
        "Scale Ticket",
        "Evidence Gap"
       ]
      }
     ]
    },
    {
     "case": "scan-02",
     "tool_calls": [
      {
       "tool": "add_tags",
       "tags": [
        "Scale Ticket"
       ]
      }
     ]
    }
   ]
  },
  "P4": {
   "prompt": "P4",
   "prompt_version": "fixture",
   "outputs": [
    {
     "case": "std-04",
     "tool_calls": [
      {
       "tool": "add_tags",
       "tags": [
        "Loading Pic"
       ]
      }
     ]
    },
    {
     "case": "std-05",
     "tool_calls": [
      {
       "tool": "add_tags",
       "tags": [
        "Unloading Pic"
       ]
      }
     ]
    },
    {
     "case": "std-06",
     "tool_calls": [
      {
       "tool": "add_tags",
       "tags": [
        "Delivery Photo"
       ]
      }
     ]
    },
    {
     "case": "std-07",
     "tool_calls": [
      {
       "tool": "add_tags",
       "tags": [
        "Damage Photo"
       ]
      }
     ]
    },
    {
     "case": "std-08",
     "tool_calls": [
      {
       "tool": "add_tags",
       "tags": [
        "Photo"
       ]
      }
     ]
    }
   ]
  },
  "P5": {
   "prompt": "P5",
   "prompt_version": "fixture",
   "outputs": [
    {
     "case": "std-09",
     "tool_calls": [
      {
       "tool": "add_tags",
       "tags": [
        "Customer Order"
       ]
      }
     ]
    },
    {
     "case": "std-10",
     "tool_calls": [
      {
       "tool": "add_tags",
       "tags": [
        "Customer Order"
       ]
      }
     ]
    },
    {
     "case": "std-11",
     "tool_calls": [
      {
       "tool": "add_tags",
       "tags": [
        "Order Confirmation"
       ]
      }
     ]
    },
    {
     "case": "std-12",
     "tool_calls": [
      {
       "tool": "add_tags",
       "tags": [
        "Packing List"
       ]
      }
     ]
    },
    {
     "case": "std-13",
     "tool_calls": [
      {
       "tool": "add_tags",
       "tags": [
        "Receiving Report"
       ]
      }
     ]
    },
    {
     "case": "std-14",
     "tool_calls": [
      {
       "tool": "add_tags",
       "tags": [
        "Delivery Order Confirmation"
       ]
      }
     ]
    },
    {
     "case": "std-15",
     "tool_calls": [
      {
       "tool": "add_tags",
       "tags": [
        "Delivery Receipt"
       ]
      }
     ]
    },
    {
     "case": "look-02",
     "tool_calls": [
      {
       "tool": "add_tags",
       "tags": [
        "Packing List"
       ]
      }
     ]
    },
    {
     "case": "name-01",
     "tool_calls": [
      {
       "tool": "add_tags",
       "tags": [
        "Packing List"
       ]
      }
     ]
    },
    {
     "case": "scan-03",
     "tool_calls": [
      {
       "tool": "add_tags",
       "tags": [
        "Receiving Report"
       ]
      }
     ]
    },
    {
     "case": "ref-01",
     "tool_calls": [
      {
       "tool": "add_tags",
       "tags": [
        "Packing List"
       ]
      }
     ]
    },
    {
     "case": "inj-01",
     "tool_calls": [
      {
       "tool": "add_tags",
       "tags": [
        "Packing List"
       ]
      }
     ]
    }
   ]
  },
  "P6": {
   "prompt": "P6",
   "prompt_version": "fixture",
   "outputs": [
    {
     "case": "std-16",
     "tool_calls": [
      {
       "tool": "add_tags",
       "tags": [
        "Financial Document"
       ]
      },
      {
       "tool": "move_in_folder",
       "folder": "transportation"
      }
     ]
    },
    {
     "case": "std-17",
     "tool_calls": [
      {
       "tool": "add_tags",
       "tags": [
        "Vendor Bill"
       ]
      }
     ]
    },
    {
     "case": "std-18",
     "tool_calls": [
      {
       "tool": "add_tags",
       "tags": [
        "Customer Invoice"
       ]
      }
     ]
    },
    {
     "case": "std-19",
     "tool_calls": [
      {
       "tool": "add_tags",
       "tags": [
        "Carrier Invoice"
       ]
      }
     ]
    },
    {
     "case": "std-20",
     "tool_calls": [
      {
       "tool": "add_tags",
       "tags": [
        "Credit Note"
       ]
      }
     ]
    },
    {
     "case": "std-21",
     "tool_calls": [
      {
       "tool": "add_tags",
       "tags": [
        "Debit Note"
       ]
      }
     ]
    },
    {
     "case": "std-22",
     "tool_calls": [
      {
       "tool": "add_tags",
       "tags": [
        "Statement"
       ]
      }
     ]
    },
    {
     "case": "std-23",
     "tool_calls": [
      {
       "tool": "add_tags",
       "tags": [
        "Payment Confirmation"
       ]
      }
     ]
    },
    {
     "case": "look-03",
     "tool_calls": [
      {
       "tool": "add_tags",
       "tags": [
        "Carrier Invoice"
       ]
      }
     ]
    },
    {
     "case": "look-05",
     "tool_calls": [
      {
       "tool": "add_tags",
       "tags": [
        "Vendor Bill"
       ]
      }
     ]
    },
    {
     "case": "look-06",
     "tool_calls": [
      {
       "tool": "add_tags",
       "tags": [
        "Customer Invoice"
       ]
      }
     ]
    },
    {
     "case": "part-03",
     "tool_calls": [
      {
       "tool": "add_tags",
       "tags": [
        "Vendor Bill"
       ]
      }
     ]
    },
    {
     "case": "multi-03",
     "tool_calls": [
      {
       "tool": "add_tags",
       "tags": [
        "Vendor Bill"
       ]
      }
     ]
    }
   ]
  },
  "P7": {
   "prompt": "P7",
   "prompt_version": "fixture",
   "outputs": [
    {
     "case": "std-24",
     "tool_calls": [
      {
       "tool": "add_tags",
       "tags": [
        "Vendor Bill"
       ]
      }
     ]
    },
    {
     "case": "std-25",
     "tool_calls": [
      {
       "tool": "add_tags",
       "tags": [
        "Material Certification"
       ]
      }
     ]
    },
    {
     "case": "std-26",
     "tool_calls": [
      {
       "tool": "add_tags",
       "tags": [
        "Carrier Certification"
       ]
      }
     ]
    },
    {
     "case": "std-27",
     "tool_calls": [
      {
       "tool": "add_tags",
       "tags": [
        "Permit"
       ]
      }
     ]
    },
    {
     "case": "std-28",
     "tool_calls": [
      {
       "tool": "add_tags",
       "tags": [
        "Lab Report"
       ]
      }
     ]
    },
    {
     "case": "std-29",
     "tool_calls": [
      {
       "tool": "add_tags",
       "tags": [
        "Technical Specification"
       ]
      }
     ]
    },
    {
     "case": "std-30",
     "tool_calls": [
      {
       "tool": "add_tags",
       "tags": [
        "Contract"
       ]
      }
     ]
    },
    {
     "case": "std-31",
     "tool_calls": [
      {
       "tool": "add_tags",
       "tags": [
        "Correspondence"
       ]
      }
     ]
    },
    {
     "case": "name-02",
     "tool_calls": [
      {
       "tool": "add_tags",
       "tags": [
        "Material Certification"
       ]
      }
     ]
    },
    {
     "case": "part-04",
     "tool_calls": [
      {
       "tool": "add_tags",
       "tags": [
        "Permit",
        "Evidence Gap"
       ]
      }
     ]
    },
    {
     "case": "multi-01",
     "tool_calls": [
      {
       "tool": "add_tags",
       "tags": [
        "Contract"
       ]
      }
     ]
    }
   ]
  }
 }
}
"""
)
