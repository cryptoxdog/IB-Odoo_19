SET NOCOUNT ON;
/* Full GPLedger — optional GP / commission / adjustments */
SELECT
  LedgerID,
  CONVERT(varchar(19), TradeDt, 120) AS TradeDt,
  RTRIM(BuySellNo) AS BuySellNo,
  Source, Sale, Cost, GrossProfit, Commission,
  RTRIM(AdjCpID) AS AdjCpID,
  AdjType, AdjFxAmount,
  RTRIM(APBatchNo) AS APBatchNo,
  RTRIM(ARBatchNo) AS ARBatchNo,
  ReferenceID
FROM dbo.GPLedger
ORDER BY LedgerID;
