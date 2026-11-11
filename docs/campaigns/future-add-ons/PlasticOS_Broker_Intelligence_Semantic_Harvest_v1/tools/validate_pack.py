#!/usr/bin/env python3
"""Offline semantic-harvest pack validator, no Odoo imports and no mutation."""
from __future__ import annotations
import argparse,csv,hashlib,io,json,re,sys,zipfile
from collections import Counter
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
SPECS={
 'candidates/18_broker_capabilities.jsonl':18,
 'candidates/12_rejection_meanings.jsonl':12,
 'candidates/56_coaching_scenarios.jsonl':56,
 'candidates/20_unique_coaching_patterns.jsonl':20,
 'candidates/material_inspection_requirements.jsonl':32,
 'candidates/proposed_decision_sequences.jsonl':12,
 'comparisons/pp_kb_crosswalk.jsonl':12,
 'evaluation/adversarial_acceptance_cases.jsonl':18,
 'evidence/source_scenario_index.jsonl':867,
 'evidence/media_reference_inventory.jsonl':116,
 'evidence/rejection_extension_examples.jsonl':59,
}

def data(path): return json.loads((ROOT/path).read_text(encoding='utf-8'))
def lines(path):
 values=[json.loads(row) for row in (ROOT/path).read_text(encoding='utf-8').splitlines() if row.strip()]
 assert len(values)==SPECS[path],f'{path}: {len(values)} expected {SPECS[path]}'
 return values

def check_sources(value,files):
 if isinstance(value,dict):
  if 'archive_member' in value:
   member=value['archive_member']
   assert member in files,('unregistered archive member',member)
   assert value.get('member_sha256')==files[member],('wrong source digest',member)
   if 'record_ordinal_1based' in value: assert type(value['record_ordinal_1based']) is int and value['record_ordinal_1based']>0
   if 'selector' in value: assert re.fullmatch(r'[A-Z_]+\[\d+\]',value['selector'])
  for x in value.values():check_sources(x,files)
 elif isinstance(value,list):
  for x in value:check_sources(x,files)

def check_with_donor(donor:Path,source,scenario):
 assert donor.is_file(),f'donor ZIP missing: {donor}'
 assert hashlib.sha256(donor.read_bytes()).hexdigest()==source['original_zip']['sha256'], 'original ZIP SHA mismatch'
 with zipfile.ZipFile(donor) as z:
  assert z.testzip() is None,'donor CRC failure'
  for entry in source['archive_text_members']:
   assert hashlib.sha256(z.read(entry['member'])).hexdigest()==entry['sha256'],('text member mismatch',entry['member'])
  for entry in lines('evidence/media_reference_inventory.jsonl'):
   assert hashlib.sha256(z.read(entry['member'])).hexdigest()==entry['sha256'],('media member mismatch',entry['member'])
  cache={}
  yaml_checked=0
  for record in scenario:
   source_ref=record['source']; member=source_ref['archive_member']
   if member.endswith('.csv'):
    if member not in cache:cache[member]=list(csv.DictReader(io.StringIO(z.read(member).decode('utf-8-sig'))))
    idx=source_ref['record_ordinal_1based']-1
    assert 0<=idx<len(cache[member]),('CSV record index',record['id'])
    row=cache[member][idx]
    assert (row['prompt'],row['response'])==(record['prompt'],record['response']),('CSV content mismatch',record['id'])
   elif member.endswith(('.yaml','.yml')):
    try:import yaml
    except ImportError as e:raise AssertionError('PyYAML required for optional donor YAML verification') from e
    if member not in cache:cache[member]=yaml.safe_load(z.read(member))
    m=re.fullmatch(r'([A-Z_]+)\[(\d+)\]',source_ref['selector'])
    assert m is not None,('YAML selector',record['id'])
    row=cache[member][m[1]][int(m[2])]
    assert (row['prompt'],row['response'])==(record['prompt'],record['response']),('YAML content mismatch',record['id'])
    yaml_checked+=1
   else:
    raise AssertionError(('Unrecognized record source',member))
   computed=hashlib.sha256(json.dumps(row,sort_keys=True,ensure_ascii=False).encode('utf-8')).hexdigest()
   assert record['source_record_sha256']==computed,('source row digest mismatch',record['id'])
  assert yaml_checked==168
  print('DONOR_BYTES_PASS: archive SHA, CRC, 14 source text/code files, 116 media hashes, 867 scenario identities')

