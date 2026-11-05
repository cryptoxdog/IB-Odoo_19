SET NOCOUNT ON;
/* WksDelivery — single-result form of the SELECT in 05_extract_all.sql. */
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
