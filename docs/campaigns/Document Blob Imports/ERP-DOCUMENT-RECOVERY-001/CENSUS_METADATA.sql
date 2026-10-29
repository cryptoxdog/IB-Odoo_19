-- Full-corpus identity census. Metadata only. No Blob_Image. No backup.
-- Run in the SSMS window connected to UCSerp. Paste every result grid back.

SET NOCOUNT ON;
SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED;

SELECT '01_columns' AS result_set;
SELECT c.column_id, c.name, ty.name AS type_name, c.max_length
FROM erp_Documents.sys.columns AS c
JOIN erp_Documents.sys.types AS ty ON ty.user_type_id = c.user_type_id
WHERE c.object_id = OBJECT_ID(N'erp_Documents.dbo.DocumentImage')
ORDER BY c.column_id;

SELECT '02_dbname_counts' AS result_set;
SELECT UPPER(RTRIM(CONVERT(varchar(128), DBName))) AS db_name, COUNT_BIG(*) AS image_rows
FROM erp_Documents.dbo.DocumentImage
GROUP BY UPPER(RTRIM(CONVERT(varchar(128), DBName)))
ORDER BY image_rows DESC;

IF OBJECT_ID('tempdb..#img') IS NOT NULL DROP TABLE #img;

SELECT
    ImageID,
    DocID,
    ISNULL(LTRIM(RTRIM(CONVERT(varchar(255), RefID))), '') AS RefID,
    ISNULL(LTRIM(RTRIM(CONVERT(varchar(20), RefType))), '') AS RefType,
    ISNULL(LTRIM(RTRIM(CONVERT(varchar(255), DocName))), '') AS DocName,
    ISNULL(LTRIM(RTRIM(CONVERT(varchar(255), DocType))), '') AS DocType,
    Blob_Size,
    CreatedDT,
    CASE
        WHEN ISNULL(LTRIM(RTRIM(CONVERT(varchar(255), RefID))), '') NOT LIKE '%[^0-9]%'
         AND ISNULL(LTRIM(RTRIM(CONVERT(varchar(255), RefID))), '') <> ''
         AND LEN(ISNULL(LTRIM(RTRIM(CONVERT(varchar(255), RefID))), '')) <= 9
        THEN CONVERT(int, LTRIM(RTRIM(CONVERT(varchar(255), RefID))))
        ELSE NULL
    END AS RefInt
INTO #img
FROM erp_Documents.dbo.DocumentImage
WHERE UPPER(RTRIM(CONVERT(varchar(128), DBName))) = 'erp_SM';

SELECT '03_corpus' AS result_set;
SELECT
    COUNT_BIG(*) AS images,
    COUNT(DISTINCT ImageID) AS distinct_image_id,
    COUNT(DISTINCT DocID) AS distinct_doc_id,
    COUNT(DISTINCT RefID) AS distinct_ref_id,
    MIN(CreatedDT) AS min_created,
    MAX(CreatedDT) AS max_created,
    SUM(CASE WHEN DocName <> '' THEN 1 ELSE 0 END) AS rows_with_doc_name,
    SUM(CASE WHEN DocType <> '' THEN 1 ELSE 0 END) AS rows_with_doc_type
FROM #img;

SELECT '04_by_reftype' AS result_set;
SELECT
    RefType,
    COUNT_BIG(*) AS images,
    COUNT(DISTINCT DocID) AS distinct_docs,
    COUNT(DISTINCT RefID) AS distinct_refs,
    SUM(CASE WHEN RefID = '' THEN 1 ELSE 0 END) AS blank_ref,
    SUM(CASE WHEN RefID <> '' AND RefID NOT LIKE '%[^0-9]%' THEN 1 ELSE 0 END) AS numeric_ref,
    SUM(CASE WHEN RefID LIKE '%[^0-9]%' THEN 1 ELSE 0 END) AS non_numeric_ref,
    SUM(CASE WHEN DocName <> '' THEN 1 ELSE 0 END) AS named_rows,
    SUM(CASE WHEN DocType <> '' THEN 1 ELSE 0 END) AS typed_rows,
    MIN(CreatedDT) AS min_created,
    MAX(CreatedDT) AS max_created
FROM #img
GROUP BY RefType
ORDER BY RefType;

