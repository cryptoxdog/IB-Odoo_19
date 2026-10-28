-- One row per CIETRADE_SM image. Metadata only.
-- Same live databases as the census. No backup. No Blob_Image.
-- In SSMS: Query > Results To > Results to File.
-- Save as \\ucsservers01\home\ibeylin\Desktop\SQL 10-28-26\cietrade_sm_manifest.csv
-- Do not save the file into the git repository.

SET NOCOUNT ON;
SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED;

SELECT
    i.ImageID,
    i.DocID,
    LTRIM(RTRIM(CONVERT(varchar(255), i.RefID))) AS RefID,
    LTRIM(RTRIM(CONVERT(varchar(20), i.RefType))) AS RefType,
    LTRIM(RTRIM(CONVERT(varchar(255), i.DocName))) AS DocName,
    LTRIM(RTRIM(CONVERT(varchar(255), i.DocType))) AS DocType,
    LTRIM(RTRIM(CONVERT(varchar(20), i.FileExt))) AS FileExt,
    i.IsCompressed,
    i.Blob_Size,
    CONVERT(varchar(23), i.CreatedDT, 121) AS CreatedDT,
    LTRIM(RTRIM(CONVERT(varchar(150), i.CreatedBy))) AS CreatedBy,
    CASE LTRIM(RTRIM(CONVERT(varchar(20), i.RefType)))
        WHEN 'W' THEN 'linked_worksheet'
        WHEN 'P' THEN 'linked_po'
        WHEN '#' THEN 'linked_worksheet'
        WHEN 'E' THEN 'unassigned'
        WHEN 'B' THEN 'unassigned'
        ELSE 'excluded'
    END AS disposition
FROM cieTrade_Documents.dbo.DocumentImage AS i
WHERE UPPER(RTRIM(CONVERT(varchar(128), DBName))) = 'CIETRADE_SM'
ORDER BY i.ImageID;
