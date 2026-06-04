# Auto Payment Reconciliation App Analysis

Analysis date: 2026-06-04
Server inspected: 147.93.106.128
Bench path: /home/dux/frappe-bench
App path: /home/dux/frappe-bench/apps/auto_payment_reconciliation

This file documents the existing `auto_payment_reconciliation` custom app only. No implementation, migration, build, restart, cache clear, install, uninstall, or database update/delete command was run during this analysis.

## 1. App Overview

- App name: `auto_payment_reconciliation`
- App title: `Auto Payment Reconciliation`
- Publisher: Dux Digitech
- Purpose: supplier-wise automatic payment reconciliation for ERPNext payables.
- Desk Page route: `auto_payment_reconciliation`
- Desk URL pattern: `/app/auto_payment_reconciliation`
- Documented production URL in README/project notes: `https://apps.duxdigitech.in/app/auto_payment_reconciliation`

The app provides a custom Frappe Desk Page where the user selects a Company, loads supplier-wise unreconciled Purchase Invoices and supplier payments, reviews matching status, previews allocation, queues reconciliation, tracks progress, views supplier details, and exports supplier-wise rows.

The current public flow is supplier-wise only. The backend contains context definitions for Receive and Internal Transfer, but `_payment_type(filters)` always returns `Pay`, so all public page/API flows resolve to:

- Party Type: Supplier
- Invoice DocType: Purchase Invoice
- Payment Entry type: Pay
- Account type: Payable
- Root type: Liability

Current UI flow:

1. Open the Desk page at `/app/auto_payment_reconciliation`.
2. Select Company. The control defaults to `frappe.defaults.get_default("company")` when available.
3. Click Get Unreconciled Entries.
4. App creates or reuses an active `Auto Payment Reconciliation Run` and loads supplier-wise child rows.
5. User filters/searches rows, views details, selects rows, optionally clicks Allocate, then Reconcile.
6. Reconcile queues a background job. A top banner and queue section update through polling every 4 seconds.
7. Export downloads a CSV for the current run.

## 2. Folder/File Structure

Important files found:

- `hooks.py`
  - Defines app metadata, title, publisher, license, and required apps `frappe` and `erpnext`.
- `auto_payment_reconciliation/api.py`
  - Main backend logic and page APIs.
  - Includes supplier discovery, native Payment Reconciliation wrappers, run creation/reuse, queue logic, allocation, reconciliation, export, and status polling.
- Page files:
  - `auto_payment_reconciliation/auto_payment_reconciliation/page/auto_payment_reconciliation/auto_payment_reconciliation.js`
  - `auto_payment_reconciliation/auto_payment_reconciliation/page/auto_payment_reconciliation/auto_payment_reconciliation.css`
  - `auto_payment_reconciliation/auto_payment_reconciliation/page/auto_payment_reconciliation/auto_payment_reconciliation.json`
- DocType files:
  - `auto_payment_reconciliation/auto_payment_reconciliation/doctype/auto_payment_reconciliation_run/auto_payment_reconciliation_run.py`
  - `auto_payment_reconciliation/auto_payment_reconciliation/doctype/auto_payment_reconciliation_run/auto_payment_reconciliation_run.json`
  - `auto_payment_reconciliation/auto_payment_reconciliation/doctype/auto_payment_reconciliation_supplier_entry/auto_payment_reconciliation_supplier_entry.py`
  - `auto_payment_reconciliation/auto_payment_reconciliation/doctype/auto_payment_reconciliation_supplier_entry/auto_payment_reconciliation_supplier_entry.json`
- Workspace/module files:
  - `auto_payment_reconciliation/auto_payment_reconciliation/workspace/auto_payment_reconciliation/auto_payment_reconciliation.json`
  - `auto_payment_reconciliation/auto_payment_reconciliation/module_def/auto_payment_reconciliation/auto_payment_reconciliation.json`
  - `auto_payment_reconciliation/config/desktop.py`
  - `auto_payment_reconciliation/modules.txt`
