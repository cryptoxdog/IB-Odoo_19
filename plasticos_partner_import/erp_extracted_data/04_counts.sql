SET NOCOUNT ON;
/* Exact row counts (LEGACY_ERP_SM_EXPORT) */
SELECT 'CounterParty_active' AS metric, COUNT(*) AS n
FROM dbo.CounterParty
WHERE ActiveStatus = 'A'
  AND CpID NOT LIKE '(%' AND CpID NOT LIKE '{%' AND CpID NOT LIKE '[%'
UNION ALL
SELECT 'CounterParty_all', COUNT(*) FROM dbo.CounterParty
UNION ALL
SELECT 'Address_all', COUNT(*) FROM dbo.Address
UNION ALL
SELECT 'Contact_active', COUNT(*) FROM dbo.Contact WHERE IsActive = 'Y' OR IsActive IS NULL
UNION ALL
SELECT 'Payables_all', COUNT(*) FROM dbo.Payables
UNION ALL
SELECT 'Receipt_all', COUNT(*) FROM dbo.Receipt
UNION ALL
SELECT 'GPLedger_all', COUNT(*) FROM dbo.GPLedger
ORDER BY metric;
