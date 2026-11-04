-- ERP INVENTORY INBOUND: SOURCE DISCOVERY ONLY.
-- Use the existing configured, read-only restored SQL Server reader. No app UI.
-- SELECT only. Never execute CREATE, ALTER, UPDATE, INSERT, DELETE or MERGE.
-- Keep raw outputs local/gitignored; publish only sanitized field names and IDs.
SET NOCOUNT ON;

-- A. Verify all worksheet/order/address metadata, especially the destination
--    warehouse selector. Previously tracked column inventory does not list
--    dbo.BuySell, so infer NO column names beyond those already projected.
SELECT t.name AS table_name, c.column_id, c.name AS column_name,
       ty.name AS sql_type, c.max_length
FROM sys.tables AS t
JOIN sys.columns AS c ON c.object_id = t.object_id
JOIN sys.types AS ty ON ty.user_type_id = c.user_type_id
WHERE SCHEMA_NAME(t.schema_id) = 'dbo'
  AND t.name IN ('BuySell', 'Address', 'WKSDetail', 'PO', 'PODetail')
ORDER BY t.name, c.column_id;

-- B. Concrete warehouse vocabulary: the exact pseudo-party site and a
--    corroborating real-party address that must not be conflated with it.
SELECT AddressID, RTRIM(CpID) AS CpID, RTRIM(Type) AS Type,
       RTRIM(WarehouseID) AS WarehouseID, Addr1, Addr2, City, Region
FROM dbo.Address
WHERE AddressID IN (404812, 404811)
   OR (RTRIM(CpID) = '(INV)' AND RTRIM(Type) = 'GREENVIEW WASHINGTON WAREHOUSE')
ORDER BY AddressID;

-- C. Representative inbound worksheet and its actual native order links.
SELECT RTRIM(BuySellNo) AS BuySellNo, RTRIM(CustID) AS CustID,
       RTRIM(VendorID) AS VendorID, OrderDt, InvoiceDt, RTRIM(status) AS status
FROM dbo.BuySell
WHERE RTRIM(BuySellNo) = '60403';

SELECT DetailID, RTRIM(BuySellNo) AS BuySellNo, SPO_ID, PPO_ID,
       RTRIM(GradeID) AS GradeID, SWeight, SWeightUOM,
       PWeight, PWeightUOM, IsReceived, IsItemReceived,
       RTRIM(WarehouseLocation) AS WarehouseLocation
FROM dbo.WKSDetail
WHERE RTRIM(BuySellNo) = '60403'
ORDER BY DetailID;

SELECT POID, RTRIM(PONumber) AS PONumber,
       RTRIM(Source) AS Source, RTRIM(CpID) AS CpID, PODate
FROM dbo.PO
WHERE RTRIM(PONumber) = '33498';

-- D. AFTER examining section A, use the verified source column(s) on
--    BuySell / WKSDetail / its actual related table to show exactly WHY the
--    UI displays the second Sold To warehouse for worksheet 60403.
--    Bind that value to Address 404812 by the actual source key or a proven
--    unique (CpID, Type) relationship. Do NOT guess a string-only join,
--    substitute Address 404811, or equate a WarehouseLocation bin with a site.
--    If no such source link can be proven, STOP and classify the implementation
--    as blocked for warehouse identity; do not synthesize a warehouse.
