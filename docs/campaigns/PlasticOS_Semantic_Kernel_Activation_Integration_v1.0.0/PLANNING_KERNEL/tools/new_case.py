#!/usr/bin/env python3
"""Generate a blank non-authoritative planning case without touching repository code."""
import argparse,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser()
p.add_argument('--mode',required=True,choices=['new_addon','wip_alignment'])
p.add_argument('--id',required=True)
p.add_argument('--out',required=True,type=Path)
a=p.parse_args()
case=json.loads((ROOT/'TEMPLATES/CASE.template.json').read_text())
case['case_id']=a.id;case['mode']=a.mode
if a.mode == 'wip_alignment':
    case['target']['wip']={'base_revision':'','head_revision':'','test_evidence':'','related_prs':[],'capabilities':[]}
if a.out.exists(): p.error('Refusing to overwrite '+str(a.out))
a.out.parent.mkdir(parents=True,exist_ok=True)
a.out.write_text(json.dumps(case,indent=2)+'\n')
print('Generated DRAFT case (no code permission):', a.out)
