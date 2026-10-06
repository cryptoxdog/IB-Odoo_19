SET NOCOUNT ON;
/* Full ContactRoleAssignment — no row limit.
   Single-table form of grid 4 in 05_extract_all.sql / grid 1 in 06_extract_remaining.sql,
   so the direct database read (plasticos_partner_import/erp/reader.py) can execute
   this projection on its own. Column set and ordering are unchanged. */
SELECT CRA_ID, CT_ID, RTRIM(RoleNm) AS RoleNm
FROM dbo.ContactRoleAssignment
ORDER BY CRA_ID;
