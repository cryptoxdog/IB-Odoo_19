---
auto_generated: false
authority: derived-index
component_id: plasticos_accounting
component_name: PlasticOS Accounting
module_version: 19.0.1.6.3
layer: 3
installable: true
auto_install: true
application: false
depends:
  - account
models_owned: []
models_extended: []
crons: []
---

# PlasticOS Accounting

The front matter above is a derived index. `__manifest__.py` wins on any conflict.

## What it does

Seed data for Odoo Accounting: the PlasticOS payment terms and chart-of-accounts entries.

## How it works

- **Payment terms.** `data/payment_terms.xml` creates nine `account.payment.term` records inside `<data noupdate="1">`, so an upgrade does not overwrite local edits.
- **Accounts.** `data/accounts.xml` creates 58 `account.account` records inside `<data noupdate="0">`, so an upgrade reloads them from the file.
- **Install hook.** `pre_init_hook` in `__init__.py` checks whether `account_account` has a `create_asset` column (added by Enterprise `account_asset`). Only when it exists does the hook set that column's database default to `no`, so the account inserts do not hit its NOT NULL constraint.

## Models

None. The module defines and extends no model. It has no `models/` package.

## Runtime

- No cron, no views, no access file.
- `auto_install` is true: Odoo installs it once Accounting is installed.
- The manifest summary also names incoterms. No data file in this module seeds incoterms.

## Boundaries

- Data only. No invoice, payment, or posting logic.
- The account and term records are the files' contents; read them there rather than in this page.

## Read next

- [`data/payment_terms.xml`](data/payment_terms.xml)
- [`data/accounts.xml`](data/accounts.xml)
- [`__init__.py`](__init__.py)
