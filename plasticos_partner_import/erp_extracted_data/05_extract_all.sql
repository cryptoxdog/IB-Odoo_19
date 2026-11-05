SET NOCOUNT ON;
/*
  LEGACY_ERP_SM_EXPORT — ALL P0 extracts in ONE Execute (many result grids).

  Toolbar DB must be: LEGACY_ERP_SM_EXPORT
  Output: Results to Grid

  After Execute: for EACH results tab (Results, Results1, …):
    click grid → Ctrl+A → Ctrl+Shift+C (Copy with Headers)
    → paste into Mac file named as the comment above that SELECT.

  Skip WksDocument huge Field* blobs — slim header/meta only.
*/

-- ===== 1) CounterParty.csv =====
SELECT
  RTRIM(CpID) AS CpID, CompanyNm, Role, ActiveStatus, MasterAccountID, OurCustNo,
  RTRIM(Terms) AS Terms, RTRIM(TermsCode) AS TermsCode, APEMail, PaymentDays,
  CurrCode, OnHold, CreditLimit, CustSvcRep, IndustryNm, WebSite,
  CONVERT(varchar(19), CpLastEdit, 120) AS CpLastEdit
FROM dbo.CounterParty
WHERE ActiveStatus = 'A'
  AND CpID NOT LIKE '(%' AND CpID NOT LIKE '{%' AND CpID NOT LIKE '[%'
ORDER BY CpID;

-- ===== 2) Address.csv =====
SELECT
  AddressID, RTRIM(CpID) AS CpID, RTRIM(Type) AS Type,
  Addr1, Addr2, Addr3, City, Region, PostalCd, Country,
  Telephone, Fax, Email, MobilePhone,
  InvoiceAddr, RemitToAddress, isBillingAddressOnly, BillingEmail
FROM dbo.Address
ORDER BY AddressID;

-- ===== 3) Contact.csv =====
SELECT
  CT_ID, RTRIM(CpID) AS CpID, ContactNm, CompanyNm,
  RTRIM(Location) AS Location, Email,
  PhoneBusiness, PhoneMobile, PhoneOther,
  RTRIM(IsActive) AS IsActive, Notes
FROM dbo.Contact
ORDER BY CT_ID;

-- ===== 4) ContactRoleAssignment.csv =====
SELECT CRA_ID, CT_ID, RTRIM(RoleNm) AS RoleNm
FROM dbo.ContactRoleAssignment
ORDER BY CRA_ID;

-- ===== 5) Payables.csv =====
SELECT
  PayableID, RTRIM(BuySellNo) AS BuySellNo, ItemID, RTRIM(CpID) AS CpID,
  Amount, FxAmount, CurrencyCd, InvoiceNo,
  CONVERT(varchar(19), InvoiceDt, 120) AS InvoiceDt,
  CONVERT(varchar(19), RcvDt, 120) AS RcvDt,
  Posted, IsCheck, CheckNo, RTRIM(APBatchNo) AS APBatchNo,
  CONVERT(varchar(19), Reference_Date, 120) AS Reference_Date, GLAcct
FROM dbo.Payables
ORDER BY PayableID;

-- ===== 6) PayablesBatch.csv =====
SELECT
  RTRIM(APBatchNo) AS APBatchNo, RTRIM(COID) AS COID, NumofItems, RTRIM(UserID) AS UserID,
  CONVERT(varchar(19), PostingDt, 120) AS PostingDt,
  FXAmount, CurrencyCd, PostedInAccting, Comment, APTerms,
  CONVERT(varchar(19), RecordDate, 120) AS RecordDate,
  RTRIM(CpID) AS CpID, InvoiceNo, PrePay, ExportBatchNo,
  CONVERT(varchar(19), InvoiceDt, 120) AS InvoiceDt,
  FxRate, FxDiscountAmt, DoNotExport,
  CONVERT(varchar(19), DueDate, 120) AS DueDate,
  ReversedFxAmt, ReverseBatchNo
FROM dbo.PayablesBatch
ORDER BY APBatchNo;

-- ===== 7) Receipt.csv =====
SELECT
  ReceiptID, RTRIM(BuySellNo) AS BuySellNo, Amount, FxAmount, CurrencyCd,
  RTRIM(CheckNo) AS CheckNo,
  CONVERT(varchar(19), PaymentDt, 120) AS PaymentDt,
  CONVERT(varchar(19), EntryDt, 120) AS EntryDt,
  DiscountAmt, LedgerID, PostingType, Reference,
  CONVERT(varchar(19), DepositDate, 120) AS DepositDate,
  RTRIM(ARBatchNo) AS ARBatchNo
FROM dbo.Receipt
ORDER BY ReceiptID;

