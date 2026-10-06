$ErrorActionPreference = "Stop"
# Connection targets are supplied by the operator. The SQL Server host and
# database names are deployment facts, not repository facts, so they are not
# hardcoded here (see INVARIANTS.md invariant 20, policy BAN001).
if (-not $env:ERP_SQL_SERVER) { throw "Set ERP_SQL_SERVER to the ERP SQL Server host." }
if (-not $env:ERP_SQL_DATABASE) { throw "Set ERP_SQL_DATABASE to the ERP database name." }
$Server = $env:ERP_SQL_SERVER
$Db = $env:ERP_SQL_DATABASE
$Out = Join-Path $env:USERPROFILE "Desktop\erp_probe_$(Get-Date -Format yyyyMMdd_HHmmss).csv"
sqlcmd -S $Server -E -d $Db -W -s "," -Q "SET NOCOUNT ON; SELECT TOP 20 s.name AS schema_name, t.name AS table_name, SUM(p.rows) AS approx_rows FROM sys.tables t INNER JOIN sys.schemas s ON s.schema_id=t.schema_id INNER JOIN sys.partitions p ON p.object_id=t.object_id AND p.index_id IN (0,1) WHERE t.is_ms_shipped=0 GROUP BY s.name,t.name ORDER BY approx_rows DESC;" -o $Out
Write-Host "WROTE $Out"
