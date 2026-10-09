SET NOCOUNT ON;
/* PO — sales and purchase order headers. Source=SO is a sale, Source=PO is a purchase. */
SELECT
  POID,
  RTRIM(PONumber) AS PONumber,
  CONVERT(varchar(19), PODate, 120) AS PODate,
  RTRIM(CpID) AS CpID,
  RTRIM(Source) AS Source,
  RTRIM(PriceBasis) AS PriceBasis,
  RTRIM(Terms) AS Terms,
  RTRIM(POReference) AS POReference
FROM dbo.PO
ORDER BY POID;
