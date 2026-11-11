import ast
import hashlib
import json
import unittest
from collections import Counter
from pathlib import Path
from xml.etree import ElementTree as ET

BASE = Path(__file__).resolve().parents[1]
H = BASE / 'source_catalog/semantic_harvest_v1'


class HarvestIntegrityTest(unittest.TestCase):
    def test_original_file_manifest_is_preserved(self):
        for line in (H / 'FILE_MANIFEST.sha256').read_text().splitlines():
            sha, path = line.split('  ', 1)
            self.assertEqual(hashlib.sha256((H / path).read_bytes()).hexdigest(), sha, path)

    def test_source_scenario_count(self):
        self.assertEqual(len((H / 'evidence/source_scenario_index.jsonl').read_text().splitlines()), 867)

    def test_rejection_aliases_remain_unresolved(self):
        aliases = [json.loads(x) for x in (H / 'comparisons/rejection_namespace_conflicts.jsonl').read_text().splitlines()]
        self.assertEqual(len(aliases), 28)
        self.assertTrue(all(x['resolution'] != 'APPROVED' for x in aliases))

    def test_56_coach_scenarios_are_retained(self):
        self.assertEqual(len((H / 'candidates/56_coaching_scenarios.jsonl').read_text().splitlines()), 56)

    def test_harvest_counts(self):
        coverage = json.loads((H / 'HARVEST_COVERAGE.json').read_text())['counts']
        for k, n in [('capabilities',18), ('rejection_code_meanings',12), ('coach_distinct_patterns',20),
                     ('inspection_concerns',32), ('candidate_sequences',12), ('source_scenarios',867),
                     ('namespace_conflict_aliases',28), ('evaluation_cases',18)]:
            self.assertEqual(coverage[k], n)

    def test_exactly_106_initial_drafts(self):
        doc = ET.parse(BASE / 'plasticos_broker_intelligence/data/knowledge_drafts.xml').getroot()
        rows = doc.findall('record')
        self.assertEqual(len(rows),106)
        self.assertEqual(doc.attrib.get('noupdate'),'1')
        for r in rows:
            fields = {x.attrib['name']: x.text for x in r.findall('field')}
            self.assertNotIn('state',fields)
            self.assertEqual(len(fields['source_sha256']),64)
            self.assertEqual(fields['stable_key'], fields['source_candidate_id'])

    def test_every_admission_key_unique(self):
        register = json.loads((BASE / 'source_catalog/candidate_admission_register.json').read_text())
        keys = [x['id'] for x in register['candidates']]
        self.assertEqual(len(keys),len(set(keys)))
        self.assertEqual(sum(register['loaded_as_draft'].values()),106)

    def test_every_manifest_is_optional(self):
        roots = ['plasticos_broker_intelligence','plasticos_broker_intelligence_mack',
                 'plasticos_broker_intelligence_web_leads','plasticos_broker_intelligence_rejections']
        for root in roots:
            d = ast.literal_eval((BASE / root / '__manifest__.py').read_text())
            self.assertFalse(d['auto_install'])
            self.assertTrue(d['installable'])
            self.assertTrue((BASE / root / '__init__.py').exists())
            for f in d['data']:
                self.assertTrue((BASE / root / f).is_file(), f'{root}/{f}')

    def test_there_is_no_second_zip_baseline_fabrication(self):
        report = json.loads((BASE / 'source_catalog/candidate_admission_register.json').read_text())
        self.assertEqual(report['open_pr_count_observed'],0)
        self.assertEqual(report['staging_sha'], 'c2c72bc36d6201d4114531a8f666c411db612f64')


if __name__ == '__main__':
    unittest.main()
