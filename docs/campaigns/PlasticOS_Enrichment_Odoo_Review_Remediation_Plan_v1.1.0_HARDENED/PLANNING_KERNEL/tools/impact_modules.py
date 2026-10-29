#!/usr/bin/env python3
"""Enumerate declared dependency dependents (not a complete code/runtime census)."""
import argparse,json
from pathlib import Path
from validate_case import reverse_dependents
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser()
p.add_argument('--roots',nargs='+',required=True)
p.add_argument('--snapshot',type=Path,default=ROOT/'SOURCES/REPO_MANIFEST_SNAPSHOT.json')
a=p.parse_args()
obj=json.loads(a.snapshot.read_text())
known={m['name'] for m in obj['modules']}
unknown=set(a.roots)-known
if unknown:p.error('Unknown root modules in frozen snapshot: '+str(sorted(unknown)))
print(json.dumps({'source_revision':obj['revision'],'roots':a.roots,'reverse_manifest_candidates':sorted(reverse_dependents(a.roots,obj)),'limitations':'Declared reverse depends only, not Python/XML/SQL/mail/cron/Enterprise database or code-level reachability'},indent=2))
