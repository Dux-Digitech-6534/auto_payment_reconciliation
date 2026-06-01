# Auto Payment Reconciliation

## Project Overview

`auto_payment_reconciliation` is a custom Frappe/ERPNext app for supplier-wise automatic payment reconciliation.

The app provides a Frappe Desk Page where the user selects only Company. The system automatically finds Suppliers with unreconciled Purchase Invoices or unallocated supplier payments, creates supplier-wise rows, previews allocations, and reconciles through ERPNext native Payment Reconciliation logic.

## App Details

- App name: `auto_payment_reconciliation`
- Module: `Auto Payment Reconciliation`
- Desk Page route: `auto_payment_reconciliation`
- Browser URL: `https://apps.duxdigitech.in/app/auto_payment_reconciliation`
- Frappe site name: `app.duxdigitech.in`
- Bench path: `/home/dux/frappe-bench`
- App path: `/home/dux/frappe-bench/apps/auto_payment_reconciliation`

## Current UI Layout

1. ERPNext Desk topbar/sidebar remains native.
2. Page title: Auto Payment Reconciliation.
3. Breadcrumb/subtitle: Invoicing > Auto Payment Reconciliation.
4. Top action buttons: Get Unreconciled Entries, Allocate, Reconcile.
5. Company Selection section with Company only.
6. Full-width light-blue Current Reconciliation progress banner.
7. Compact top Company Queue section.
8. Supplier-wise Unreconciled Entries table.
9. Bottom actions: Select All Exact Matches and Export.

Not shown in the UI:

- Payment Type
- Party Type
- Party
- Receivable Account
- Payable Account
- Default Advance Account
- Right-side activity panel
- Pause button
- Cancel button
- Supplier ID column in the main table

## Supplier Table Columns

- Checkbox
- Supplier Name
- Invoices
- Payments
- Invoice Amt.
- Payment Amt.
- Difference
- Match Status
- Allocation Status
- Action

Supplier ID is retained internally for references and details, but it is hidden from the main table.

## Current Reconciliation Banner

The top banner is powered by `get_reconciliation_status` and updates during live polling.

Running state shows:

- Company name and Reconciliation in Progress
- Started by user full name
- Started date/time
- Progress bar and percentage
- Current Supplier
- Processed count
- Remaining Time
- Last Updated

Queued state shows:

- Company name and Reconciliation Queued
- Requested by user full name
- Queue Position
- Estimated Start
- Estimated Duration
- Requested On

Completed state shows:

- Reconciled by user full name
- Completed On
- Time Taken
- Processed total
- Progress 100%

Failed state shows:

- Error log
- Time Taken
- Processed count

## Company Queue

The Company Queue appears near the top of the page. It uses real backend queue data and shows queued companies with requested user, waiting status, estimated start, and estimated duration. If no queue exists, it shows `No company is queued.`

## Native ERPNext Reuse

The app reuses ERPNext Payment Reconciliation methods for supplier/payables:

- `get_unreconciled_entries()`
- `allocate_entries()`
- `validate_allocation()`
- `reconcile_allocations()`

The app does not directly edit `GL Entry`, Payment Ledger, or accounting balances.

## Backend Notes

- Public reconciliation flow resolves to supplier/payables (`Pay`) behavior.
- Any hidden `payment_type` metadata is kept only for schema compatibility and is not exposed in the page.
- Queue and progress tracking are stored in `Auto Payment Reconciliation Run`.
- Supplier rows are stored in `Auto Payment Reconciliation Supplier Entry`.
- Run ID naming fix remains intact: `ABBR/APR/FY/0001` or `ABBR/LOC/APR/FY/0001`, never duplicated as `ABBR/ABBR/APR/FY/0001`.

## DocTypes

### Auto Payment Reconciliation Run

Stores run-level tracking: company, account metadata, status, requested/started/reconciled/completed users and dates, duration, total/processed entries, progress, current supplier, queue fields, error log, and supplier child rows.

### Auto Payment Reconciliation Supplier Entry

Stores supplier-level tracking: selected flag, supplier, supplier name, internal supplier ID, invoice/payment counts and totals, difference, match status, allocation status, invoice/payment/allocation JSON, remarks, errors, reconciled user/date, and supplier duration.

## Files Changed - 2026-06-01

- `auto_payment_reconciliation/auto_payment_reconciliation/api.py`
- `auto_payment_reconciliation/auto_payment_reconciliation/auto_payment_reconciliation/page/auto_payment_reconciliation/auto_payment_reconciliation.js`
- `auto_payment_reconciliation/auto_payment_reconciliation/auto_payment_reconciliation/page/auto_payment_reconciliation/auto_payment_reconciliation.css`
- `auto_payment_reconciliation/auto_payment_reconciliation/auto_payment_reconciliation/doctype/auto_payment_reconciliation_run/auto_payment_reconciliation_run.json`
- `README.md`
- `project.md`

## Testing Steps

1. Open `https://apps.duxdigitech.in/app/auto_payment_reconciliation`.
2. Verify only Company appears in Company Selection.
3. Verify Payment Type is not visible.
4. Click Get Unreconciled Entries and confirm supplier rows load automatically.
5. Verify Supplier ID is not visible in the main table.
6. Verify View opens Summary, Invoices, and Payments with clickable document links.
7. Verify Select All Exact Matches selects only Exact Match rows.
8. Verify Allocate works for eligible supplier rows.
9. Verify Reconcile queues/runs through ERPNext native Payment Reconciliation.
10. Verify the top blue banner updates progress/current supplier/remaining time while running.
11. Verify the top queue section shows real queued companies or `No company is queued.`
12. Verify no Pause or Cancel buttons appear.

## Manual Commands

Run manually from bench root:

```bash
cd /home/dux/frappe-bench
env/bin/pip install -e apps/auto_payment_reconciliation
bench --site app.duxdigitech.in migrate
bench --site app.duxdigitech.in clear-cache
bench restart
```

## Known Limitations

- This final UI is supplier/payables-only. Customer/receivable and internal-transfer reconciliation are intentionally not exposed.
- Key CSS is injected from page JS to avoid relying only on `bench build`.

## Layout Note - 2026-06-01

- Current Reconciliation and Company Queue were moved above Company Selection.
