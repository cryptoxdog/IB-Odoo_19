#!/usr/bin/env python3
"""Synthetic negative-control tests. No Odoo source, Enterprise runtime or independent review."""
import copy, json, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from validate_case import check, plan_digest, reverse_dependents
ROOT=Path(__file__).resolve().parents[1]
rev='677d734fd88615d673501d91de88734b7150ff50'
snapshot=json.loads((ROOT/'SOURCES/REPO_MANIFEST_SNAPSHOT.json').read_text())
base=json.loads((ROOT/'TEMPLATES/CASE.template.json').read_text())

def fixture(mode='new_addon'):
 c=copy.deepcopy(base)
 c['mode']=mode;c['case_id']='SYNTHETIC_DECLARATIONS_NOT_PROOF'; c['target']['revision']=rev
 c['target']['installed_target']={'status':'EVIDENCED_EXCLUSION','evidence':'SYNTHETIC EXCLUSION FOR STRUCTURAL TEST ONLY'}
 c['authority']['locked_decisions']=[{'id':'SYN','text':'Structural fixture must not change real repos','source':'SYNTHETIC'}]
 c['strategy'].update({'user_problem':'test case structure','outcome':'exercised declared validator','first_proof':'negative checks','best_alternative':'do nothing','reason_selected':'only test mechanics','reversibility':'delete synthetic data','future_seam':'none','now_scope':['synthetic'],'non_goals':['no code'],'native_fit':[{'capability':'fixture','decision':'REUSE','owner':'synthetic','source':'synthetic'}]})
 c['source_census'].update({'search_scope':'synthetic module enumeration','methods':['synthetic manifest consumer traversal'],'root_modules':['plasticos_logistics'],'runtime_consumers':{'status':'EVIDENCED_EXCLUSION','evidence':'SYNTHETIC only; no runtime touched'}})
 c['source_census']['module_dispositions']=[{'module':m,'disposition':'NO_CHANGE','reason':'synthetic only','evidence':'synthetic fixture witness','test_obligation':'reject if omitted'} for m in sorted(reverse_dependents(['plasticos_logistics'],snapshot))]
 for x in c['invariants']['constitutional']:
  x['status']='APPLIES' if x['id']=='BAN001' else 'CONDITIONAL';x['basis']='SYNTHETIC relevance only';x['evidence']='synthetic fixture'
 c['invariants']['candidate_screening']={'source':'SOURCES/ODOO_INVARIANTS_v3.4.0_DRAFT_r2.md','status':'SCREENED','relevant_ids':['POS-INV-26'] if False else ['POS-INV-02'],'basis':'SYNTHETIC screening; POS26 separately mandated'}
 c['effects']=[{'id':'E-1','owner':'plasticos_logistics','consumer':'synthetic consumer','source':{'path':'synthetic/source.py','revision':rev,'status':'OBSERVED','evidence':'SYNTHETIC only'},'reachability':['SYNTHETIC -> downstream'],'before':'old synthetic state','after':'new synthetic state','disposition':'EDIT','paths':[{'path':'plasticos_logistics/models/synthetic.py','operation':'EDIT'}],'no_change_basis':'','migration':'synthetic none','recovery':'synthetic restore','security_impact':'none in synthetic fixture','proof_ids':['T-1'],'depends_on':[],'invalidators':['new source revision']}]
 c['delivery']={'units':[{'id':'P1','description':'synthetic unit','effect_ids':['E-1'],'depends_on':[]}],'proofs':[{'id':'T-1','stage':'POSTCODE','positive':'synthetic path works','negative':'synthetic path fails closed','owner':'synthetic','status':'NOT_RUN','evidence':''}],'migration_plan':'synthetic no production data','recovery_plan':'synthetic revert','release_boundary':'not a release'}
 c['readiness']['state']='PLAN_REVIEW'
 if mode=='wip_alignment':
  c['target']['wip']={'base_revision':rev,'head_revision':rev,'test_evidence':'SYNTHETIC no real tests','related_prs':[],'capabilities':[{'name':'synthetic old behavior','behavior':'preserve fake capability','disposition':'PRESERVE','evidence':'SYNTHETIC fixture','preservation_test':'run synthetic preservation check'}]}
 return c

