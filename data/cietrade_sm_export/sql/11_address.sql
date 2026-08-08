SET NOCOUNT ON;
/* Full Address — no row limit */
SELECT
  AddressID,
  RTRIM(CpID) AS CpID,
  RTRIM(Type) AS Type,
  Addr1, Addr2, Addr3, City, Region, PostalCd, Country,
  Telephone, Fax, Email, MobilePhone,
  InvoiceAddr, RemitToAddress, isBillingAddressOnly, BillingEmail
FROM dbo.Address
ORDER BY AddressID;
