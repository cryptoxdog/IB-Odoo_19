SET NOCOUNT ON;
/* WKSDetail — worksheet lines (buy/sell). No CREATE TABLE.
   DB: cieTrade_SM_EXPORT (not cieTrade_SM, not master).
   Toolbar must show cieTrade_SM_EXPORT. */
SELECT
  DetailID,
  RTRIM(BuySellNo) AS BuySellNo,
  GradeID,
  InvoiceDesc,
  SWeight, SWeightUOM, SPrice, SPriceUOM, SAmount,
  PPrice, PUOM, PAmount, PWeight, PWeightUOM,
  RTRIM(SCurrencyCd) AS SCurrencyCd,
  SFxAmount,
  RTRIM(PCurrencyCd) AS PCurrencyCd,
  PFxAmount,
  Color,
  RTRIM(DesignatedCpID) AS DesignatedCpID,
  SPo, PPo,
  LotNo, UnitType, Units,
  Comment,
  IsReceived, IsItemReceived
FROM dbo.WKSDetail
ORDER BY DetailID;
