\set ON_ERROR_STOP on
\pset format unaligned
\pset tuples_only on
\echo # markers
SELECT name||'|'||model||'|'||res_id FROM ir_model_data WHERE module='plasticos_transaction' ORDER BY name, model;
\echo # sale orders
SELECT d.name||'|'||s.name||'|'||coalesce(s.origin,'')||'|'||s.state||'|'||s.partner_id||'|'||coalesce(s.user_id::text,'')||'|'||round(s.amount_total::numeric,2)||'|'||coalesce(s.date_order::text,'')||'|'||coalesce(s.transaction_id::text,'')
  FROM sale_order s JOIN ir_model_data d ON d.model='sale.order' AND d.res_id=s.id AND d.module='plasticos_transaction' ORDER BY d.name;
\echo # sale lines
SELECT d.name||'|'||l.order_id||'|'||l.product_id||'|'||l.product_uom_qty||'|'||l.price_unit||'|'||coalesce(l.product_uom_id::text,'')
  FROM sale_order_line l JOIN ir_model_data d ON d.model='sale.order.line' AND d.res_id=l.id AND d.module='plasticos_transaction' ORDER BY d.name;
\echo # purchase orders
SELECT d.name||'|'||p.name||'|'||coalesce(p.origin,'')||'|'||p.state||'|'||p.partner_id||'|'||coalesce(p.user_id::text,'')||'|'||round(p.amount_total::numeric,2)||'|'||coalesce(p.date_order::text,'')
  FROM purchase_order p JOIN ir_model_data d ON d.model='purchase.order' AND d.res_id=p.id AND d.module='plasticos_transaction' ORDER BY d.name;
\echo # purchase lines
SELECT d.name||'|'||l.order_id||'|'||l.product_id||'|'||l.product_qty||'|'||l.price_unit||'|'||coalesce(l.product_uom_id::text,'')
  FROM purchase_order_line l JOIN ir_model_data d ON d.model='purchase.order.line' AND d.res_id=l.id AND d.module='plasticos_transaction' ORDER BY d.name;
\echo # moves
SELECT d.name||'|'||m.move_type||'|'||m.state||'|'||m.partner_id||'|'||round(m.amount_total::numeric,2)||'|'||coalesce(m.invoice_date::text,'')||'|'||coalesce(m.invoice_origin,'')||'|'||coalesce(m.ref,'')||'|'||coalesce(m.reversed_entry_id::text,'')||'|'||(SELECT count(*) FROM account_move_line l WHERE l.move_id=m.id)
  FROM account_move m JOIN ir_model_data d ON d.model='account.move' AND d.res_id=m.id AND d.module='plasticos_transaction' ORDER BY d.name;
\echo # transactions
SELECT t.name||'|'||t.state||'|'||coalesce(t.sale_order_id::text,'')||'|'||coalesce(t.user_id::text,'')||'|'||coalesce(t.buyer_id::text,'')||'|'||coalesce(t.supplier_id::text,'')||'|'||coalesce(t.customer_invoice_id::text,'')
       ||'|'||coalesce((SELECT string_agg(r.purchase_order_id::text, ',' ORDER BY r.purchase_order_id) FROM plasticos_transaction_purchase_order_rel r WHERE r.plasticos_transaction_id=t.id),'')
       ||'|'||coalesce((SELECT string_agg(r.account_move_id::text, ',' ORDER BY r.account_move_id) FROM plasticos_tx_vendor_rel r WHERE r.plasticos_transaction_id=t.id),'')
       ||'|'||coalesce((SELECT string_agg(r.account_move_id::text, ',' ORDER BY r.account_move_id) FROM plasticos_tx_freight_rel r WHERE r.plasticos_transaction_id=t.id),'')
       ||'|'||round(t.revenue_total::numeric,2)||'|'||round(t.cost_total::numeric,2)||'|'||round(t.gross_margin::numeric,2)
       ||'|'||coalesce(t.commission_locked::text,'')||'|'||coalesce(round(t.commission_locked_amount::numeric,2)::text,'')||'|'||coalesce(t.commission_payout_state,'')
       ||'|'||coalesce(round(t.freight_actual::numeric,2)::text,'')||'|'||coalesce(round(t.other_expenses::numeric,2)::text,'')
  FROM plasticos_transaction t ORDER BY t.name;
\echo # partners
SELECT d.name||'|'||p.name||'|'||coalesce(p.user_id::text,'')||'|'||coalesce(p.parent_id::text,'')||'|'||p.active
  FROM res_partner p JOIN ir_model_data d ON d.model='res.partner' AND d.res_id=p.id AND d.module='plasticos_transaction' ORDER BY d.name;
\echo # chatter notes on transactions
SELECT t.name||'|'||count(*) FROM mail_message mm JOIN plasticos_transaction t ON t.id = mm.res_id WHERE mm.model='plasticos.transaction' AND mm.message_type='comment' GROUP BY t.name ORDER BY t.name;
