#!/usr/bin/env python3
"""Inspect pack contents and provenance; structural validation only."""
import hashlib,json,sys,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def sha(data):return hashlib.sha256(data).hexdigest()
def validate():
    m=json.loads((ROOT/'MANIFEST.json').read_text())
    manifest_paths={x['path'] for x in m['files']}
    actual={str(x.relative_to(ROOT)) for x in ROOT.rglob('*') if x.is_file() and '__pycache__' not in x.parts and x.name!='MANIFEST.json'}
    errors=[]
    if manifest_paths!=actual:errors.append('manifest coverage difference: '+str(sorted(manifest_paths^actual)))
    for x in m['files']:
        data=(ROOT/x['path']).read_bytes()
        if len(data)!=x['size'] or sha(data)!=x['sha256']:errors.append('changed file: '+x['path'])
    lock=json.loads((ROOT/'SOURCES/REPO_SOURCE_LOCK.json').read_text())
    draft=ROOT/lock['candidate_invariant_source']['path']
    if sha(draft.read_bytes())!=lock['candidate_invariant_source']['sha256']:errors.append('altered preserved draft')
    ms=json.loads((ROOT/'SOURCES/REPO_MANIFEST_SNAPSHOT.json').read_text())
    if ms['module_count']!=30 or len({x['name'] for x in ms['modules']})!=30:errors.append('module census not 30')
    # Check exact prohibition via ASCII code points without embedding forbidden literal.
    token=bytes([99,105,101,116,114,97,100,101])
    for f in actual|{'MANIFEST.json'}:
        if token in f.lower().encode() or token in (ROOT/f).read_bytes().lower():errors.append('forbidden tracked content/path: '+f)
    return {'status':'PASS' if not errors else 'FAIL','files':len(m['files']),'manifest_complete':manifest_paths==actual,'original_draft_sha256':sha(draft.read_bytes()),'repo_revision':lock['revision'],'module_count':ms['module_count'],'errors':errors,'proof_limit':'Integrity and declared sources only; not current remote, installed Enterprise or business behavior.'}
if __name__=='__main__':
    r=validate();print(json.dumps(r,indent=2));sys.exit(0 if r['status']=='PASS' else 1)
