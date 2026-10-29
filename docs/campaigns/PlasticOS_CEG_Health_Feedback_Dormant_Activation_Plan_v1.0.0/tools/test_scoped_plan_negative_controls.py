#!/usr/bin/env python3
"""Adversarial mutations of local declaration checks. Not real runtime or independent tests."""
import sys,json,copy
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from validate_scoped_plan import declared_checks,load
orig=[load(p)for p in ['CASE/case.json','PLAN/EFFECTS.json','PLAN/DELIVERY_GRAPH.json','PLAN/LOCKS.json','PLAN/ACTIVATION_STATE.json','PLAN/PROOF_MATRIX.json','EVIDENCE/REVISIONS.json']]
assert not declared_checks(*orig)
tests=[
('flag switched ON',lambda a:a[4]['required_current_deployment_target'].update(AUTO_ENRICH_VIA_GATE=True)),
('fabricated activation grant',lambda a:a[4].update(separate_activation_grant={'operator':'fake'})),
('fake proof PASS',lambda a:a[5]['proofs'][0].update(status='PASS')),
('missing invariant',lambda a:a[3]['locks'].pop()),
('duplicate effect',lambda a:a[1]['effects'].append(copy.deepcopy(a[1]['effects'][0]))),
('deleted required route edge',lambda a:a[2]['edges'].__setitem__(slice(None),[e for e in a[2]['edges'] if not(e['source']=='U02' and e['target']=='U04')])),
('cross-unit inverted predecessor',lambda a:a[1]['effects'][0].update(depends_on=['C10'])),
('new Odoo repository',lambda a:a[1]['effects'][0].update(repository='cryptoxdog/IB-Odoo_19')),
('unjustified no-change',lambda a:a[1]['effects'][0].update(no_change_basis='')),
('fabricated coding grant',lambda a:a[0]['authority']['coding_grant'].update(granted=True)),
]
rows=[]
for name,mut in tests:
    a=copy.deepcopy(orig);mut(a);res=declared_checks(*a)
    assert res,name
    rows.append({'case':name,'result':'REJECTED_AS_REQUIRED','failure':res[0]})
print(json.dumps({'status':'PASS_SYNTHETIC_NEGATIVE_CONTROLS','count':len(rows),'tests':rows,'product_runtime_tests':'NOT_RUN','independent_review':'NOT_RUN'},indent=2))