- Documentation/project files:
  - `README.md`
  - `project.md`
- Setup/package files:
  - `pyproject.toml`
  - `setup.py`
  - `MANIFEST.in`
- Other utility:
  - `auto_payment_reconciliation/test_data.py` contains a whitelisted test data creation helper. It is not part of the normal page flow and was not run.

## 3. UI Analysis

Page title:

- Frappe page title: `Auto Payment Reconciliation`
- Breadcrumb/subtitle area: `Invoicing > Auto Payment Reconciliation`
- Helper text: supplier-wise automatic payment reconciliation using ERPNext accounting data.

Company selection:

- Visible field: Company Link field.
- Source: ERPNext Company master.
- The visible UI does not ask for Supplier, Payment Type, Party Type, Payable Account, Receivable Account, or Default Advance Account.

Current Reconciliation banner:

- Full-width status banner near the top of the page.
- Shows no active reconciliation, running, queued, completed, failed, or draft/not-started state.
- Running state shows company, started by, started on, progress, current supplier, processed count, remaining time, and last updated.
- Queued state shows company, requested by, queue position, estimated start, estimated duration, and requested on.
- Completed state shows reconciled by, completed on, time taken, processed total, and progress 100%.
- Failed state shows error log, completed/time taken, processed count, and progress.

Company Queue section:

- Compact top section below the Current Reconciliation banner.
- Populated by `get_reconciliation_status()` from queued runs.
- Shows queue position, company, requested by, start estimate, estimated duration, and status.
- If no queue exists, it shows `No company is queued.`

Supplier-wise table:

Visible columns:

- Checkbox
- Supplier Name
- Invoices
- Payments
- Invoice Amt.
- Payment Amt.
- Difference
- Match Status
- Allocation Status
- Action/View

Visible filters/actions above or below the table:

- Search Supplier
- All Match Statuses dropdown
- Amount Range text input
- Date Range text input
- Show Only Exact Matches checkbox
- Select All Exact Matches button
- Export button

View dialog:

- Opens from the View button.
- Dialog title includes supplier name and supplier ID.
- Tabs: Summary, Invoices, Payments.
- Summary shows Supplier, Supplier ID, Company, Run ID, invoice/payment counts, totals, difference, match/allocation status, reconciled by/on, time taken, and remarks/errors.
- Invoice table shows invoice type, invoice number, posting date, due date, outstanding amount, currency, and account.
- Payment table shows payment document, reference name, posting date, unallocated amount, currency, and account.

Buttons:

- Get Unreconciled Entries
  - Calls `auto_payment_reconciliation.api.get_unreconciled_entries`.
  - Loads or reuses a run and updates the table.
- Allocate
  - Calls `auto_payment_reconciliation.api.allocate_selected` for selected suppliers.
  - Enabled only when at least one selected row can allocate.
- Reconcile
  - Calls `auto_payment_reconciliation.api.reconcile_selected` after confirmation.
  - Queues a background reconciliation run and starts polling.
- Export
  - Calls `auto_payment_reconciliation.api.export_unreconciled_entries`.
  - Downloads a CSV in browser using a Blob.
- View
  - Calls `auto_payment_reconciliation.api.get_supplier_details`.

Hidden/not shown in current UI:

- Payment Type
- Party Type
- Party selector
- Supplier ID column in the main table
- Receivable Account
- Payable Account
- Default Advance Account
- Right-side activity panel
- Pause button
- Cancel button
- Source voucher/source doctype fields

Important UI risk:

- Invoice/payment document links use `frappe.set_route("Form", doctype, name)`, so they open in the same Desk tab instead of a new browser tab.

## 4. Backend/API Analysis

Main whitelisted methods in `auto_payment_reconciliation/api.py`:

### `get_unreconciled_entries(company, filters=None)`

- Requires page access with write permission.
- Validates selected Company.
- Parses filters and creates/reuses an active run.
- If run is not queued/running, finds candidate suppliers and appends supplier rows.
- Returns run name, company, currency, payment type, party type/label, rows, and status.

