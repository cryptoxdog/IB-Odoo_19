SET NOCOUNT ON;
/* PayablesBatch — PrePay=1 batches stay out of vendor bills. Comment is not worksheet notes.
   Header columns after PrePay are read for source batch identity and reconciliation only;
   no Odoo field is written from them (mapping_status.py). Column names and types:
   diagnostics/q4_columns.csv (INFORMATION_SCHEMA of the restored database). */
SELECT
  RTRIM(APBatchNo) AS APBatchNo,
  PrePay,
  NumofItems,
  CONVERT(varchar(19), PostingDt, 120) AS PostingDt,
  FXAmount,
  CurrencyCd,
  PostedInAccting,
  Comment,
  APTerms,
  RTRIM(CpID) AS CpID,
  InvoiceNo,
  CONVERT(varchar(19), InvoiceDt, 120) AS InvoiceDt,
  CONVERT(varchar(19), DueDate, 120) AS DueDate,
  ReversedFxAmt
FROM dbo.PayablesBatch
ORDER BY APBatchNo;
