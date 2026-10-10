SET NOCOUNT ON;
/* PODetail — order lines. PO_ID is the line key, not the header key. */
SELECT
  PO_ID,
  RTRIM(PONumber) AS PONumber,
  RTRIM(GradeID) AS GradeID
FROM dbo.PODetail
ORDER BY PO_ID, PONumber;
