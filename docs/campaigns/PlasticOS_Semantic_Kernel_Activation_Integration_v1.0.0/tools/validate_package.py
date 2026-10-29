#!/usr/bin/env python3
"""Package-only integrity. Never grants source completeness or product/runtime acceptance."""
from __future__ import annotations
import argparse, hashlib, importlib.util, json, re, sys
from pathlib import Path

def load(path: Path):
    return json.loads(path.read_text(encoding='utf-8'))

def cycle(graph: dict[str,list[str]]) -> bool:
    state={}
    def visit(node):
        if state.get(node)==1:return True
        if state.get(node)==2:return False
        state[node]=1
        if any(visit(p) for p in graph.get(node,[]) if p in graph):return True
        state[node]=2
        return False
    return any(visit(n) for n in graph)

def records_errors(c,x,g,a,trace):
    errors=[]
    def need(v,msg):
        if not v:errors.append(msg)
    effects=c['effects']+x['effects'];ids=[e['id']for e in effects]
    pids={p['id']for p in c['delivery']['proofs']}
    need(len(ids)==len(set(ids)),'duplicate effect')
    need(all(set(e['proof_ids'])<=pids for e in effects),'dangling proof')
    need(all(p['status']=='NOT_RUN' for p in c['delivery']['proofs']),'unexecuted product proof claimed run')
    need(c['authority']['coding_grant']['granted'] is False,'unexpected coding grant')
    need(c['authority']['plan_acceptance']['granted'] is False,'self-admitted implementation plan')
    need(a['production_enabled'] is False and a['production_operator_approved'] is False,'production activation')
    need(a['final_activation_grant'] is None,'fabricated activation grant')
    need(a['runtime_proofs']=='NOT_RUN','runtime claim')
    nodes={n['id']:n for n in g['nodes']}
    need(len(nodes)==len(g['nodes']),'duplicate graph node')
    deps={n:[]for n in nodes}
    for e in g['edges']:
        if e['source']not in nodes or e['target']not in nodes:errors.append('dangling graph edge');continue
        need(e['relation']=='requires','unexpected relation')
        deps[e['target']].append(e['source'])
    need(not cycle(deps),'cyclic graph')
    def ancestors(n):
        seen=set();todo=list(deps.get(n,[]))
        while todo:
            p=todo.pop()
            if p not in seen:seen.add(p);todo.extend(deps.get(p,[]))
        return seen
    allocations=[i for n in g['nodes']for i in n['effects']]
    need(set(allocations)==set(ids) and len(allocations)==len(ids),'effect allocation not exactly once')
    unit={e:n['id'] for n in g['nodes']for e in n['effects']}
    for e in effects:
        for p in e.get('depends_on',[]):
            need(p in unit,'unknown effect predecessor')
            if p in unit and e['id'] in unit:
                need(unit[p]==unit[e['id']] or unit[p]in ancestors(unit[e['id']]),'effect ordering '+e['id']+' <- '+p)
    need('U11'in ancestors('U12') and 'U10'in ancestors('U12'),'activation before staging/verification')
    need({d['id']for d in c['authority']['locked_decisions']}=={r['decision']for r in trace['coverage']},'intent coverage')
    for row in trace['coverage']:
        need(set(row['effect_ids'])<=set(ids),'trace effect missing')
        need(set(row['proof_ids'])<=pids,'trace proof missing')
    return errors

def validate(root: Path):
    c=load(root/'case.json');x=load(root/'PLAN/CROSS_REPO_PLAN.json');g=load(root/'PLAN/DELIVERY_GRAPH.json');a=load(root/'PLAN/ACTIVATION_STATE.json');trace=load(root/'PLAN/INTENT_TRACE.json')
    errors=records_errors(c,x,g,a,trace)
    k=root/'PLANNING_KERNEL'
    spec=importlib.util.spec_from_file_location('supplied_kernel',k/'tools/validate_case.py')
    module=importlib.util.module_from_spec(spec);assert spec and spec.loader;spec.loader.exec_module(module)
    schema=module.schema_errors(c);errors.extend('schema: '+s for s in schema)
    gate=module.check(c,'plan')
    expected={'TARGET_ENV_UNKNOWN','OPEN_OPERATOR_DECISIONS','UNEXPLORED_DYNAMIC_CONSUMERS'}
    if set(gate)!=expected:errors.append('unexpected kernel gate disposition: '+repr(gate))
    p=load(root/'EVIDENCE/PREDECESSOR_COMPARISON.json')
    for m in p['members']:
        q=root/m['delivered_path']
        if not q.is_file() or hashlib.sha256(q.read_bytes()).hexdigest()!=m['sha256']:errors.append('kernel preservation: '+m['delivered_path'])
    dag=load(root/'PLAN/PROSPECTIVE_MODULE_DAG.json')
    graph={m['name']:m['depends']for m in dag['baseline_modules']}
    for m in dag['proposed_modules']:graph[m['name']]=m['depends']+list(m.get('conditional_dependency',{}))
    if cycle(graph):errors.append('prospective addon cycle')
    for m in dag['baseline_modules']:
        if 'plasticos_semantic_bridge'in m['depends']:errors.append('mandatory bridge dependency')
    prohibited=''.join(map(chr,[99,105,101,116,114,97,100,101]))
    for f in root.rglob('*'):
        if not f.is_file():continue
        name=f.relative_to(root).as_posix()
        if f.is_symlink():errors.append('symlink: '+name)
        raw=f.read_bytes()
        if prohibited in name.casefold() or prohibited.encode()in raw.lower():errors.append('BAN001 package content/path: '+name)
        if re.search(rb'(?:github_pat_|ghp_)[A-Za-z0-9_]{20,}|[?&]token=[A-Za-z0-9_-]{20,}|-----BEGIN (?:RSA )?PRIVATE KEY-----',raw):errors.append('possible secret: '+name)
    sums=root/'SHA256SUMS.json'
    if sums.exists():
        sm=load(sums)['sha256_by_path']
        actual={f.relative_to(root).as_posix():hashlib.sha256(f.read_bytes()).hexdigest()for f in root.rglob('*')if f.is_file() and f!=sums}
        if sm!=actual:errors.append('checksum coverage/content mismatch')
    return {'status':'PASS_STRUCTURAL_WITH_RELEASE_BLOCKED'if not errors else 'FAIL','errors':errors,'schema':'PASS'if not schema else 'FAIL','kernel_plan_gate':{'status':'FAIL','errors':gate,'interpretation':'Expected material-frontier refusal; not execution readiness.'},'effects':len(c['effects'])+len(x['effects']),'proof_obligations':len(c['delivery']['proofs']),'delivery_units':len(g['nodes']),'preserved_kernel_members':len(p['members']),'plan_digest':module.plan_digest(c),'independent_semantic_acceptance':'NOT_RUN','runtime':'NOT_RUN','production_activation':'NOT_AUTHORIZED'}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('root',nargs='?',type=Path,default=Path(__file__).resolve().parents[1]);args=parser.parse_args()
    try:result=validate(args.root)
    except Exception as exc:result={'status':'FAIL','errors':[str(exc)]}
    print(json.dumps(result,indent=2));return 0 if result['status']=='PASS_STRUCTURAL_WITH_RELEASE_BLOCKED'else 1
if __name__=='__main__':sys.exit(main())
