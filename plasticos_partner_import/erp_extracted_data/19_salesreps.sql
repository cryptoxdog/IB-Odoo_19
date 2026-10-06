SET NOCOUNT ON;
/* Full company sales-rep assignments — no row limit.
   Source table: dbo.Counterparty_Referrer (meta/census_payment_rank.txt lists it at 977 rows,
   the row count of the 2026 SalesReps extract). The column set is the header of
   bulk/SalesReps.csv; ReferrerNo keeps its char padding, the mapping layer strips it.
   Confirm the table name against the restored database before the first direct read. */
SELECT RTRIM(CpID) AS CpID, ReferrerNo, Rate, Charge, IsDefault, ChgPer
FROM dbo.Counterparty_Referrer
ORDER BY CpID, ReferrerNo;
