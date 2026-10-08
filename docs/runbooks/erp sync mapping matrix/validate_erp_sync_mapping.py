#!/usr/bin/env python3
"""Validate candidate ERP Sync mapping shape and locked consistency.

This validates pack content, not live SQL facts or Odoo realization.
Run only under an authorized validation contract; the standing agent prompt grants no execution authority.
"""
from __future__ import annotations
import json, sys, re
from pathlib import Path

REQUIRED_RULES = {f"ERP-{x:03}" for x in range(1,20)}
REQUIRED_TABLES = {"WKSDetail", "PO", "PODetail", "BuySell", "Referrer"}

def check(path: Path) -> None:
 d=json.loads(path.read_text(encoding="utf-8"))
 errors=[]
 def require(condition, desc):
  if not condition:errors.append(desc)
 require(d.get('schema_id')=='erp-sync-field-mapping/v1','bad schema id')
 require(d.get('pack_status')=='proposal_until_adopted','must not claim accepted authority')
 require(d.get('integration_base')=='Staging','wrong integration base')
 rules=d.get('rule_set',[])
 ids=[r.get('id') for r in rules]
 require(len(ids)==len(set(ids)) and set(ids)==REQUIRED_RULES,'incomplete/duplicate mandatory rule inventory')
 cat=d.get('field_catalog',[])
 require(len(cat)==152,'field_catalog must keep the 147 v10 rows plus the five operator revisions')
 require([r.get('id') for r in cat]==[f'v10-row-{i}' for i in range(2,154)],'field catalog row identity/order drift')
 blob=json.dumps(cat)
 require('plasticos.transaction' not in blob and 'plasticos.load' not in blob,'custom transaction or load target remains')
 by={(x['source']['table'].split(' (')[0], x['source']['field']): x for x in cat}
 require(by[('BuySell','ProblemNotes')]['target_candidate']['field']=='note','sticky note target drifted')
 require(by[('BuySell','Notes')]['target_candidate']['field']=='note','speech-bubble target drifted')
 require(by[('PO','PriceBasis where Source=SO')]['target_candidate']['field']=='incoterm','sale incoterm target drifted')
 require(by[('PO','PriceBasis where Source=PO')]['target_candidate']['field']=='incoterm_id','purchase incoterm target drifted')
 require(by[('WksDelivery','TrailerNo')]['target_candidate']['field']=='carrier_tracking_ref','trailer target drifted')
 gl=d.get('execution_revision',{}).get('gl_account_crosswalk',{})
 cogs=gl.get('cost_of_goods_sold',{})
 require(gl.get('rule','').startswith('The source account code is a lookup'),'GL cell values must stay a lookup')
 require(cogs.get('Material Cost',{}).get('source_name')=='Purchases','material account map drifted')
 require(cogs.get('Freight Cost',{}).get('source_name')=='Inland Freight','freight account map drifted')
 for x in cat:
  require(isinstance(x.get('source'),dict) and bool(x['source'].get('table')) and bool(x['source'].get('field')),'invalid source for '+str(x.get('id')))
  require(x.get('tier') in {'excluded','external_owner','sql_reported_impl_pending','candidate_direct','candidate_review'},'bad tier '+str(x.get('id')))
 source_tables={x['source']['table'].split(' (')[0] for x in cat}
 require(REQUIRED_TABLES<=source_tables,'missing required ERP source tables')
 require(d.get('cutoffs',{}).get('commission_paid_settled_display_before')=='2026-06-01','commission cutoff changed')
 require(d.get('cutoffs',{}).get('null_date')=='exception','missing date must be exception')
 ex=d.get('historical_exclusions',{})
 require(ex.get('tables')==['PrepayLedger'],'legacy exclusion broadened')
 require(ex.get('batch_predicate')=='PayablesBatch.PrePay=1','prepay batch predicate changed')
 require(ex.get('import_linked_ordinary_documents') is True,'linked normal business documents must be retained')
 require(ex.get('reported_prepaid_ledger_count')==41 and ex.get('reported_flagged_batch_count')==38,'expected observed prepay census changed')
 weights=d.get('weight_authority',{})
 require('SWeight' in weights.get('sales_actual',[]) and 'PWeight' in weights.get('purchase_actual',[]),'worksheet actual quantity removed')
 require('PODetail.Weight' in weights.get('excluded_placeholder',[]),'placeholder reintroduced')
 joins=d.get('joins',[])
 require(any(j.get('left')=='WKSDetail.SPO_ID' and j.get('right')=='PODetail.PO_ID' and 'PO.POID' in j.get('forbidden',[]) for j in joins),'SO join regression')
 require(any(j.get('left')=='WKSDetail.PPO_ID' and j.get('right')=='PODetail.PO_ID' for j in joins),'PO join regression')
 require(d.get('owner_boundaries',{}).get('quickbooks','').startswith('historical customer and vendor payments'),'QB settlement authority changed')
 data=path.read_bytes()
 forbidden=bytes([99,105,101,116,114,97,100,101])
 require(forbidden not in data.lower(),'repository prohibited identifier in mapping')
 if errors:
  for e in errors:print('FAIL:',e)
  raise SystemExit(1)
 print(f'PASS: {len(rules)} invariant rules, {len(cat)} mapped candidate rows, core scope/joins/cutoffs/exclusions consistent')
 print('LIMIT: Does not execute SQL or Odoo; is not importer or financial-cutover proof.')

if __name__=='__main__':
 check(Path(sys.argv[1]) if len(sys.argv)>1 else Path(__file__).with_name('erp_sync_mapping_v1.json'))
