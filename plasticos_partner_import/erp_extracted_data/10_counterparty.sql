SET NOCOUNT ON;
/* Full active CounterParty — no row limit (clipboard OK per operator) */
SELECT
  RTRIM(CpID) AS CpID,
  CompanyNm,
  Role,
  ActiveStatus,
  MasterAccountID,
  OurCustNo,
  RTRIM(Terms) AS Terms,
  RTRIM(TermsCode) AS TermsCode,
  APEMail,
  PaymentDays,
  CurrCode,
  OnHold,
  CreditLimit,
  CustSvcRep,
  IndustryNm,
  WebSite,
  CONVERT(varchar(19), CpLastEdit, 120) AS CpLastEdit
FROM dbo.CounterParty
WHERE ActiveStatus = 'A'
  AND CpID NOT LIKE '(%'
  AND CpID NOT LIKE '{%'
  AND CpID NOT LIKE '[%'
ORDER BY CpID;
