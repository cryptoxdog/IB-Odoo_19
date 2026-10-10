SET NOCOUNT ON;
/* BuySell — worksheet header. Notes and ProblemNotes print on the sale order. */
SELECT
  RTRIM(BuySellNo) AS BuySellNo,
  RTRIM(CustID) AS CustID,
  RTRIM(VendorID) AS VendorID,
  CONVERT(varchar(19), OrderDt, 120) AS OrderDt,
  CONVERT(varchar(19), InvoiceDt, 120) AS InvoiceDt,
  RTRIM(PriceBasis) AS PriceBasis,
  CAST(Notes AS varchar(max)) AS Notes,
  CAST(ProblemNotes AS varchar(max)) AS ProblemNotes,
  RTRIM(status) AS status,
  RTRIM(BookingNo) AS BookingNo,
  RTRIM(ReferrerNo1) AS ReferrerNo1,
  RTRIM(ReferrerNo2) AS ReferrerNo2,
  CAST(Commission1 AS varchar(40)) AS Commission1,
  CAST(Commission2 AS varchar(40)) AS Commission2
FROM dbo.BuySell
ORDER BY BuySellNo;
