SET NOCOUNT ON;
SELECT DB_NAME() AS db_name, SUSER_SNAME() AS login_name, @@SERVERNAME AS server_name;
SELECT TOP (40)
    s.name AS schema_name,
    t.name AS table_name,
    SUM(p.rows) AS approx_row_count
FROM sys.tables AS t
INNER JOIN sys.schemas AS s ON s.schema_id = t.schema_id
INNER JOIN sys.partitions AS p ON p.object_id = t.object_id AND p.index_id IN (0, 1)
WHERE t.is_ms_shipped = 0
  AND (
        t.name LIKE '%Pay%'
     OR t.name LIKE '%Receipt%'
     OR t.name LIKE '%Check%'
     OR t.name LIKE '%Ledger%'
     OR t.name LIKE '%Invoice%'
     OR t.name LIKE '%Counter%'
     OR t.name LIKE '%Address%'
     OR t.name LIKE '%Contact%'
     OR t.name LIKE '%WKS%'
     OR t.name LIKE '%Wks%'
  )
GROUP BY s.name, t.name
ORDER BY approx_row_count DESC, s.name, t.name;