### `get_supplier_details(company, supplier, filters=None)`

- Requires page read access.
- Validates Company.
- Uses current run row if present; otherwise rebuilds supplier row from fresh native data.
- Returns summary, invoice refs, and payment refs for the View dialog.

### `allocate_supplier(company, supplier, filters=None, preview=True)`

- Requires page write access.
- Validates Company.
- Rebuilds one supplier row and returns allocation preview JSON plus eligibility flags.
- This method exists but the current page uses `allocate_selected` for the Allocate button.

### `allocate_selected(run_name, suppliers)`

- Requires page write access.
- Rebuilds selected supplier rows from current native data.
- Updates allocation JSON/status in child rows.
- Skips ineligible suppliers and records messages.
- Catches per-supplier failures and marks child rows as Error.
- Has a specific retry/friendly response path for `frappe.TimestampMismatchError`.

### `reconcile_supplier(company, supplier, allocations=None)`

- Requires page write access.
- Validates Company.
- Creates an ad-hoc new run for one supplier, refreshes row, reconciles, then inserts the run.
- The `allocations` argument is accepted but not used.
- This method is not used by the current page flow.

### `reconcile_selected(run_name, suppliers)`

- Requires page write access.
- Checks selected suppliers and current run status.
- Prevents duplicate queued/running reconciliation for the same company.
- Marks eligible child rows selected.
- Sets run status to Queued and stores queue/progress tracking fields.
- Enqueues `auto_payment_reconciliation.api.process_reconciliation_run` when no other run is active.
- Returns rows and status data for immediate UI update.

### `process_reconciliation_run(run_name)`

- Whitelisted background worker method.
- Processes selected suppliers one by one.
- Sets status Running, updates current supplier, progress, remaining time, and commits between suppliers.
- Calls `_reconcile_supplier_for_run()` for each supplier.
- Sets final run status to Completed or Failed.
- Starts the next queued run after finishing.
- Risk: it is whitelisted and does not call `_require_page_access()` directly. Since it writes using `ignore_permissions=True`, review whether it should remain externally callable or be restricted to background execution.

### `export_unreconciled_entries(run_name)`

- Requires page read access.
- Reads run child rows and returns CSV content, filename, and content type.
- Export includes supplier ID and JSON refs even though supplier ID is hidden in the main table.

### `get_reconciliation_status(run_name=None, company=None)`

- Requires page read access.
- Returns currently running run, current run if `run_name` is supplied and no running run exists, queued runs, and current rows for the supplied run.
- Adds display names and relative queue timing fields.
- Returns fresh child rows from the run document for frontend polling.

Other whitelisted method found:

### `create_bulk_reconciliation_test_data(...)` in `auto_payment_reconciliation/test_data.py`

- Creates idempotent APR-TEST suppliers, Purchase Invoices, and Payment Entries for testing.
- Default `dry_run=True` reports a plan only.
- Can create and submit ERPNext documents if called with non-dry-run options.
- Not part of the production page flow and was not executed during this analysis.

## 5. DocType Analysis

### Auto Payment Reconciliation Run

Purpose:

- Stores run-level state for supplier-wise reconciliation.
- Tracks filters, queue status, progress, timing, errors, and child supplier rows.

Important fields:

- `company`: Company Link, required.
- `payment_type`: hidden/read-only Select, default Pay.
- `payable_account`: Account Link.
- `default_advance_account`: Account Link.
- `from_date`, `to_date`: optional Date filters.
- `status`: Draft, Queued, Running, Completed, Failed, Cancelled.
- `requested_by`, `requested_on`: queue/request tracking.
- `started_by`, `started_on`: run start tracking.
- `reconciled_by`, `reconciled_on`: reconciliation ownership/time.
- `completed_on`, `duration_seconds`, `duration_display`: completion tracking.
- `total_entries`, `processed_entries`, `progress_percent`, `remaining_time`, `last_updated_on`, `current_supplier`: progress tracking.
- `queue_position`, `estimated_start`, `estimated_duration`: queue tracking.
- `error_log`: Long Text.
- `supplier_entries`: Table of `Auto Payment Reconciliation Supplier Entry`.

