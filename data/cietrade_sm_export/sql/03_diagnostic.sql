SET NOCOUNT ON;
/* cieTrade_SM_EXPORT — deep field diagnostic (one run)
   Result sets:
     1) identity
     2) columns + nullability/defaults/lengths
     3) primary keys
     4) foreign keys
     5) CounterParty Role / ActiveStatus distinct values
     6) Receipt PostingType distinct values
   Copy each Results tab → CSV (Clipboard → Mac/Cursor).
*/
DECLARE @tables TABLE (name sysname PRIMARY KEY);
INSERT INTO @tables(name) VALUES
  (N'Payables'),(N'PayablesBatch'),(N'Receipt'),(N'ReceiptBatch'),
  (N'GPLedger'),(N'UACashLedger'),(N'PrepayLedger'),
  (N'CounterParty'),(N'Address'),(N'Contact'),(N'ContactRoleAssignment'),
  (N'WKSDetail'),(N'WksDelivery');

-- 1) identity
SELECT DB_NAME() AS db_name, SUSER_SNAME() AS login_name, @@SERVERNAME AS server_name;

-- 2) full column settings
SELECT
    c.TABLE_SCHEMA,
    c.TABLE_NAME,
    c.ORDINAL_POSITION,
    c.COLUMN_NAME,
    c.DATA_TYPE,
    c.CHARACTER_MAXIMUM_LENGTH AS char_len,
    c.NUMERIC_PRECISION AS num_precision,
    c.NUMERIC_SCALE AS num_scale,
    c.DATETIME_PRECISION AS dt_precision,
    c.IS_NULLABLE,
    c.COLUMN_DEFAULT,
    c.COLLATION_NAME,
    CASE WHEN ic.is_identity = 1 THEN 'YES' ELSE 'NO' END AS is_identity,
    CASE WHEN ic.is_computed = 1 THEN 'YES' ELSE 'NO' END AS is_computed
FROM INFORMATION_SCHEMA.COLUMNS AS c
INNER JOIN @tables t ON t.name = c.TABLE_NAME
LEFT JOIN sys.schemas AS ss ON ss.name = c.TABLE_SCHEMA
LEFT JOIN sys.tables AS st ON st.schema_id = ss.schema_id AND st.name = c.TABLE_NAME
LEFT JOIN sys.columns AS ic
  ON ic.object_id = st.object_id AND ic.name = c.COLUMN_NAME
WHERE c.TABLE_SCHEMA = N'dbo'
ORDER BY c.TABLE_NAME, c.ORDINAL_POSITION;

-- 3) primary keys
SELECT
    tc.TABLE_SCHEMA,
    tc.TABLE_NAME,
    kc.COLUMN_NAME,
    kc.ORDINAL_POSITION AS pk_ordinal,
    tc.CONSTRAINT_NAME
FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS AS tc
INNER JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE AS kc
  ON kc.CONSTRAINT_NAME = tc.CONSTRAINT_NAME
 AND kc.TABLE_SCHEMA = tc.TABLE_SCHEMA
 AND kc.TABLE_NAME = tc.TABLE_NAME
INNER JOIN @tables t ON t.name = tc.TABLE_NAME
WHERE tc.CONSTRAINT_TYPE = N'PRIMARY KEY'
  AND tc.TABLE_SCHEMA = N'dbo'
ORDER BY tc.TABLE_NAME, kc.ORDINAL_POSITION;

-- 4) foreign keys (inbound/outbound involving P0 tables)
SELECT
    fk.name AS fk_name,
    OBJECT_SCHEMA_NAME(fk.parent_object_id) AS child_schema,
    OBJECT_NAME(fk.parent_object_id) AS child_table,
    c1.name AS child_column,
    OBJECT_SCHEMA_NAME(fk.referenced_object_id) AS parent_schema,
    OBJECT_NAME(fk.referenced_object_id) AS parent_table,
    c2.name AS parent_column,
    fk.delete_referential_action_desc AS on_delete,
    fk.update_referential_action_desc AS on_update
FROM sys.foreign_keys AS fk
INNER JOIN sys.foreign_key_columns AS fkc ON fkc.constraint_object_id = fk.object_id
INNER JOIN sys.columns AS c1
  ON c1.object_id = fkc.parent_object_id AND c1.column_id = fkc.parent_column_id
INNER JOIN sys.columns AS c2
  ON c2.object_id = fkc.referenced_object_id AND c2.column_id = fkc.referenced_column_id
WHERE OBJECT_NAME(fk.parent_object_id) IN (SELECT name FROM @tables)
   OR OBJECT_NAME(fk.referenced_object_id) IN (SELECT name FROM @tables)
ORDER BY child_table, fk_name, child_column;

-- 5) CounterParty discrete settings (roles / status)
SELECT Role, COUNT(*) AS row_count
FROM dbo.CounterParty
GROUP BY Role
ORDER BY row_count DESC;

SELECT ActiveStatus, COUNT(*) AS row_count
FROM dbo.CounterParty
GROUP BY ActiveStatus
ORDER BY row_count DESC;

SELECT OnHold, COUNT(*) AS row_count
FROM dbo.CounterParty
GROUP BY OnHold
ORDER BY row_count DESC;

-- 6) Receipt posting types
SELECT PostingType, COUNT(*) AS row_count
FROM dbo.Receipt
GROUP BY PostingType
ORDER BY row_count DESC;

SELECT TOP (20) CurrencyCd, COUNT(*) AS row_count
FROM dbo.Payables
GROUP BY CurrencyCd
ORDER BY row_count DESC;
