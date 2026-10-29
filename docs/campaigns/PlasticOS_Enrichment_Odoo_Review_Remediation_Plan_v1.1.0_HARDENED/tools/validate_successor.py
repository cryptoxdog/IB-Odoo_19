#!/usr/bin/env python3
"""Package-only consistency checks and deliberate negative controls. Not runtime tests."""
from __future__ import annotations
import json,hashlib,copy,argparse,sys
from pathlib import Path

def load(path):return json.loads(path.read_text())
def hashfile(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def cyclic(g):
 st={}
 def visit(x):
  if st.get(x)==1:return True
  if st.get(x)==2:return False
  st[x]=1
  if any(visit(y) for y in g.get(x,[]) if y in g):return True
  st[x]=2;return False
 return any(visit(n)for n in g)

def check_data(c,g,locks,source,ledger,trace):
 err=[]
 def chk(ok,msg):
  if not ok:err.append(msg)
 ids=[e['id']for e in c['effects']];pids=[p['id']for p in c['delivery']['proofs']];units=c['delivery']['units'];deps={u['id']:u['depends_on']for u in units}
 chk(len(set(ids))==len(ids)==33,'unique effect census')
 chk(len(set(pids))==len(pids)==32,'unique proof census')
 chk(len(set(x['id']for x in locks['locks']))==len(locks['locks'])==21,'operator invariants')
 chk(all(p['status']=='NOT_RUN'for p in c['delivery']['proofs']),'runtime proof falsely passed')
 chk(c['authority']['coding_grant']['granted'] is False,'coding unauthorized')
 chk(c['authority']['plan_acceptance']['granted'] is False,'plan self-accepted')
 chk(c['target']['installed_target']['status']=='UNOBSERVED','installed target falsely observed')
 chk(c['target']['revision']==source['revision']==g['root_revision'],'source revision drift')
 chk(c['target']['repository']=='cryptoxdog/IB-Odoo_19','outside repository')
 chk(g['terminal']=='READY_BUT_DISABLED' and g['code_and_activation_granted'] is False,'false activation')
 chk(set(x for u in units for x in u['effect_ids'])==set(ids)and sum(len(u['effect_ids'])for u in units)==len(ids),'effects not allocated exactly once')
 chk(not cyclic(deps),'delivery cycle')
 chk({n['id']for n in g['nodes']}==set(deps),'graph node mismatch')
 chk({(e['source'],e['target'],e['relation'])for e in g['edges']}=={(d,u['id'],'requires')for u in units for d in u['depends_on']},'graph edges not projected')
 chk(all(set(e['proof_ids'])<=set(pids)for e in c['effects']),'effect missing proof')
 chk(all(e['source']['status']=='PROPOSED_NEW' or e['source'].get('git_blob_sha')for e in c['effects']),'effect missing source blob')
 chk(all(e['source']['revision']==source['revision']for e in c['effects']),'effect source revision mismatch')
 chk(all(e['source']['path'].startswith(('plasticos_','docs/adr/','tests/'))for e in c['effects']),'external owner in effects')
 paths={p['path']for e in c['effects']for p in e['paths']}
 chk(paths=={r['path']for r in ledger['rows']},'file-change ledger not derived')
 chk(len(paths)==len(ledger['rows']),'file path duplicated')
 chk(all(row['repository']=='cryptoxdog/IB-Odoo_19'for row in ledger['rows']),'external source change')
 chk(all(row['operation']=='CREATE' or row['source_blob_sha'] for row in ledger['rows']),'edited file no blob')
 chk({t['id']for t in trace['operator_locks']}=={l['id']for l in locks['locks']},'intent trace gap')
 chk(all(set(t['effects'])<=set(ids)and set(t['proofs'])<=set(pids)for t in trace['operator_locks']),'trace dangling ref')
 return err

def load_group(r):return [load(r/s)for s in ['case.json','DELIVERY/DEPENDENCY_GRAPH.json','INVARIANTS/OPERATOR_LOCKS.json','EVIDENCE/REPO_SOURCE_LOCK_CURRENT.json','PLAN/FILE_CHANGE_LEDGER.json','PLAN/SOURCE_EFFECT_TO_PROOF.json']]
def verify(root):
 parts=load_group(root);errors=check_data(*parts);s=load(root/'EVIDENCE/REPO_MANIFEST_SNAPSHOT_CURRENT.json')
 if len(s['modules'])!=s['module_count'] or s['module_count']!=30:errors.append('30-source-manifest census')
 if cyclic({m['name']:m['depends']for m in s['modules']}):errors.append('source dependency cycle')
 if (root/'EVIDENCE/PRESERVED_KERNEL.json').exists():
  for item in load(root/'EVIDENCE/PRESERVED_KERNEL.json')['files']:
   if hashfile(root/item['path'])!=item['sha256']:errors.append('original kernel changed: '+item['path'])
 if (root/'SHA256SUMS.json').exists():
  old=load(root/'SHA256SUMS.json')['sha256_by_path'];new={f.relative_to(root).as_posix():hashfile(f)for f in root.rglob('*')if f.is_file()and f.name!='SHA256SUMS.json'}
  if new!=old:errors.append('checksum manifest mismatch')
 return {'status':'PACKAGE_DECLARATION_PASS_RELEASE_BLOCKED'if not errors else 'FAIL','errors':errors,'effects':len(parts[0]['effects']),'product_proofs':'NOT_RUN','installed_runtime':'UNOBSERVED','authorization':'NOT_GRANTED'}
def negatives(root):
 orig=load_group(root);assert not check_data(*orig)
 mutations=[
 ('grant coding',lambda a:a[0]['authority']['coding_grant'].update(granted=True)),
 ('self accept',lambda a:a[0]['authority']['plan_acceptance'].update(granted=True)),
 ('promote test',lambda a:a[0]['delivery']['proofs'][0].update(status='OBSERVED_PASS')),
 ('activate',lambda a:a[1].update(code_and_activation_granted=True)),
 ('drift',lambda a:a[0]['target'].update(revision='0'*40)),
 ('external repo',lambda a:a[0]['target'].update(repository='Quantum-L9/Enrichment.Inference.Engine')),
 ('drop effect',lambda a:a[0]['delivery']['units'][0]['effect_ids'].pop()),
 ('cycle graph',lambda a:a[0]['delivery']['units'][0]['depends_on'].append('U07')),
 ('lose lock',lambda a:a[2]['locks'].pop()),
 ('lose path',lambda a:a[4]['rows'].pop()),
 ('break trace',lambda a:a[5]['operator_locks'][0].update(effects=['NOT_AN_EFFECT'])),
 ('inject external source',lambda a:a[0]['effects'][0]['source'].update(path='Quantum-L9/CEG/engine.py'))]
 results=[]
 for name,mutate in mutations:
  a=copy.deepcopy(orig);mutate(a);e=check_data(*a);assert e,name;results.append({'scenario':name,'verdict':'REJECTED','reason':e[0]})
 return {'status':'PASS_SYNTHETIC_NEGATIVE_CONTROLS','cases':results,'product_tests':'NOT_RUN'}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('root',type=Path,nargs='?',default=Path(__file__).resolve().parents[1]);p.add_argument('--negative',action='store_true');a=p.parse_args()
 try:v=negatives(a.root)if a.negative else verify(a.root)
 except Exception as ex:v={'status':'FAIL','errors':[str(ex)]}
 print(json.dumps(v,indent=2));sys.exit(0 if v['status'].startswith(('PASS','PACKAGE_DECLARATION_PASS')) else 1)
