SET NOCOUNT ON;
/* ReceiptBatch — single-result form of the SELECT in 05_extract_all.sql. */
SELECT
  RTRIM(ARBatchNo) AS ARBatchNo, PostType, RTRIM(COID) AS COID, NumOfItems,
  RTRIM(UserID) AS UserID,
  CONVERT(varchar(19), PostingDt, 120) AS PostingDt,
  CONVERT(varchar(19), RecordDate, 120) AS RecordDate,
  RTRIM(CPID) AS CPID, CheckNo, Currency, HcApplyAmt, FxApplyAmt,
  ExportBatchNo, PostedInAccting, DoNotExport
FROM dbo.ReceiptBatch
ORDER BY ARBatchNo;
