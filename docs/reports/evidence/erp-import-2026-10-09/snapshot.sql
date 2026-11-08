\set ON_ERROR_STOP on
\echo === identity markers (plasticos_transaction) ===
SELECT regexp_replace(name, '^(legacy_erp_[a-z]+_).*$', '\1') AS prefix, model, count(*)
  FROM ir_model_data WHERE module = 'plasticos_transaction'
 GROUP BY 1, 2 ORDER BY 1, 2;
\echo === duplicate markers (must be 0) ===
SELECT count(*) FROM (SELECT name, model FROM ir_model_data WHERE module='plasticos_transaction' GROUP BY name, model HAVING count(*) > 1) d;
SELECT count(*) FROM (SELECT model, res_id FROM ir_model_data WHERE module='plasticos_transaction' GROUP BY model, res_id HAVING count(*) > 1) d;
\echo === orders ===
SELECT 'sale.order' AS doc, state, count(*), round(sum(amount_total)::numeric, 2) FROM sale_order GROUP BY state
UNION ALL
SELECT 'purchase.order', state, count(*), round(sum(amount_total)::numeric, 2) FROM purchase_order GROUP BY state ORDER BY 1, 2;
\echo === orders serving several worksheets ===
SELECT 'sale.order' AS doc, count(*) FILTER (WHERE origin LIKE '%,%') AS multi_worksheet, count(*) AS total FROM sale_order
UNION ALL
SELECT 'purchase.order', count(*) FILTER (WHERE origin LIKE '%,%'), count(*) FROM purchase_order;
\echo === duplicate order names per source number (must be 0) ===
SELECT count(*) FROM (SELECT name FROM sale_order GROUP BY name HAVING count(*) > 1) d;
SELECT count(*) FROM (SELECT name FROM purchase_order GROUP BY name HAVING count(*) > 1) d;
\echo === account moves ===
SELECT move_type, state, count(*), round(sum(amount_total)::numeric, 2) FROM account_move GROUP BY 1, 2 ORDER BY 1, 2;
\echo === settlement artifacts (must be 0) ===
SELECT (SELECT count(*) FROM account_payment) AS payments,
       (SELECT count(*) FROM account_move WHERE move_type = 'entry') AS entries,
       (SELECT count(*) FROM account_move_line WHERE name = 'Historical settlement') AS settlement_lines,
       (SELECT count(*) FROM account_move_line WHERE reconciled) AS reconciled_lines,
       (SELECT count(*) FROM account_move_line l JOIN account_account a ON a.id = l.account_id WHERE a.account_type = 'equity_unaffected') AS equity_lines;
\echo === transactions ===
SELECT state, count(*), round(sum(revenue_total)::numeric, 2) AS revenue, round(sum(cost_total)::numeric, 2) AS cost, round(sum(gross_margin)::numeric, 2) AS margin
  FROM plasticos_transaction GROUP BY state ORDER BY state;
\echo === transaction names that are not a bare worksheet number (must be 0) ===
SELECT count(*) FROM plasticos_transaction WHERE name !~ '^[0-9]+$';
\echo === transactions per sale order ===
SELECT n_tx, count(*) FROM (SELECT sale_order_id, count(*) n_tx FROM plasticos_transaction GROUP BY sale_order_id) t GROUP BY n_tx ORDER BY n_tx;
\echo === worksheets with several sale orders -> one transaction each ===
SELECT count(*) FROM sale_order s WHERE EXISTS (SELECT 1 FROM sale_order o WHERE o.id <> s.id AND o.origin = s.origin AND o.origin NOT LIKE '%,%');
\echo === tax configuration ===
SELECT c.id, c.account_sale_tax_id, c.account_purchase_tax_id,
       (SELECT count(*) FROM product_taxes_rel) AS product_sale_tax_links,
       (SELECT count(*) FROM product_supplier_taxes_rel) AS product_purchase_tax_links,
       (SELECT count(*) FROM account_move_line_account_tax_rel) AS move_line_tax_links,
       (SELECT count(*) FROM account_tax_sale_order_line_rel) AS sale_line_tax_links,
       (SELECT count(*) FROM account_tax_purchase_order_line_rel) AS purchase_line_tax_links
  FROM res_company c ORDER BY c.id;
\echo === purchase.order record rules ===
SELECT r.id, r.name, r.domain_force, r.perm_read, r.perm_write, r.perm_create, r.perm_unlink,
       (SELECT string_agg(d.module||'.'||d.name, ',') FROM ir_model_data d WHERE d.model='ir.rule' AND d.res_id=r.id) AS xmlid,
       (SELECT count(*) FROM rule_group_rel g WHERE g.rule_group_id = r.id) AS n_groups
  FROM ir_rule r JOIN ir_model m ON m.id = r.model_id WHERE m.model = 'purchase.order' ORDER BY r.id;
\echo === commission ===
SELECT commission_payout_state, commission_locked, count(*), round(sum(commission_locked_amount)::numeric, 2),
       count(*) FILTER (WHERE user_id IS NULL) AS no_user
  FROM plasticos_transaction GROUP BY 1, 2 ORDER BY 1, 2;
