# Linda logistics open PRs | Docker pre-merge

Fixture `odoo_test_tpl_ee_c9e8a81f52f23680`, fingerprint `c9e8a81f52f23680595b63d3f5ce3730f95db97195384243ef2fd10b35156c30`, unchanged. Image content `aea60f938586e37745d83a5a65eddefb63c18ede38058272cfeef5f539ab73cb` before and after. Each head was a clean detached worktree. Command: `make test-module m=plasticos_logistics`.

| PR | Head | Clone | Registered tests | Failed | Errors | Exit |
|---|---|---|---|---|---|---|
| #302 | `c3eaed74671092cc68b07cc54d793993d5952fb8` | `odoo_test_w40b4c4db7a` | 4 | 0 | 0 | 0 |
| #304 | `e6e463f5031d3b011986444a8ae59d3b4fdc630f` | `odoo_test_wdb953dba3a` | 73 | 0 | 0 | 0 |
| #305 | `cfffe4527948b9ba77c09bc18d1026252300b86b` | `odoo_test_w4382288706` | 87 | 0 | 0 | 0 |

No registered test failed. None of the three PRs is merge-ready. See `ACTION_ITEMS.md`.

#302 ran only `TestLoadCardinality`. Its PO issuance tests were not collected. #304 ran 43 PO tests, 26 SO tests, and 4 load tests. #305 ran those plus 14 inbound tests. Nineteen freight tests that `Staging` registers were not collected on any of these heads.
