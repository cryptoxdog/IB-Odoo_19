SET NOCOUNT ON;
/* PayablesBatch — PrePay=1 batches stay out of vendor bills. Comment is not worksheet notes. */
SELECT
  RTRIM(APBatchNo) AS APBatchNo,
  PrePay
FROM dbo.PayablesBatch
ORDER BY APBatchNo;
