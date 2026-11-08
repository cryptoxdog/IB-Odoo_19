SET NOCOUNT ON;
/* Full Payables — payment history */
SELECT
  PayableID,
  RTRIM(BuySellNo) AS BuySellNo,
  ItemID,
  RTRIM(CpID) AS CpID,
  Amount, FxAmount, CurrencyCd,
  InvoiceNo,
  CONVERT(varchar(19), InvoiceDt, 120) AS InvoiceDt,
  CONVERT(varchar(19), RcvDt, 120) AS RcvDt,
  Posted, IsCheck, CheckNo,
  RTRIM(APBatchNo) AS APBatchNo,
  CONVERT(varchar(19), Reference_Date, 120) AS Reference_Date,
  GLAcct
FROM dbo.Payables
ORDER BY PayableID;