Naming logic:

- Implemented in the DocType controller, not in the JSON `autoname` property.
- `autoname()` calls `_assign_run_name()`.
- `before_insert()` reassigns if missing or if a duplicate abbreviation segment pattern is detected.

Status fields:

- Main status: `status`.
- Progress fields: `total_entries`, `processed_entries`, `progress_percent`, `remaining_time`, `current_supplier`.
- Failure field: `error_log`.

Child table relation:

- Parent field `supplier_entries` is a Table field with options `Auto Payment Reconciliation Supplier Entry`.

Permissions visible in JSON:

- Accounts Manager: create, read, write, delete, export, report, print, email, share.
- Accounts User: create, read, write, export, report, print, email, share. No delete.
- System Manager: create, read, write, delete, export, report, print, email, share.

### Auto Payment Reconciliation Supplier Entry

Purpose:

- Child table row for one supplier/party in a reconciliation run.
- Stores source refs, calculated totals, matching/allocation status, reconciliation result, and per-supplier timing/errors.

Important fields:

- `selected`: Check, used when reconciling selected rows.
- `party_type`: hidden Link to DocType, default Supplier.
- `supplier`: Dynamic Link using `party_type`.
- `supplier_name`: display name.
- `supplier_id`: internal party ID.
- `invoices_count`, `payments_count`: counts from native Payment Reconciliation data.
- `invoice_amount`, `payment_amount`, `difference`: calculated totals.
- `match_status`: Exact Match, Partial Match, Needs Review.
- `allocation_status`: Ready for Allocation, Auto Allocated, Pending Review, Reconciled, Error.
- `invoice_refs_json`, `payment_refs_json`, `allocation_refs_json`: serialized source/preview details.
- `remarks`, `last_error`: notes and errors.
- `reconciled_by`, `reconciled_on`, `duration_seconds`, `duration_display`: per-supplier completion tracking.

Naming logic:

- No custom controller naming logic.
- It is an `istable` child DocType; Frappe assigns child row names.

Permissions:

- JSON has an empty `permissions` list because this is a child table.
- Access is controlled through the parent Run document.

## 6. Naming Logic Analysis

Current Run ID format:

- Without location: `<COMPANY_ABBR>/APR/<FY>/<NUMBER>`
- With location: `<COMPANY_ABBR>/<LOCATION>/APR/<FY>/<NUMBER>`
- Example shape: `ABC/APR/26-27/0001`
- Example shape with location: `ABC/MUMBAI/APR/26-27/0001`

Company abbreviation logic:

- Reads first available Company field from `abbr`, `company_abbr`, `abbreviation`.
- Sanitizes to uppercase alphanumeric only.
- If no abbreviation exists, falls back to company initials.
- If initials are unavailable, falls back to `APR`.

Location logic:

- Reads first available Company field from:
  - `location`
  - `custom_location`
  - `campus`
  - `custom_campus`
  - `branch`
  - `custom_branch`
  - `city`
  - `custom_city`
- Sanitizes to uppercase alphanumeric only.
- Adds location segment only when it exists and is not equal to company abbreviation.

Financial year logic:

- Uses `from_date` if present; otherwise current date.
- Financial year starts in April.
- If month is April or later, start year is current year.
- If month is before April, start year is previous year.
- Format is `YY-YY`.

Running number logic:

- `_next_run_name(prefix)` searches latest existing name matching the prefix.
- Reads trailing numeric segment with regex `/(\d{4,})$`.
- Increments by 1 and formats with at least 4 digits.
- There is no explicit database lock around the sequence, so simultaneous inserts for the same prefix could theoretically collide.

Duplicate ABBR/ABBR handling:

