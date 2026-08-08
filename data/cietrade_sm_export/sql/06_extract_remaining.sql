SET NOCOUNT ON;
/*
  Remaining / optional grids only (batches, roles, delivery, docs, prepay).
  One Execute → 7 result grids. Copy each with headers.
  DB: cieTrade_SM_EXPORT
*/

-- ===== 1) ContactRoleAssignment.csv =====
SELECT CRA_ID, CT_ID, RTRIM(RoleNm) AS RoleNm
FROM dbo.ContactRoleAssignment
ORDER BY CRA_ID;

-- ===== 2) PayablesBatch.csv =====
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

-- ===== 3) ReceiptBatch.csv =====
SELECT
  RTRIM(ARBatchNo) AS ARBatchNo, PostType, RTRIM(COID) AS COID, NumOfItems,
  RTRIM(UserID) AS UserID,
  CONVERT(varchar(19), PostingDt, 120) AS PostingDt,
  CONVERT(varchar(19), RecordDate, 120) AS RecordDate,
  RTRIM(CPID) AS CPID, CheckNo, Currency, HcApplyAmt, FxApplyAmt,
  ExportBatchNo, PostedInAccting, DoNotExport
FROM dbo.ReceiptBatch
ORDER BY ARBatchNo;

-- ===== 4) UACashLedger.csv =====
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

-- ===== 5) PrepayLedger.csv =====
SELECT
  PrepayID, InvoiceNo, RTRIM(VendorID) AS VendorID, RTRIM(SONumber) AS SONumber,
  RTRIM(COID) AS COID,
  CONVERT(varchar(19), PostDt, 120) AS PostDt,
  GLAcct, CurrencyCd, Amount, FxAmount, RTRIM(APBatchNo) AS APBatchNo,
  FxRate, SalesTaxCodeID, SalesTaxAmt, SalesTaxAmtFx, FxContractNo
FROM dbo.PrepayLedger
ORDER BY PrepayID;

-- ===== 6) WksDelivery.csv =====
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

-- ===== 7) WksDocument.csv (slim) =====
SELECT
  DocumentID, DocType, RTRIM(BuySellNo) AS BuySellNo,
  CONVERT(varchar(19), CreationDt, 120) AS CreationDt,
  RTRIM(UserID) AS UserID, RefFile,
  FaxRecipiant, FaxNumber, FaxAttn,
  CONVERT(varchar(19), FaxDate, 120) AS FaxDate,
  Notes, LastfaxStatus, FaxJob, LastFaxTime
FROM dbo.WksDocument
ORDER BY DocumentID;
