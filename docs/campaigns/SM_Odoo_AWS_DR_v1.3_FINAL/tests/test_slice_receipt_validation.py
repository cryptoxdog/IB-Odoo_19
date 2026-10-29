import sys
from pathlib import Path
import unittest
try:
    import yaml
except ImportError:
    yaml=None
sys.path.insert(0,str(Path(__file__).resolve().parents[1] / 'tools'))
if yaml:
    from validate_slice_receipt import check

@unittest.skipUnless(yaml is not None, 'PyYAML is needed for receipt validation')
class ReceiptTests(unittest.TestCase):
    def base(self):
        p=Path(__file__).resolve().parents[1]/'coordination/SLICE_RECEIPT_TEMPLATE.yaml'
        x=yaml.safe_load(p.read_text('utf-8'))
        x['contract_id']='03'; x['status']='PASS'; x['observation_utc']='2026-10-29T00:00:00Z'
        x['contract_revision_sha256']='a'*64
        x['source']['repository_sha']='b'*40
        x['validation']['observed_real_checks']=['private://real-observation-1']
        x['validation']['observed_negative_tests']=['private://denied-action-1']
        x['validation']['actual_deployed_recovery_release_digest']='c'*64
        x['validation']['independent_restore_reference']='private://real-restore'
        x['validation']['immutable_dependency_closed']=True
        x['validation']['verified_protected_s3_versions']=['private://s3-version-1']
        x['handoff']['private_evidence_repository_reference']='private://receipts/03'
        x['handoff']['independent_consumer_ready']=True
        x['handoff']['tested_capability_level']='INDEPENDENT_DAILY'
        x['handoff']['cleanup_and_rotation_complete']=True
        return x
    def test_fixture_passes_structural_only(self):
        self.assertTrue(check(self.base()))
    def test_unknown_restoration_fails(self):
        x=self.base(); x['validation']['independent_restore_reference']='UNKNOWN'
        with self.assertRaises(AssertionError):check(x)
    def test_open_issue_fails(self):
        x=self.base();x['handoff']['open_in_scope_items']=['TODO']
        with self.assertRaises(AssertionError):check(x)
    def test_blocked_is_not_pass(self):
        x=self.base();x['status']='BLOCKED_EXTERNAL';x['handoff']['externally_blocked_items']=[]
        with self.assertRaises(AssertionError):check(x)
    def test_hourly_contract_cannot_pass_as_daily(self):
        x=self.base();x['contract_id']='04'
        with self.assertRaises(AssertionError):check(x)
if __name__=='__main__':unittest.main()
