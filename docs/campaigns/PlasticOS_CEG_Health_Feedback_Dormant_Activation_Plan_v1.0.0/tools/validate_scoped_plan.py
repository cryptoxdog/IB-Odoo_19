#!/usr/bin/env python3
"""Validate declared health plan only. No repo execution or operator admission."""
from __future__ import annotations
import argparse, hashlib, importlib.util, json, sys
from pathlib import Path

R = Path(__file__).resolve().parents[1]
GOVERNED = {
    'Quantum-L9/Cognitive.Engine.Graphs': '0d84ec8531baf604383c5ddc012f40aa84fc4b76',
    'Quantum-L9/Constellation.Gate': 'cfeb81fa4d11eb8c106314fa27310f660a1dfad7',
    'Quantum-L9/Enrichment.Inference.Engine': '3f96eda98240789963b0e6534aa2151aed12658e',
}

def load(name):return json.loads((R/name).read_text(encoding='utf8'))

def declared_checks(case,eff,dag,locks,activation,proofs,refs):
    errors=[]
    def require(ok,msg):
        if not ok: errors.append(msg)
    target=activation['required_current_deployment_target']
    flag_set={'HEALTH_API_ENABLED','AUTO_ENRICH_VIA_GATE','GRAPH_INFERENCE_FEEDBACK_ENABLED'}
    require(set(target)==flag_set and all(v is False for v in target.values()),'current required OFF flags changed')
    future=activation['desired_future_state_after_separate_approval']
    require(set(future)==flag_set and all(v is True for v in future.values()),'future desired scope changed')
    require(activation['business_use_enabled'] is False and activation['pack_makes_config_change'] is False,'premature activation/configuration')
    require(activation['code_defaults_preserved_false'] is True,'code default no longer false')
    require(activation['separate_activation_grant'] is None and activation['authorization']=='NONE','false operator authorization')
    require(activation['all_proofs']=='NOT_RUN','false runtime proof claim')
    require(case['authority']['coding_grant']['granted'] is False and case['authority']['plan_acceptance']['granted'] is False,'false coding/plan grant')
    require(set(GOVERNED)=={r['repository'] for r in refs['repositories']},'unpermitted repository')
    require(all(r['revision']==GOVERNED[r['repository']] for r in refs['repositories']),'source revision mismatch')
    invar=locks['locks']; ids=[a['id'] for a in invar]
    require(len(ids)==18 and set(ids)=={'H-'+str(i).zfill(2) for i in range(1,19)} and len(ids)==len(set(ids)),'invariant IDs absent/duplicated')
    require(all(q['status']=='OPERATOR_SCOPE_AND_PROPOSED_SAFETY_INVARIANT' for q in invar),'new invariant authority invented')
    nodes={n['id']:n for n in dag['nodes']}
    require(len(nodes)==len(dag['nodes']) and len(nodes)==9,'missing/duplicate delivery node')
    prereq={x:[] for x in nodes}
    for e in dag['edges']:
        if e['source'] not in nodes or e['target'] not in nodes: errors.append('dangling graph dependency');continue
        require(e['relation']=='requires','wrong graph relation')
        prereq[e['target']].append(e['source'])
    visiting=set();memo={}
    def ancestors(node):
        if node in visiting:errors.append('delivery graph cycle: '+node);return set()
        if node in memo:return set(memo[node])
        visiting.add(node);v=set(prereq[node])
        for p in prereq[node]:v|=ancestors(p)
        visiting.remove(node);memo[node]=set(v);return v
    closure={n:ancestors(n) for n in nodes}
    require('U00' in closure['U08'] and 'U07' in closure['U08'],'readiness before earlier proof')
    require('U03' in closure['U04'] and 'U02' in closure['U04'],'dispatch before route/scan')
    eids=[e['id'] for e in eff['effects']];require(len(eids)==len(set(eids)) and len(eids)==24,'effect census missing/duplicated')
    ids=set(eids)
    proofids={p['id'] for p in proofs['proofs']}
    require(len(proofids)==21 and len(proofs['proofs'])==21,'proof census incomplete')
    require(all(p['status']=='NOT_RUN' for p in proofs['proofs']) and proofs['status']=='NOT_RUN','product test status invented')
    unit_map={e['id']:e['unit'] for e in eff['effects']}
    for e in eff['effects']:
        require(e['repository'] in GOVERNED and e['revision']==GOVERNED[e['repository']], 'effect wrong repo/revision '+e['id'])
        require(set(e['proof_ids'])<=proofids,'effect missing proof '+e['id'])
        require(e['disposition'] in ('EDIT','NO_CHANGE'),'effect disposition invalid '+e['id'])
        if e['disposition']=='NO_CHANGE':require(bool(e['no_change_basis']) and not e['paths'],'no-change unjustified '+e['id'])
        else:require(bool(e['paths']),'edit lacks path '+e['id'])
        for d in e['depends_on']:
            if d not in ids:errors.append('missing predecessor '+e['id']);continue
            require(unit_map[d]==e['unit'] or unit_map[d] in closure[e['unit']],f'out-of-order cross-unit predecessor {e["id"]}<-{d}')
    caseids={e['id'] for e in case['effects']};require(caseids=={e['id'] for e in eff['effects'] if e['owner']=='CEG'},'CEG case effect mismatch')
    alloc=[i for u in case['delivery']['units'] for i in u['effect_ids']]
    require(caseids==set(alloc) and len(caseids)==len(alloc),'CEG case effect allocation incomplete')
    require({p['id'] for p in case['delivery']['proofs']}==proofids,'proof matrix and case mismatch')
    require(all(e['id'] in caseids for e in case['effects']),'case outside CEG')
    require('Odoo' in str(case['strategy']['deferred']) and 'Offer Drafting' in str(case['strategy']['deferred']), 'scope exclusion missing')
    return errors

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--no-schema',action='store_true');args=parser.parse_args()
    case=load('CASE/case.json'); effects=load('PLAN/EFFECTS.json');dag=load('PLAN/DELIVERY_GRAPH.json');locks=load('PLAN/LOCKS.json');activation=load('PLAN/ACTIVATION_STATE.json');proofs=load('PLAN/PROOF_MATRIX.json');refs=load('EVIDENCE/REVISIONS.json')
    errs=declared_checks(case,effects,dag,locks,activation,proofs,refs)
    if not args.no_schema:
        p=R/'PLANNING_KERNEL/tools/validate_case.py';spec=importlib.util.spec_from_file_location('scoped_case_schema',p);module=importlib.util.module_from_spec(spec);assert spec and spec.loader;spec.loader.exec_module(module)
        errs += ['case schema '+e for e in module.schema_errors(case)]
    for p in ['README.md','EXECUTIVE_BRIEF.md','INVARIANTS/HEALTH_KERNEL.md','PLAN/WHOLE_CHANGE_PLAN.md','PLAN/WIRING_AND_CONTRACTS.md','ADRS/ADR-CEG-HEALTH-DORMANT.md','ADRS/ADR-GATE-HEALTH-OWNERSHIP.md','ADRS/ADR-EIE-RETURN-RELIABILITY.md','DELIVERY/EXECUTION_GATES.md','DELIVERY/TEST_AND_ROLLBACK.md','EVIDENCE/READINESS_ASSESSMENT.md']:
        if not (R/p).is_file():errs.append('missing narrative '+p)
    sumfile=R/'SHA256SUMS.json'
    if sumfile.exists():
        hashes=load('SHA256SUMS.json')['sha256_by_path']
        actual={f.relative_to(R).as_posix():hashlib.sha256(f.read_bytes()).hexdigest() for f in R.rglob('*') if f.is_file() and f!=sumfile}
        if hashes!=actual:errs.append('checksum manifest mismatch')
    result={'status':'PASS_PACKAGE_DECLARED_STRUCTURE_ONLY' if not errs else 'FAIL','errors':errs,'effect_groups':len(effects['effects']),'proof_obligations':len(proofs['proofs']),'delivery_units':len(dag['nodes']),'lock_count':len(locks['locks']),'code_tests':'NOT_RUN','multi_node_proof':'NOT_RUN','independent_acceptance':'NOT_RUN','deployed_state':'UNKNOWN','activation':'NOT_AUTHORIZED'}
    print(json.dumps(result,indent=2))
    return 0 if not errs else 1
if __name__=='__main__':sys.exit(main())