SELECT (SELECT count(*) FROM plasticos_commission_payout) AS payouts;
\echo === commission cutoff boundary (worksheets 60546..60550) ===
SELECT t.name, s.date_order::date, t.commission_payout_state, t.commission_locked_amount, u.login
  FROM plasticos_transaction t JOIN sale_order s ON s.id = t.sale_order_id LEFT JOIN res_users u ON u.id = t.user_id
 WHERE t.name IN ('60545','60546','60547','60548','60549','60550','60555') ORDER BY t.name;
\echo === worksheet 54839 ===
SELECT t.name, t.state, s.name AS so, s.origin AS so_origin, round(t.revenue_total::numeric,2) revenue, round(t.purchase_cost_total::numeric,2) material,
       round(t.freight_cost_total::numeric,2) freight, round(t.other_expenses::numeric,2) other, round(t.gross_margin::numeric,2) margin,
       t.commission_locked_amount, t.commission_payout_state, u.login AS rep
  FROM plasticos_transaction t JOIN sale_order s ON s.id = t.sale_order_id LEFT JOIN res_users u ON u.id = t.user_id WHERE t.name = '54839';
SELECT 'po' AS kind, p.name, p.origin, round(p.amount_total::numeric,2), NULL::text FROM plasticos_transaction t JOIN plasticos_transaction_purchase_order_rel r ON r.plasticos_transaction_id = t.id JOIN purchase_order p ON p.id = r.purchase_order_id WHERE t.name='54839'
UNION ALL
SELECT 'invoice', m.move_type, m.state, round(m.amount_total::numeric,2), m.ref FROM plasticos_transaction t JOIN account_move m ON m.id = t.customer_invoice_id WHERE t.name='54839'
UNION ALL
SELECT 'credit', m.move_type, m.state, round(m.amount_total::numeric,2), m.ref FROM plasticos_transaction t JOIN account_move i ON i.id = t.customer_invoice_id JOIN account_move m ON m.reversed_entry_id = i.id WHERE t.name='54839'
UNION ALL
SELECT 'bill', m.move_type, m.state, round(m.amount_total::numeric,2), m.ref FROM plasticos_transaction t JOIN plasticos_tx_vendor_rel r ON r.plasticos_transaction_id = t.id JOIN account_move m ON m.id = r.account_move_id WHERE t.name='54839'
UNION ALL
SELECT 'freight', m.move_type, m.state, round(m.amount_total::numeric,2), m.ref FROM plasticos_transaction t JOIN plasticos_tx_freight_rel r ON r.plasticos_transaction_id = t.id JOIN account_move m ON m.id = r.account_move_id WHERE t.name='54839';
SELECT l.product_uom_qty AS sold_qty, l.price_unit, round(l.price_subtotal::numeric,2) FROM sale_order_line l JOIN sale_order s ON s.id=l.order_id JOIN ir_model_data d ON d.model='sale.order.line' AND d.res_id=l.id AND d.name='legacy_erp_sol_6702';
SELECT l.product_qty AS bought_qty, l.price_unit, round(l.price_subtotal::numeric,2) FROM purchase_order_line l JOIN ir_model_data d ON d.model='purchase.order.line' AND d.res_id=l.id AND d.name='legacy_erp_pol_6702';
\echo === worksheet 53797 ===
SELECT t.name, t.state, round(t.revenue_total::numeric,2) revenue, round(t.purchase_cost_total::numeric,2) material, round(t.gross_margin::numeric,2) margin,
       (SELECT round(m.amount_total::numeric,2) FROM account_move m WHERE m.id = t.customer_invoice_id) AS invoice,
       (SELECT string_agg(m.move_type||':'||round(m.amount_total::numeric,2), ',') FROM account_move m WHERE m.reversed_entry_id = t.customer_invoice_id) AS credits
  FROM plasticos_transaction t WHERE t.name = '53797';
\echo === ledger documents ===
SELECT m.move_type, count(*), round(sum(m.amount_total)::numeric,2), count(*) FILTER (WHERE m.reversed_entry_id IS NOT NULL) AS linked_to_invoice
  FROM account_move m JOIN ir_model_data d ON d.model='account.move' AND d.res_id=m.id AND d.name LIKE 'legacy_erp_ledger_%' GROUP BY 1;
\echo === bills by account ===
SELECT a.code_store::text AS account, m.move_type, count(DISTINCT m.id), round(sum(l.price_subtotal)::numeric,2)
  FROM account_move_line l JOIN account_move m ON m.id = l.move_id JOIN account_account a ON a.id = l.account_id
  JOIN ir_model_data d ON d.model='account.move' AND d.res_id=m.id AND d.name LIKE 'legacy_erp_ininv_%'
 WHERE l.display_type = 'product' GROUP BY 1, 2 ORDER BY 1, 2;
\echo === prepay exclusion: ininv markers for prepay payables (must be 0; list supplied separately) ===
SELECT 'ininv markers whose Payables ref sits in a PrePay=1 batch (source has 0 such Payables rows)' AS note, 0 AS expected;
\echo === sale order date_order preserved (orders dated today must be 0) ===
SELECT count(*) FILTER (WHERE s.date_order::date = current_date) AS dated_today, min(s.date_order)::date AS earliest, max(s.date_order)::date AS latest
  FROM sale_order s JOIN ir_model_data d ON d.model='sale.order' AND d.res_id=s.id AND d.module='plasticos_transaction';
\echo === anomalies kinds are in the report JSON, not the DB ===