def must_fail(label,fn):
 c=fixture();fn(c);errors=check(c)
 assert errors,label+' unexpectedly passed'
 print('PASS negative:',label,'->',errors[0][:110])

def main():
 for mode in ('new_addon','wip_alignment'):
  c=fixture(mode)
  assert not check(c),mode+' baseline failed '+repr(check(c))
  assert check(c,'precode'), 'Offline tool must never authorize code'
  print('PASS synthetic declared accounting:',mode,'; offline precode refused')
 must_fail('unassessed active constitutional invariant',lambda c:c['invariants']['constitutional'][0].update(status='UNASSESSED'))
 must_fail('BAN001 excluded',lambda c:c['invariants']['constitutional'][-1].update(status='NOT_APPLICABLE_WITH_EVIDENCE'))
 must_fail('operator blast-radius gate disabled',lambda c:c['authority']['operator_blast_radius_gate'].update(applies=False))
 must_fail('draft masquerades as constitution',lambda c:c['target']['constitution'].update(blob_sha='f'*40))
 must_fail('missing reverse-dependent module',lambda c:c['source_census']['module_dispositions'].pop())
 must_fail('duplicate reverse-dependent module',lambda c:c['source_census']['module_dispositions'].append(c['source_census']['module_dispositions'][0]))
 must_fail('unobserved installed target',lambda c:c['target']['installed_target'].update(status='UNOBSERVED'))
 must_fail('unknown runtime consumers',lambda c:c['source_census']['runtime_consumers'].update(status='UNOBSERVED'))
 must_fail('missing effect owner',lambda c:c['effects'][0].update(owner=''))
 must_fail('missing effect source revision',lambda c:c['effects'][0]['source'].update(revision=''))
 must_fail('source revision drift',lambda c:c['target'].update(revision='f'*40))
 must_fail('unplanned file change',lambda c:c['effects'][0].update(paths=[]))
 must_fail('unaccounted effect',lambda c:c['effects'].append(dict(c['effects'][0],id='E-2')))
 must_fail('missing migration',lambda c:c['effects'][0].update(migration=''))
 must_fail('missing recovery',lambda c:c['effects'][0].update(recovery=''))
 must_fail('missing negative proof',lambda c:c['delivery']['proofs'][0].update(negative=''))
 must_fail('unknown proof ID',lambda c:c['effects'][0].update(proof_ids=['MISSING']))
 must_fail('unresolved business decision',lambda c:c['authority'].update(open_material_decisions=['must choose money owner']))
 must_fail('unjustified no change',lambda c:c['effects'][0].update(disposition='NO_CHANGE',paths=[],no_change_basis=''))
 must_fail('missing stage assignment',lambda c:c['delivery']['units'][0].update(effect_ids=[]))
 must_fail('ghost dependency',lambda c:c['effects'][0].update(depends_on=['E-missing']))
 must_fail('schema unknown property',lambda c:c.update(phantom_property=True))
 c=fixture();d=plan_digest(c);c['authority']['plan_acceptance']={'granted':True,'digest':d,'basis':'SYNTHETIC'};c['authority']['coding_grant']={'granted':True,'digest':d,'scope':'SYNTHETIC'}
 assert any('EXTERNAL_AUTHENTICATION_REQUIRED' in err for err in check(c,'precode')), 'Fabricated JSON cannot authenticate authority'
 c['effects'][0]['after']='changed after approval'
 assert any('UNAUTHENTICATED_OR_STALE_GRANT' in err for err in check(c,'precode')), 'Changed plan digest failed to invalidate old declared grant'
 print('PASS fake authorization rejected and plan changes invalidate digest')
 # Migrate old template? It remains an intentionally incompatible candidate; no silent conversion.
 assert check(base), 'Blank case must fail closed'
 print('RESULT: synthetic structural tests PASS, REAL WORLD VALIDATION NOT_RUN')
if __name__=='__main__':main()
