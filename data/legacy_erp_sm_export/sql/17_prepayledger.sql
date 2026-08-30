SET NOCOUNT ON;
/* PrepayLedger — optional (~41 rows); not in 2026-08-07 Excel land */
SELECT
  PrepayID, InvoiceNo, RTRIM(VendorID) AS VendorID, RTRIM(SONumber) AS SONumber,
  RTRIM(COID) AS COID,
  CONVERT(varchar(19), PostDt, 120) AS PostDt,
  GLAcct, CurrencyCd, Amount, FxAmount, RTRIM(APBatchNo) AS APBatchNo,
  FxRate, SalesTaxCodeID, SalesTaxAmt, SalesTaxAmtFx, FxContractNo
FROM dbo.PrepayLedger
ORDER BY PrepayID;
