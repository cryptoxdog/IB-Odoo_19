$ErrorActionPreference = "Stop"
$Server = if ($env:CIETRADE_SQL_SERVER) { $env:CIETRADE_SQL_SERVER } else { "UCSCIETRADE" }
$Db = if ($env:CIETRADE_SQL_DATABASE) { $env:CIETRADE_SQL_DATABASE } else { "cieTrade_SM" }
$Out = Join-Path $env:USERPROFILE "Desktop\cieTrade_probe_$(Get-Date -Format yyyyMMdd_HHmmss).csv"
sqlcmd -S $Server -E -d $Db -W -s "," -Q "SET NOCOUNT ON; SELECT TOP 20 s.name AS schema_name, t.name AS table_name, SUM(p.rows) AS approx_rows FROM sys.tables t INNER JOIN sys.schemas s ON s.schema_id=t.schema_id INNER JOIN sys.partitions p ON p.object_id=t.object_id AND p.index_id IN (0,1) WHERE t.is_ms_shipped=0 GROUP BY s.name,t.name ORDER BY approx_rows DESC;" -o $Out
Write-Host "WROTE $Out"