- `_run_name_prefix()` does not add location if `location == abbr`.
- `_has_duplicate_abbr_segment()` detects existing bad shape `ABBR/ABBR/APR/FY/NUMBER`.
- `before_insert()` reassigns the name if that duplicate pattern is found.
- `_find_reusable_run()` skips the bad literal name `APR-#####`.

## 7. Reconciliation Logic Analysis

How suppliers are fetched:

- `_candidate_suppliers(company, filters)` builds a supplier set from custom queries before building native rows.
- Sources:
  - Submitted Purchase Invoices with `outstanding_amount > 0`.
  - Submitted Payment Entries with `payment_type = Pay`, `party_type = Supplier`, and `unallocated_amount > 0`.
  - Submitted Journal Entry Accounts with Supplier party, no reference type, and a positive amount for the Pay context.
- Optional date filters are applied to invoice/payment/journal posting dates.
- Optional payable account filter is considered for Journal Entry Account.
- Suppliers are sorted by supplier display name.

How invoice/payment counts are calculated:

- `_build_supplier_row()` creates a native ERPNext `Payment Reconciliation` document for one supplier.
- It calls `pr.get_unreconciled_entries()`.
- Invoice rows are serialized from `pr.invoices`.
- Payment rows are serialized from `pr.payments` and filtered to Payment Entry or Journal Entry refs.
- Counts are `len(invoices)` and `len(payments)`.
- Invoice amount is sum of `outstanding_amount`.
- Payment amount is sum of `unallocated_amount`.
- Difference is `invoice_amount - payment_amount` using company currency precision.

How allocation works:

- `_allocation_preview_from_pr(pr)` converts native invoice/payment child rows to dictionaries.
- It calls `pr.allocate_entries({"invoices": invoices, "payments": payments})`.
- Allocation preview is stored in `allocation_refs_json`.
- Exact matches become `Auto Allocated` when allocations exist.
- Partial matches become `Ready for Allocation` when allocations exist.
- Missing preview becomes `Pending Review`.
- Allocation errors become `Error` with remarks/last_error.

How reconcile works:

- `reconcile_selected()` queues selected eligible suppliers on the run.
- `process_reconciliation_run()` processes selected suppliers sequentially.
- `_reconcile_supplier_for_run()` checks eligibility, reloads native unreconciled entries, allocates, validates, reconciles, refreshes the row, and records per-supplier duration.
- On supplier exception, it rolls back to a savepoint and marks that supplier row `Error`.

ERPNext native Payment Reconciliation methods reused:

- `get_unreconciled_entries()`
- `allocate_entries()`
- `validate_allocation()`
- `reconcile_allocations()`

GL Entry handling:

- The app does not directly edit `GL Entry`.
- No direct `GL Entry` update/delete logic was found.
- Accounting changes are delegated to native ERPNext Payment Reconciliation.
- The only direct `frappe.db.set_value()` found is for queue position tracking on the custom Run DocType.

## 8. Post-Reconciliation Refresh Analysis

Function that refreshes row after reconcile:

- `_reconcile_supplier_for_run()` calls `_refresh_supplier_row()` after `pr.reconcile_allocations()` succeeds.
- `_refresh_supplier_row()` calls `_build_supplier_row()` again, which reloads native ERPNext Payment Reconciliation unreconciled data.

Fresh fields refreshed after reconcile:

- `invoices_count`
- `payments_count`
- `invoice_amount`
- `payment_amount`
- `difference`
- `match_status`
- `allocation_status`
- `invoice_refs_json`
- `payment_refs_json`
- `allocation_refs_json`
- `remarks`
- `last_error`

Stale browser data handling:

- `get_reconciliation_status()` returns `rows` for the supplied `run_name`.
- Frontend `refresh_status()` polls every 4 seconds while queued/running statuses exist.
- Frontend `apply_polled_rows()` replaces `this.rows` with polled rows and re-applies filters.
- This means the current browser table is refreshed from server child rows during and after reconciliation.

Remaining refresh risk:

- Rows are refreshed but not removed. A supplier can remain visible with invoice count 0 and payment count 0 after successful reconciliation, marked as Reconciled.
- Initial load also does not explicitly filter out rows where native data returns zero invoices and zero payments.
- This can make a correctly refreshed row look like an incorrect or stale count to users.

## 9. Error Handling Analysis

### Source Simple Voucher Doctype must be set first

- No explicit string handling for `Source Simple Voucher Doctype must be set first` was found.
- If native ERPNext raises this during row building/allocation/reconciliation, it is handled as a generic native failure.
- In `_build_supplier_row()`, native load/allocation errors become `allocation_status = Error`, with remarks and last_error.
- In `_reconcile_supplier_for_run()`, reconciliation errors roll back to the savepoint and mark the supplier row Error.
- Future work should add defensive/source-doctype aware handling if this error appears in production.

### Document modified timestamp error

- `_save_run_with_retry()` catches `frappe.TimestampMismatchError` and retries once.
- `allocate_selected()` has a friendly fallback response: `This run was updated by another process. Please try Allocate again.`
- Reconciliation queue/run saves do not have the same friendly TimestampMismatch path everywhere; worker-level failures can end up in run `error_log`.

### Suppliers with zero invoice and zero payment

- `_row_eligibility()` treats them as ineligible.
- Because it checks missing payments first, the message becomes `Payment Entry not available for selected supplier.`
- The row is not automatically hidden or removed.
- Such rows can still appear in table/export/status rows.

### Invalid/ineligible suppliers

- Ineligible suppliers are skipped before reconciliation.
- Reasons include no payments, no invoices, Needs Review, already Reconciled, Error, or no allocation preview.
- `allocate_selected()` records skipped suppliers with messages.
- `reconcile_selected()` returns skipped supplier details and does not queue them.

### Native ERPNext failure for a supplier

- During row build, `_safe_native_entries()` catches native failure and returns an Error row.
- During allocation, exceptions are counted as failed and row status is set to Error.
- During reconciliation, `_reconcile_supplier_for_run()` rolls back to a savepoint, sets row Error, records last_error/remarks, and returns failed status.
- `process_reconciliation_run()` aggregates failed suppliers in `error_log`.

## 10. Current Known Issues / Risks

- Zero-zero supplier rows can still appear.
  - The app does not filter out rows with `invoices_count = 0` and `payments_count = 0`.
  - After successful reconciliation, refreshed rows can remain visible as zero-zero Reconciled rows.

- Invoice/payment links open in the same tab.
  - `open_doc_link()` uses `frappe.set_route("Form", doctype, name)`.
  - Users lose the reconciliation page context when opening linked documents.

- Native Payment Reconciliation compatibility errors are generic.
  - Specific native errors such as `Source Simple Voucher Doctype must be set first` are not handled separately.
  - They will surface as generic Error remarks/last_error.

- Counts can look incorrect after reconcile even when refresh is working.
  - The backend refreshes rows from native data after reconcile.
  - However, it keeps the supplier row in the table and marks it Reconciled, often with zero invoice/payment counts.
  - Users may expect completed rows to disappear or be visually separated.

- Candidate supplier discovery is broader than native source of truth.
  - `_candidate_suppliers()` uses custom Purchase Invoice, Payment Entry, and Journal Entry queries to decide which suppliers to inspect.
  - `_build_supplier_row()` then uses native Payment Reconciliation for actual row data.
  - This mismatch can produce suppliers that were candidates by custom query but have no current native unreconciled rows.

- Payment Entry fully allocated but still counted is a potential compatibility/data risk.
  - Candidate discovery filters `Payment Entry.unallocated_amount > 0`.
  - Counts are ultimately based on native `pr.payments`, which is better than only using the candidate query.
  - If ERPNext/native data, voucher metadata, or Payment Entry unallocated fields are inconsistent, the app does not add an extra defensive validation layer beyond native Payment Reconciliation.