SELECT '05_images_per_docid' AS result_set;
SELECT
    CASE
        WHEN n = 1 THEN '1'
        WHEN n = 2 THEN '2'
        WHEN n BETWEEN 3 AND 5 THEN '3-5'
        WHEN n BETWEEN 6 AND 10 THEN '6-10'
        WHEN n BETWEEN 11 AND 50 THEN '11-50'
        ELSE '51+'
    END AS images_per_doc,
    COUNT_BIG(*) AS doc_ids,
    SUM(n) AS images,
    MIN(n) AS min_n
FROM (SELECT DocID, COUNT_BIG(*) AS n FROM #img GROUP BY DocID) AS s
GROUP BY
    CASE
        WHEN n = 1 THEN '1'
        WHEN n = 2 THEN '2'
        WHEN n BETWEEN 3 AND 5 THEN '3-5'
        WHEN n BETWEEN 6 AND 10 THEN '6-10'
        WHEN n BETWEEN 11 AND 50 THEN '11-50'
        ELSE '51+'
    END
ORDER BY MIN(n);

SELECT '06_images_per_ref' AS result_set;
SELECT
    RefType,
    CASE
        WHEN n = 1 THEN '1'
        WHEN n = 2 THEN '2'
        WHEN n BETWEEN 3 AND 5 THEN '3-5'
        WHEN n BETWEEN 6 AND 10 THEN '6-10'
        WHEN n BETWEEN 11 AND 50 THEN '11-50'
        ELSE '51+'
    END AS images_per_ref,
    COUNT_BIG(*) AS ref_ids,
    SUM(n) AS images
FROM (SELECT RefType, RefID, COUNT_BIG(*) AS n FROM #img GROUP BY RefType, RefID) AS s
GROUP BY
    RefType,
    CASE
        WHEN n = 1 THEN '1'
        WHEN n = 2 THEN '2'
        WHEN n BETWEEN 3 AND 5 THEN '3-5'
        WHEN n BETWEEN 6 AND 10 THEN '6-10'
        WHEN n BETWEEN 11 AND 50 THEN '11-50'
        ELSE '51+'
    END
ORDER BY RefType, MIN(n);

SELECT '07_refid_shared_by_type' AS result_set;
SELECT
    SUM(CASE WHEN w = 1 AND p = 1 THEN 1 ELSE 0 END) AS refs_in_W_and_P,
    SUM(CASE WHEN w = 1 AND e = 1 THEN 1 ELSE 0 END) AS refs_in_W_and_E,
    SUM(CASE WHEN p = 1 AND e = 1 THEN 1 ELSE 0 END) AS refs_in_P_and_E,
    SUM(CASE WHEN w = 1 AND p = 1 AND e = 1 THEN 1 ELSE 0 END) AS refs_in_W_P_and_E,
    SUM(CASE WHEN type_count > 1 THEN 1 ELSE 0 END) AS refs_with_multiple_types
FROM (
    SELECT
        RefID,
        MAX(CASE WHEN RefType = 'W' THEN 1 ELSE 0 END) AS w,
        MAX(CASE WHEN RefType = 'P' THEN 1 ELSE 0 END) AS p,
        MAX(CASE WHEN RefType = 'E' THEN 1 ELSE 0 END) AS e,
        COUNT(DISTINCT RefType) AS type_count
    FROM #img
    WHERE RefID <> ''
    GROUP BY RefID
) AS s;

SELECT '08_blank_or_non_numeric_refs' AS result_set;
SELECT TOP 30 RefType, RefID, COUNT_BIG(*) AS images, MIN(CreatedDT) AS min_created, MAX(CreatedDT) AS max_created
FROM #img
WHERE RefID = '' OR RefID LIKE '%[^0-9]%'
GROUP BY RefType, RefID
ORDER BY images DESC, RefType, RefID;

SELECT '09_recovery_point' AS result_set;
SELECT 'documents.CreatedDT' AS source_col, MIN(CreatedDT) AS min_dt, MAX(CreatedDT) AS max_dt, COUNT_BIG(*) AS rows_n
FROM #img
UNION ALL
SELECT 'erp_SM.BuySell.OrderDt', MIN(OrderDt), MAX(OrderDt), COUNT_BIG(*) FROM erp_SM.dbo.BuySell
UNION ALL
SELECT 'erp_SM.PO.PODate', MIN(PODate), MAX(PODate), COUNT_BIG(*) FROM erp_SM.dbo.PO
UNION ALL
SELECT 'erp_SM.WksDocument.CreationDt', MIN(CreationDt), MAX(CreationDt), COUNT_BIG(*) FROM erp_SM.dbo.WksDocument
UNION ALL
SELECT 'erp_SM.PODocument.CreationDt', MIN(CreationDt), MAX(CreationDt), COUNT_BIG(*) FROM erp_SM.dbo.PODocument;

IF OBJECT_ID('tempdb..#class') IS NOT NULL DROP TABLE #class;

SELECT
    i.ImageID,
    i.DocID,
    i.RefID,
    i.RefType,
    i.CreatedDT,
    CASE WHEN b.k IS NOT NULL THEN 1 ELSE 0 END AS buysell_hit,
    CASE WHEN p.k IS NOT NULL THEN 1 ELSE 0 END AS po_hit,
    CASE WHEN d.DetailID IS NOT NULL THEN 1 ELSE 0 END AS detail_hit,
    CASE WHEN w.RefFile IS NOT NULL THEN 1 ELSE 0 END AS wks_reg_hit,
    CASE WHEN w.RefFile IS NOT NULL AND w.parent_variants = 1 AND w.reg_parent = i.RefID THEN 1 ELSE 0 END AS wks_reg_agrees,
    CASE WHEN w.RefFile IS NOT NULL AND NOT (w.parent_variants = 1 AND w.reg_parent = i.RefID) THEN 1 ELSE 0 END AS wks_reg_disagrees,
    CASE WHEN o.RefFile IS NOT NULL THEN 1 ELSE 0 END AS po_reg_hit,
    CASE WHEN o.RefFile IS NOT NULL AND o.parent_variants = 1 AND o.reg_parent = i.RefID THEN 1 ELSE 0 END AS po_reg_agrees,
    CASE WHEN o.RefFile IS NOT NULL AND NOT (o.parent_variants = 1 AND o.reg_parent = i.RefID) THEN 1 ELSE 0 END AS po_reg_disagrees
INTO #class
FROM #img AS i
LEFT JOIN (
    SELECT DISTINCT LTRIM(RTRIM(BuySellNo)) AS k
    FROM erp_SM.dbo.BuySell
    WHERE LTRIM(RTRIM(BuySellNo)) <> ''
) AS b ON b.k = i.RefID AND i.RefID <> ''
LEFT JOIN (
    SELECT DISTINCT LTRIM(RTRIM(PONumber)) AS k
    FROM erp_SM.dbo.PO
    WHERE LTRIM(RTRIM(PONumber)) <> ''
) AS p ON p.k = i.RefID AND i.RefID <> ''
LEFT JOIN (
    SELECT DetailID
    FROM erp_SM.dbo.WKSDetail
    GROUP BY DetailID
) AS d ON d.DetailID = i.RefInt
LEFT JOIN (
    SELECT
        LTRIM(RTRIM(RefFile)) AS RefFile,
        MIN(LTRIM(RTRIM(BuySellNo))) AS reg_parent,
        COUNT(DISTINCT LTRIM(RTRIM(BuySellNo))) AS parent_variants
    FROM erp_SM.dbo.WksDocument
    GROUP BY LTRIM(RTRIM(RefFile))
) AS w ON w.RefFile = CONVERT(varchar(30), i.DocID)
LEFT JOIN (
    SELECT
        LTRIM(RTRIM(RefFile)) AS RefFile,
        MIN(LTRIM(RTRIM(PONumber))) AS reg_parent,
        COUNT(DISTINCT LTRIM(RTRIM(PONumber))) AS parent_variants
    FROM erp_SM.dbo.PODocument
    GROUP BY LTRIM(RTRIM(RefFile))
) AS o ON o.RefFile = CONVERT(varchar(30), i.DocID);

SELECT '10_classification' AS result_set;
SELECT
    RefType,
    COUNT_BIG(*) AS images,
    SUM(buysell_hit) AS buysell_hit,
    SUM(po_hit) AS po_hit,
    SUM(CASE WHEN buysell_hit = 1 AND po_hit = 1 THEN 1 ELSE 0 END) AS both_parents,
    SUM(CASE WHEN buysell_hit = 0 AND po_hit = 0 THEN 1 ELSE 0 END) AS neither_parent,
    SUM(CASE WHEN detail_hit = 1 AND buysell_hit = 0 AND po_hit = 0 THEN 1 ELSE 0 END) AS detail_only,
    SUM(CASE WHEN detail_hit = 1 AND (buysell_hit = 1 OR po_hit = 1) THEN 1 ELSE 0 END) AS detail_and_parent,
    SUM(wks_reg_hit) AS wks_reg_hit,
    SUM(wks_reg_agrees) AS wks_reg_agrees,
    SUM(wks_reg_disagrees) AS wks_reg_disagrees,
    SUM(po_reg_hit) AS po_reg_hit,
    SUM(po_reg_agrees) AS po_reg_agrees,
    SUM(po_reg_disagrees) AS po_reg_disagrees,
    SUM(CASE WHEN wks_reg_hit = 0 AND po_reg_hit = 0 THEN 1 ELSE 0 END) AS no_registry
FROM #class
GROUP BY RefType
ORDER BY RefType;

SELECT '11_universe_coverage' AS result_set;
SELECT
    (SELECT COUNT_BIG(*) FROM erp_SM.dbo.BuySell) AS buysell_rows,
    (SELECT COUNT_BIG(*) FROM #class WHERE RefType = 'W' AND buysell_hit = 1) AS w_images_on_buysell,
    (SELECT COUNT(DISTINCT RefID) FROM #class WHERE RefType = 'W' AND buysell_hit = 1 AND RefID <> '') AS worksheets_with_w_doc,
    (SELECT COUNT_BIG(*) FROM (SELECT DISTINCT LTRIM(RTRIM(BuySellNo)) AS k FROM erp_SM.dbo.BuySell) AS b WHERE NOT EXISTS (SELECT 1 FROM #class c WHERE c.RefType = 'W' AND c.RefID = b.k)) AS worksheets_without_w_doc,
    (SELECT COUNT_BIG(*) FROM erp_SM.dbo.PO) AS po_rows,
    (SELECT COUNT_BIG(*) FROM #class WHERE RefType = 'P' AND po_hit = 1) AS p_images_on_po,
    (SELECT COUNT(DISTINCT RefID) FROM #class WHERE RefType = 'P' AND po_hit = 1 AND RefID <> '') AS pos_with_p_doc,
    (SELECT COUNT_BIG(*) FROM (SELECT DISTINCT LTRIM(RTRIM(PONumber)) AS k FROM erp_SM.dbo.PO) AS p WHERE NOT EXISTS (SELECT 1 FROM #class c WHERE c.RefType = 'P' AND c.RefID = p.k)) AS pos_without_p_doc;

SELECT '12_hash_and_b_rows' AS result_set;
SELECT ImageID, DocID, RefType, RefID, CreatedDT, buysell_hit, po_hit, detail_hit, wks_reg_hit, wks_reg_agrees, po_reg_hit, po_reg_agrees
FROM #class
WHERE RefType IN ('B', '#')
ORDER BY RefType, ImageID;

SELECT '13_unmatched_w' AS result_set;
SELECT TOP 20 RefID, COUNT_BIG(*) AS images, MIN(CreatedDT) AS min_created, MAX(CreatedDT) AS max_created,
    MAX(detail_hit) AS any_detail_hit, MAX(po_hit) AS any_po_hit, MAX(wks_reg_hit) AS any_wks_reg
FROM #class
WHERE RefType = 'W' AND buysell_hit = 0
GROUP BY RefID
ORDER BY images DESC, RefID;

SELECT '14_unmatched_p' AS result_set;
SELECT TOP 20 RefID, COUNT_BIG(*) AS images, MIN(CreatedDT) AS min_created, MAX(CreatedDT) AS max_created,
    MAX(detail_hit) AS any_detail_hit, MAX(buysell_hit) AS any_buysell_hit, MAX(po_reg_hit) AS any_po_reg
FROM #class
WHERE RefType = 'P' AND po_hit = 0
GROUP BY RefID
ORDER BY images DESC, RefID;

SELECT '15_e_refs' AS result_set;
SELECT TOP 20 RefID, COUNT_BIG(*) AS images, MIN(CreatedDT) AS min_created, MAX(CreatedDT) AS max_created,
    MAX(buysell_hit) AS any_buysell_hit, MAX(po_hit) AS any_po_hit, MAX(detail_hit) AS any_detail_hit,
    MAX(wks_reg_hit) AS any_wks_reg, MAX(po_reg_hit) AS any_po_reg
FROM #class
WHERE RefType = 'E'
GROUP BY RefID
ORDER BY images DESC, RefID;
