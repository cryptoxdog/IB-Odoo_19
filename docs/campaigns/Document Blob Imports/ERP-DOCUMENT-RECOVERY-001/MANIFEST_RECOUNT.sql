-- Recount that ran on UCSCIETRADE at 2026-10-28 16:21:56.
-- Same live databases. No backup. No Blob_Image.
-- SQL Server 2012: use COUNT(DISTINCT ...), not COUNT_BIG(DISTINCT ...).

SET NOCOUNT ON;
SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED;

SELECT
    COUNT_BIG(*) AS images,
    COUNT(DISTINCT ImageID) AS image_ids,
    COUNT(DISTINCT DocID) AS doc_ids,
    MIN(CreatedDT) AS min_created,
    MAX(CreatedDT) AS max_created
FROM cieTrade_Documents.dbo.DocumentImage
WHERE UPPER(RTRIM(CONVERT(varchar(128), DBName))) = 'CIETRADE_SM';

SELECT
    LTRIM(RTRIM(RefType)) AS ref_type,
    COUNT_BIG(*) AS images
FROM cieTrade_Documents.dbo.DocumentImage
WHERE UPPER(RTRIM(CONVERT(varchar(128), DBName))) = 'CIETRADE_SM'
GROUP BY LTRIM(RTRIM(RefType))
ORDER BY LTRIM(RTRIM(RefType));
