SET NOCOUNT ON;
/* Full Receipt — cash / checks applied */
SELECT
  ReceiptID,
  RTRIM(BuySellNo) AS BuySellNo,
  Amount, FxAmount, CurrencyCd,
  RTRIM(CheckNo) AS CheckNo,
  CONVERT(varchar(19), PaymentDt, 120) AS PaymentDt,
  CONVERT(varchar(19), EntryDt, 120) AS EntryDt,
  DiscountAmt, LedgerID, PostingType, Reference,
  CONVERT(varchar(19), DepositDate, 120) AS DepositDate,
  RTRIM(ARBatchNo) AS ARBatchNo
FROM dbo.Receipt
ORDER BY ReceiptID;