- Stale UI is mostly addressed, but not fully solved from a user-experience perspective.
  - Polling updates table rows from `get_reconciliation_status()`.
  - Rows are replaced in the browser, but completed zero-zero rows remain.
  - A global running run can appear in the banner even while rows are for the supplied `run_name`, which may be confusing if another company is running.

- Hardcoded site/route references exist in documentation.
  - README/project mention `https://apps.duxdigitech.in/app/auto_payment_reconciliation` and site `app.duxdigitech.in`.
  - App code itself does not appear to hardcode a company or site.

- `process_reconciliation_run()` is whitelisted.
  - It is intended as a background worker.
  - It does not call `_require_page_access()` directly and writes with `ignore_permissions=True`.
  - Review whether external RPC access should be restricted.

- `reconcile_supplier()` single-supplier API is not used by current UI.
  - It accepts `allocations` but ignores it.
  - It creates a new run and uses empty filters, so behavior may differ from selected-run reconciliation.

- Run naming has no explicit sequence lock.
  - Concurrent inserts with the same prefix could theoretically generate the same next number.

- Date and amount filters are free-text inputs.
  - The page parses them client-side with simple text parsing and no date picker validation.

## 11. Pending/Future Work

- Hide or remove zero-zero supplier rows from the main table and export.
- Open invoice/payment document links in a new browser tab.
- Make backend supplier listing match native Payment Reconciliation as the source of truth.
- Add defensive handling for invalid voucher/source doctype errors, including `Source Simple Voucher Doctype must be set first`.
- Keep post-reconciliation refresh, but decide whether reconciled zero-zero rows should be hidden, moved to a completed view, or shown with clearer status.
- Review and possibly restrict the whitelisted `process_reconciliation_run()` worker method.
- Review `reconcile_supplier()` or remove/harden it if not needed by UI.
- Add stronger validation/parsing for date and amount filters.
- Replace hardcoded documentation URL/site references with placeholders or environment-specific notes.
- Consider sequence locking or a safer naming series approach for concurrent run creation.
- Add clearer user-facing messages for fully allocated/missing/native-ineligible voucher cases.

## 12. Manual Commands Section

The following commands are needed only after future code changes. Do not run these during analysis.

```bash
cd /home/dux/frappe-bench
env/bin/pip install -e apps/auto_payment_reconciliation
bench --site <site_name> migrate
bench --site <site_name> clear-cache
bench restart
```

No command above was run while preparing this analysis.

## 13. Final Analysis Summary

What is working:

- The app is installed as a focused supplier/payables Desk Page.
- Company-only UI is implemented.
- Supplier-wise rows are built using ERPNext native Payment Reconciliation data after candidate discovery.
- Allocation preview and reconciliation reuse native ERPNext methods.
- The app does not directly edit GL Entry.
- Queue/progress tracking exists and frontend polling updates table rows.
- Post-reconciliation row refresh exists through `_refresh_supplier_row()`.
- Run naming includes company abbreviation, optional location, financial year, and running number.
- Duplicate `ABBR/ABBR/APR/...` naming is explicitly guarded.

What is partially working:

- Fresh native data is used after reconciliation, but completed suppliers can remain visible as zero-zero rows.
- Error handling catches native failures, but specific native compatibility errors are not classified.
- Queue/status polling works, but global active-run display can be confusing when another company is running.
- Candidate discovery uses custom queries before native reconciliation data, so supplier listing is not purely native-source-of-truth.

What needs fixing:

- Hide zero-zero rows or present them in a clearer completed state.
- Open document links in a new tab.
- Align supplier discovery more tightly with native Payment Reconciliation output.
- Add defensive handling for source voucher/source doctype errors.
- Review whitelisted background/test methods and unused single-supplier API exposure.
- Improve UI validation for free-text filters.

Recommended next step:

- Implement a small, focused fix set: filter zero-zero rows after native row build/refresh, update document links to open in a new tab, and add explicit handling for native source voucher errors. After that, run the manual commands in Section 12 and verify with one exact-match supplier, one partial supplier, one invoice-only supplier, one payment-only supplier, and a completed reconciliation refresh case.