def validate(*,donor_zip=None):
 schema=data('HARVEST_COVERAGE.json')
 assert schema['schema']=='plasticos-broker-semantic-harvest/v1.0-candidate'
 assert schema['status']=='CANDIDATE_READ_ONLY'
 assert schema['decisions']['core_no_autoadmit'] and schema['decisions']['no_repo_mutation']
 source=data('evidence/source_identity.json')
 assert source['beneficiary_snapshot']['Staging_revision']==schema['base_revision']
 files={entry['member']:entry['sha256'] for entry in source['archive_text_members']}
 files.update({e['member']:e['sha256'] for e in lines('evidence/media_reference_inventory.jsonl')})
 records={p:lines(p) for p in SPECS}
 for path,rs in records.items():
  check_sources(rs,files)
  if path.startswith(('candidates/','evaluation/')):
   assert len({r['id'] for r in rs})==len(rs),('duplicate identity',path)
 cap=records['candidates/18_broker_capabilities.jsonl']
 assert len({r['original_category'] for r in cap})==18
 assert sum(r['source_count'] for r in cap)==229
 codes=records['candidates/12_rejection_meanings.jsonl']
 assert len({r['code'] for r in codes})==12
 assert {r['code'] for r in codes}=={r['original_record']['code'] for r in codes}
 coaches=records['candidates/56_coaching_scenarios.jsonl']
 clusters=records['candidates/20_unique_coaching_patterns.jsonl']
 assert len({r['sop_reference'] for r in coaches})==20
 for cluster in clusters:
  ids=[r['id'] for r in coaches if r['cluster_id']==cluster['id']]
  assert sorted(ids)==sorted(cluster['scenario_ids'])
  assert cluster['scenario_count']==len(ids)
  first=next(r for r in coaches if r['id']==ids[0])
  for r in coaches:
   if r['cluster_id']==cluster['id']:
    assert r['sop_reference']==first['sop_reference']
    assert r['source_response']==first['source_response']
 assert all(r['sop_authority'].startswith('UNVERIFIED') for r in coaches)
 assert all(r['status']=='CANDIDATE_ONLY' for r in cap+codes+coaches+records['candidates/material_inspection_requirements.jsonl']+records['candidates/proposed_decision_sequences.jsonl'])
 cap_ids={r['id'] for r in cap};code_ids={r['id'] for r in codes}
 for r in records['candidates/proposed_decision_sequences.jsonl']:
  assert set(r['references']['capabilities'])<=cap_ids
  assert set(r['references']['rejection_codes'])<=code_ids
  assert 'non_authority_guard' in r
 aliases=[json.loads(l) for l in (ROOT/'comparisons/rejection_namespace_conflicts.jsonl').read_text().splitlines()]
 assert len({x['source_alias'] for x in aliases})==len(aliases)
 assert all(x['resolution'] in ('EXACT_SUFFIX_POSSIBLE_REVIEW_REQUIRED','UNKNOWN_UNRESOLVED') for x in aliases)
 assert all(e['status']=='PROPOSED_NOT_RUN' for e in records['evaluation/adversarial_acceptance_cases.jsonl'])
 assert all(e['rights_status']=='UNKNOWN' for e in records['evidence/media_reference_inventory.jsonl'])
 if donor_zip:check_with_donor(Path(donor_zip),source,records['evidence/source_scenario_index.jsonl'])
 print('STRUCTURE_PASS:',len(records),'bounded candidate/evidence sets; semantic cross-references and nonadmission gates')
 return 0

if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--donor-zip',help='Optional exact original ZIP for independent byte and CSV identity verification')
 args=parser.parse_args()
 try: sys.exit(validate(donor_zip=args.donor_zip))
 except (AssertionError,KeyError,ValueError,IOError,zipfile.BadZipFile) as ex:
  print('VALIDATION_FAILED:',ex,file=sys.stderr)
  sys.exit(1)