-- ===== 8) ReceiptBatch.csv =====
SELECT
  RTRIM(ARBatchNo) AS ARBatchNo, PostType, RTRIM(COID) AS COID, NumOfItems,
  RTRIM(UserID) AS UserID,
  CONVERT(varchar(19), PostingDt, 120) AS PostingDt,
  CONVERT(varchar(19), RecordDate, 120) AS RecordDate,
  RTRIM(CPID) AS CPID, CheckNo, Currency, HcApplyAmt, FxApplyAmt,
  ExportBatchNo, PostedInAccting, DoNotExport
FROM dbo.ReceiptBatch
ORDER BY ARBatchNo;

-- ===== 9) GPLedger.csv =====
SELECT
  LedgerID,
  CONVERT(varchar(19), TradeDt, 120) AS TradeDt,
  RTRIM(BuySellNo) AS BuySellNo,
  Source, Sale, Cost, GrossProfit, Commission,
  RTRIM(AdjCpID) AS AdjCpID, AdjType, AdjFxAmount,
  RTRIM(APBatchNo) AS APBatchNo, RTRIM(ARBatchNo) AS ARBatchNo, ReferenceID
FROM dbo.GPLedger
ORDER BY LedgerID;

-- ===== 10) UACashLedger.csv =====
SELECT
  LedgerID, RTRIM(CustID) AS CustID,
  CONVERT(varchar(19), EntryDt, 120) AS EntryDt,
  OriginalAmount, RTRIM(CheckNo) AS CheckNo, Balance, Reference,
  CurrencyCd, FxAmount, FxBalance, GLAcct, RTRIM(COID) AS COID,
  Reversed, Reversed_LedgerID, Deposited, RTRIM(DepositNo) AS DepositNo,
  CONVERT(varchar(19), DepositDate, 120) AS DepositDate,
  DepositUser, FxRate, BankFees, FXBankFees, BankFee_GPLedgerID,
  FactorID, FactorGLAcct, RTRIM(ARBatchNo) AS ARBatchNo, Notes, TradeType
FROM dbo.UACashLedger
ORDER BY LedgerID;

-- ===== 11) PrepayLedger.csv =====
SELECT
  PrepayID, InvoiceNo, RTRIM(VendorID) AS VendorID, RTRIM(SONumber) AS SONumber,
  RTRIM(COID) AS COID,
  CONVERT(varchar(19), PostDt, 120) AS PostDt,
  GLAcct, CurrencyCd, Amount, FxAmount, RTRIM(APBatchNo) AS APBatchNo,
  FxRate, SalesTaxCodeID, SalesTaxAmt, SalesTaxAmtFx, FxContractNo
FROM dbo.PrepayLedger
ORDER BY PrepayID;

-- ===== 12) WKSDetail.csv =====
SELECT
  DetailID, RTRIM(BuySellNo) AS BuySellNo, GradeID, InvoiceDesc,
  SWeight, SWeightUOM, SPrice, SPriceUOM, SAmount,
  PPrice, PUOM, PAmount, PWeight, PWeightUOM,
  RTRIM(SCurrencyCd) AS SCurrencyCd, SFxAmount,
  RTRIM(PCurrencyCd) AS PCurrencyCd, PFxAmount,
  Color, RTRIM(DesignatedCpID) AS DesignatedCpID, SPo, PPo,
  LotNo, UnitType, Units, Comment, IsReceived, IsItemReceived
FROM dbo.WKSDetail
ORDER BY DetailID;

-- ===== 13) WksDelivery.csv =====
SELECT
  ItemID, RTRIM(BuySellNo) AS BuySellNo, RTRIM(VendorID) AS VendorID,
  TrailerNo,
  CONVERT(varchar(19), DeliveryDt, 120) AS DeliveryDt,
  Cost, ChgToCustAmt, InvoiceDesc, Mileage, PrintOnInvoice,
  CurrencyCd, CurrencyCdCust, FxAmount, FxAmountCust, GLAcct, Manifest,
  PrepaidFreight, PFreightCurCode, Price, PricePer, PriceCust, PricePerCust,
  CONVERT(varchar(19), DeliveryTime, 120) AS DeliveryTime,
  FxRate, FxContractNo, ExpSalesFxRate, ReferenceID, DetailID, IsJobFreightExp
FROM dbo.WksDelivery
ORDER BY ItemID;

-- ===== 14) WksDocument.csv (slim — no Field* blobs) =====
SELECT
  DocumentID, DocType, RTRIM(BuySellNo) AS BuySellNo,
  CONVERT(varchar(19), CreationDt, 120) AS CreationDt,
  RTRIM(UserID) AS UserID, RefFile,
  FaxRecipiant, FaxNumber, FaxAttn,
  CONVERT(varchar(19), FaxDate, 120) AS FaxDate,
  Notes, LastfaxStatus, FaxJob, LastFaxTime
FROM dbo.WksDocument
ORDER BY DocumentID;
