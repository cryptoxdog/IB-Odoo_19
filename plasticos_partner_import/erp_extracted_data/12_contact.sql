SET NOCOUNT ON;
/* Full Contact — no IsActive filter (char values may not be plain Y) */
SELECT
  CT_ID,
  RTRIM(CpID) AS CpID,
  ContactNm,
  CompanyNm,
  RTRIM(Location) AS Location,
  Email,
  PhoneBusiness,
  PhoneMobile,
  PhoneOther,
  RTRIM(IsActive) AS IsActive,
  Notes
FROM dbo.Contact
ORDER BY CT_ID;
