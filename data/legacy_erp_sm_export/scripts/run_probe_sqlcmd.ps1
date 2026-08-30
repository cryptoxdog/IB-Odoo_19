$ErrorActionPreference = "Stop"
# Connection targets are supplied by the operator. The legacy source server and
# database names are deployment facts, not repository facts, so they are not
# hardcoded here (see INVARIANTS.md invariant 20, policy BAN001).
if (-not $env:LEGACY_ERP_SQL_SERVER) { throw "Set LEGACY_ERP_SQL_SERVER to the legacy source SQL Server host." }
if (-not $env:LEGACY_ERP_SQL_DATABASE) { throw "Set LEGACY_ERP_SQL_DATABASE to the legacy source database name." }
$Server = $env:LEGACY_ERP_SQL_SERVER
$Db = $env:LEGACY_ERP_SQL_DATABASE
$Out = Join-Path $env:USERPROFILE "Desktop\legacy_erp_probe_$(Get-Date -Format yyyyMMdd_HHmmss).csv"
sqlcmd -S $Server -E -d $Db -W -s "," -Q "SET NOCOUNT ON; SELECT TOP 20 s.name AS schema_name, t.name AS table_name, SUM(p.rows) AS approx_rows FROM sys.tables t INNER JOIN sys.schemas s ON s.schema_id=t.schema_id INNER JOIN sys.partitions p ON p.object_id=t.object_id AND p.index_id IN (0,1) WHERE t.is_ms_shipped=0 GROUP BY s.name,t.name ORDER BY approx_rows DESC;" -o $Out
Write-Host "WROTE $Out"
