SET NOCOUNT ON;
-- Run against cieTrade_SM_EXPORT (toolbar DB)
SELECT c.TABLE_SCHEMA, c.TABLE_NAME, c.ORDINAL_POSITION, c.COLUMN_NAME, c.DATA_TYPE, c.CHARACTER_MAXIMUM_LENGTH
FROM INFORMATION_SCHEMA.COLUMNS AS c
WHERE c.TABLE_SCHEMA = 'dbo'
  AND c.TABLE_NAME IN (
    'Payables','PayablesBatch','Receipt','ReceiptBatch','GPLedger',
    'UACashLedger','PrepayLedger',
    'CounterParty','Address','Contact','ContactRoleAssignment',
    'WKSDetail','WksDocument','WksDelivery'
  )
ORDER BY c.TABLE_NAME, c.ORDINAL_POSITION;
