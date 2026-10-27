# Open decision and runtime proof frontier

These are **not** silently decided by the logistics BRS installation:

1. Exact installed Odoo Enterprise AI module/action field/schema, permissions and vendor cost; live AI tests must be run and approval obtained before activating free-form interpretation (`BRS-02-R012`, `R062`).
2. Whether identity of inbound mail can be proven from native authentication headers/OAuth/provider evidence in deployed Google Workspace; a matching From alone does not authenticate a business commitment (`BRS-02-R011`).
3. Local holiday calendar and policy for business-day SLA beyond Mon-Fri (`BRS-07-R051`).
4. Numerator/denominator and rounding on the strictly >5% supplier-vs-buyer weight reconciliation (`BRS-07-R052`).
5. CST $150 charge event, cure/late reversal and contractual liability. No automatic debit/credit or AR/AP booking (`BRS-07-R048`, `R054`).
6. Real pickup/delivery timestamps and selected verified source for each document deadline; historical `create_date` is invalid (`BRS-06-R039`, `BRS-07-R051`).
7. Exact native Documents Request internal recipient and access controls: no external Documents invitation or reminder by default (`BRS-07-R046`, `R051`).
8. Actual native Documents multi-link/attachment/alias semantics in installed EE; typed PlasticOS evidence links must be measured and not invented (`BRS-07-R046`..`R050`).
9. Company-safe carrier/supplier/buyer QWeb report variants, especially the existing dropship PO buyer-address leak (`BRS-05-R031`).
10. Native mail throttle per-owner server and concurrency semantics, canonical single SO confirmation owner in off/shadow/live, queue crash ambiguity (`BRS-05-R034`/`R035`).
11. Native Stock route and real picking state in 3PL/PO-only/dropship/SO-from-inventory; `assigned` is not dispatched (`BRS-05-R029`, `BRS-07-R053`).
12. Financial posting and claims reconciliation under accountant control. QuickBooks still owns bank payments until separate cutover (`BRS-07-R054`).
13. Live recurring automation and external communication activation remains separately operator-authorized; BRS installation never grants it.
14. Existing open #302/#304/#305 heads and new descendant PR's actual merge-base must be rechecked at execution. Remediation v2 patch utility pinned to #305 must not be run unchanged after this BRS PR creates a new parent.
15. Branch integration 2026-10-27: non-documentation blobs on this branch match #316 head `53b18fd90046696e946a0d8e1e60e88595a5e143`. The logistics alignment overlay that arrived with closed #317 stays in this tree with the Documents chapters. Mail throttle, cancellation notices, stock-reservation dispatch, and the supplier PO report remain #316's runtime. This overlay leaves native AI, Documents Requests, mail, cron, and financial posting unexecuted. Publish only after #316 is on Staging.
