SET NOCOUNT ON;
SELECT DB_NAME() AS db_name, SUSER_SNAME() AS login_name, @@SERVERNAME AS server_name;
SELECT TOP (10) s.name AS schema_name, t.name AS table_name
FROM sys.tables t
INNER JOIN sys.schemas s ON s.schema_id = t.schema_id
WHERE t.is_ms_shipped = 0
ORDER BY t.name;
