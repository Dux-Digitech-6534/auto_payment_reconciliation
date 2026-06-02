# Auto Payment Reconciliation

Supplier-wise automatic payment reconciliation for ERPNext.

This custom app adds a Frappe Desk page at `auto_payment_reconciliation`. A user selects only a Company, loads supplier-wise unreconciled Purchase Invoices and supplier payments, reviews matches, allocates selected suppliers, and reconciles through ERPNext native Payment Reconciliation methods.

## Final Layout Update - 2026-06-01

Files changed in this update:

- `auto_payment_reconciliation/auto_payment_reconciliation/api.py`
- `auto_payment_reconciliation/auto_payment_reconciliation/auto_payment_reconciliation/page/auto_payment_reconciliation/auto_payment_reconciliation.js`
- `auto_payment_reconciliation/auto_payment_reconciliation/auto_payment_reconciliation/page/auto_payment_reconciliation/auto_payment_reconciliation.css`
- `auto_payment_reconciliation/auto_payment_reconciliation/auto_payment_reconciliation/doctype/auto_payment_reconciliation_run/auto_payment_reconciliation_run.json`
- `README.md`
- `project.md`

What changed:

- Payment Type was removed from the visible UI.
- Company Selection now shows only the Company field and helper text.
- Supplier/payables flow is restored as the default and enforced behavior.
- Supplier ID remains stored internally but is not shown in the main table.
- The old right-side/card activity panel was removed.
- A full-width light-blue Current Reconciliation banner was added near the top.
- Company Queue was moved to a compact top section.
- Pause and Cancel actions were intentionally not added.
- Live status polling remains active every 4 seconds while a run is queued or running.

## Native ERPNext Reuse

The app continues to use ERPNext native Payment Reconciliation logic for supplier/payables:

- `get_unreconciled_entries()`
- `allocate_entries()`
- `validate_allocation()`
- `reconcile_allocations()`

The app does not directly edit `GL Entry` and does not manually patch accounting balances.

## Manual Commands

Run these manually from the bench root after pulling or editing the app:

```bash
cd /home/dux/frappe-bench
env/bin/pip install -e apps/auto_payment_reconciliation
bench --site app.duxdigitech.in migrate
bench --site app.duxdigitech.in clear-cache
bench restart
```

## Correct URL

```text
https://apps.duxdigitech.in/app/auto_payment_reconciliation
```

## Testing Steps

1. Open `https://apps.duxdigitech.in/app/auto_payment_reconciliation`.
2. Confirm Company Selection shows only Company.
3. Confirm Payment Type, Party Type, Party, Payable Account, Receivable Account, and Default Advance Account are not visible.
4. Select Company and click Get Unreconciled Entries.
5. Confirm supplier-wise rows load automatically.
6. Confirm visible columns are Checkbox, Supplier Name, Invoices, Payments, Invoice Amt., Payment Amt., Difference, Match Status, Allocation Status, and Action.
7. Confirm Supplier ID is not visible in the main table.
8. Confirm filters, badges, red/green Difference, row selection, View, Allocate, Reconcile, and Export work.
9. Start reconciliation and confirm the top blue banner updates progress, current supplier, processed count, remaining time, and queue.
10. Confirm no Pause or Cancel controls are shown.

## Known Notes

- The `payment_type` field may still exist as hidden backend metadata for compatibility with already-synced DocType schema, but the page does not display it and server-side public flow resolves to supplier/payables.
- The page JS injects key CSS so the layout can update after migrate/clear-cache even if bench build is not run.

## Layout Note - 2026-06-01

- Current Reconciliation and Company Queue were moved above Company Selection.

## Post-Reconciliation Refresh Note - 2026-06-02

- After each supplier is reconciled, `_reconcile_supplier_for_run()` calls `_refresh_supplier_row()`, which rebuilds the row through `_build_supplier_row()` using fresh ERPNext native Payment Reconciliation unreconciled data.
- The refreshed fields include `invoices_count`, `payments_count`, `invoice_amount`, `payment_amount`, `difference`, `match_status`, `allocation_status`, `invoice_refs_json`, and `payment_refs_json`.
- `get_reconciliation_status()` now returns the current run rows so the page polling refreshes the supplier-wise table after reconciliation, instead of keeping stale child-table values in the browser.
