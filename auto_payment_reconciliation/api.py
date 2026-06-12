import csv
import json
from datetime import datetime
from io import StringIO

import frappe
from frappe import _
from frappe.query_builder import Criterion
from frappe.utils import add_to_date, cint, flt, get_datetime, getdate, now_datetime

import erpnext
from erpnext.accounts.party import get_party_account


ACTION_ROLES = {"Accounts Manager", "Accounts User", "System Manager"}
RUN_DOCTYPE = "Auto Payment Reconciliation Run"
ROW_DOCTYPE = "Auto Payment Reconciliation Supplier Entry"
BAD_LITERAL_RUN_NAME = "APR-" + "#" * 5


def _payment_type(filters):
	# The page is intentionally supplier/payables-only. Keep any old payment_type
	# metadata harmless by resolving all public flows to native Pay context.
	return "Pay"


def _payment_context(filters):
	payment_type = _payment_type(filters)
	if payment_type == "Receive":
		return frappe._dict({
			"payment_type": "Receive",
			"party_type": "Customer",
			"party_label": _("Customer Name"),
			"invoice_doctype": "Sales Invoice",
			"invoice_party_field": "customer",
			"invoice_account_field": "debit_to",
			"default_account_field": "default_receivable_account",
			"party_account_type": "Receivable",
			"root_type": "Asset",
			"payment_entry_type": "Receive",
			"journal_positive_side": "credit",
		})
	if payment_type == "Internal Transfer":
		return frappe._dict({
			"payment_type": "Internal Transfer",
			"party_type": None,
			"party_label": _("Supplier Name"),
		})
	return frappe._dict({
		"payment_type": "Pay",
		"party_type": "Supplier",
		"party_label": _("Supplier Name"),
		"invoice_doctype": "Purchase Invoice",
		"invoice_party_field": "supplier",
		"invoice_account_field": "credit_to",
		"default_account_field": "default_payable_account",
		"party_account_type": "Payable",
		"root_type": "Liability",
		"payment_entry_type": "Pay",
		"journal_positive_side": "debit",
	})


def _parse_filters(filters=None):
	if not filters:
		parsed = frappe._dict()
	elif isinstance(filters, str):
		parsed = frappe._dict(json.loads(filters))
	else:
		parsed = frappe._dict(filters)

	parsed.from_date = _date_value(parsed.get("from_date"))
	parsed.to_date = _date_value(parsed.get("to_date"))
	if parsed.from_date and parsed.to_date and getdate(parsed.from_date) > getdate(parsed.to_date):
		parsed.from_date, parsed.to_date = parsed.to_date, parsed.from_date
	return parsed


def _date_value(value):
	if not value:
		return None
	try:
		return str(getdate(value))
	except Exception:
		return None


def _active_statuses():
	return ["Draft", "Queued", "Running"]


def _is_bad_literal_run_name(name):
	return (name or "").strip() == BAD_LITERAL_RUN_NAME


def _run_filters_match(run, filters):
	return (
		(run.get("payment_type") or "Pay") == _payment_type(filters)
		and (run.payable_account or None) == (filters.get("payable_account") or None)
		and (run.default_advance_account or None) == (filters.get("default_advance_account") or None)
		and _date_value(run.from_date) == _date_value(filters.get("from_date"))
		and _date_value(run.to_date) == _date_value(filters.get("to_date"))
	)


def _find_reusable_run(company, filters):
	names = frappe.get_all(
		RUN_DOCTYPE,
		filters={"company": company, "status": ["in", _active_statuses()]},
		pluck="name",
		order_by="modified desc",
	)
	for name in names:
		if _is_bad_literal_run_name(name):
			continue
		run = frappe.get_doc(RUN_DOCTYPE, name)
		if _run_filters_match(run, filters):
			return run
	return None


def _require_page_access(write=False):
	user_roles = set(frappe.get_roles())
	if not user_roles.intersection(ACTION_ROLES):
		frappe.throw(_("You are not permitted to access Auto Payment Reconciliation."), frappe.PermissionError)

	if write and not frappe.has_permission(RUN_DOCTYPE, "write"):
		frappe.throw(_("Write permission is required for this action."), frappe.PermissionError)


def _validate_company(company):
	if not company or not frappe.db.exists("Company", company):
		frappe.throw(_("Please select a valid Company."))

	try:
		frappe.get_doc("Company", company).check_permission("read")
	except frappe.PermissionError:
		if "System Manager" not in frappe.get_roles():
			raise


def _company_currency(company):
	return erpnext.get_company_currency(company)


def _currency_precision(currency):
	return cint(frappe.db.get_value("Currency", currency, "fraction_units") or 2)


def _duration_display(seconds):
	seconds = cint(seconds)
	if seconds < 60:
		return f"{seconds:02d} sec" if seconds >= 10 else f"{seconds} sec"
	minutes, sec = divmod(seconds, 60)
	if minutes < 60:
		return f"{minutes:02d} min {sec:02d} sec"
	hours, minutes = divmod(minutes, 60)
	return f"{hours:02d} hr {minutes:02d} min {sec:02d} sec"


def _seconds_between(start, end):
	if not start or not end:
		return 0
	start_dt = get_datetime(start)
	end_dt = get_datetime(end)
	return cint((end_dt - start_dt).total_seconds())


def _json_loads(value):
	if not value:
		return []
	try:
		return json.loads(value)
	except Exception:
		return []


def _json_dumps(value):
	return json.dumps(value or [], default=str)


def _doc_type(value):
	value = (value or "").strip()
	aliases = {
		"Purchase Invoice": "Purchase Invoice",
		"Payment Entry": "Payment Entry",
		"Journal Entry": "Journal Entry",
	}
	return aliases.get(value, value)


def _invoice_refs(refs):
	return [
		ref
		for ref in refs or []
		if _doc_type(ref.get("reference_doctype") or ref.get("doctype") or ref.get("invoice_type"))
		in {"Purchase Invoice", "Sales Invoice", "Journal Entry"}
	]


def _payment_refs(refs):
	return [ref for ref in refs or [] if _doc_type(ref.get("reference_doctype") or ref.get("doctype") or ref.get("payment_type")) in {"Payment Entry", "Journal Entry"}]


def _has_valid_allocations(value):
	allocations = _json_loads(value)
	return bool(allocations and isinstance(allocations, list))


def _row_eligibility(values):
	has_invoices = cint(values.get("invoices_count")) > 0 and flt(values.get("invoice_amount")) > 0
	has_payments = cint(values.get("payments_count")) > 0 and flt(values.get("payment_amount")) > 0
	match_status = values.get("match_status")
	allocation_status = values.get("allocation_status")
	match_ok = match_status in {"Exact Match", "Partial Match"}
	has_allocations = _has_valid_allocations(values.get("allocation_refs_json"))
	can_allocate = has_invoices and has_payments and match_ok and allocation_status != "Reconciled"
	can_reconcile = can_allocate and allocation_status != "Error" and (
		has_allocations or allocation_status in {"Auto Allocated", "Ready for Allocation"}
	)

	message = ""
	if not has_payments:
		message = _("Payment Entry not available for selected supplier.")
	elif not has_invoices:
		message = _("Invoice not available for selected supplier.")
	elif match_status == "Needs Review":
		message = _("Supplier needs review before allocation or reconciliation.")
	elif allocation_status == "Reconciled":
		message = _("Supplier is already reconciled.")
	elif allocation_status == "Error":
		message = _("Allocation can be retried; reconciliation is blocked until allocation succeeds.")
	elif not has_allocations and allocation_status == "Pending Review":
		message = _("Allocation preview is not available for selected supplier.")

	return {
		"has_invoices": has_invoices,
		"has_payments": has_payments,
		"can_allocate": can_allocate,
		"can_reconcile": can_reconcile,
		"eligibility_message": message,
	}


def _apply_row_eligibility(values):
	values.update(_row_eligibility(values))
	return values


def _has_unreconciled_values(values):
	return (
		cint(values.get("invoices_count")) > 0
		or cint(values.get("payments_count")) > 0
		or flt(values.get("invoice_amount")) > 0
		or flt(values.get("payment_amount")) > 0
	)


def _save_run_with_retry(run_name, update_fn, retries=1):
	last_error = None
	for _attempt in range(retries + 1):
		run = frappe.get_doc(RUN_DOCTYPE, run_name)
		run.check_permission("write")
		try:
			result = update_fn(run)
			run.last_updated_on = now_datetime()
			run.save(ignore_permissions=True)
			return frappe.get_doc(RUN_DOCTYPE, run.name), result
		except frappe.TimestampMismatchError as exc:
			last_error = exc
	if last_error:
		raise last_error


def _get_reconciliation_account(company, party, filters):
	context = _payment_context(filters)
	if not context.party_type:
		return None, None

	if filters.get("payable_account"):
		return filters.payable_account, filters.get("default_advance_account")

	account = None
	default_advance_account = filters.get("default_advance_account")
	try:
		party_account = get_party_account(company, context.party_type, party, include_advance=1)
		if isinstance(party_account, (list, tuple)):
			account = party_account[0]
			default_advance_account = default_advance_account or (party_account[1] if len(party_account) > 1 else None)
		else:
			account = party_account
	except Exception:
		account = None

	account = account or frappe.db.get_value("Company", company, context.default_account_field)
	return account, default_advance_account


def _get_payable_account(company, supplier, filters):
	return _get_reconciliation_account(company, supplier, filters)


def _new_payment_reconciliation(company, party, filters):
	context = _payment_context(filters)
	if not context.party_type:
		frappe.throw(_("Internal Transfer does not have a party/invoice context in native Payment Reconciliation."))

	reconciliation_account, default_advance_account = _get_reconciliation_account(company, party, filters)
	if not reconciliation_account:
		frappe.throw(_("Missing {0} account for {1} {2}.").format(context.party_account_type.lower(), context.party_type, party))

	pr = frappe.get_doc("Payment Reconciliation")
	pr.company = company
	pr.party_type = context.party_type
	pr.party = party
	pr.receivable_payable_account = reconciliation_account
	pr.default_advance_account = default_advance_account
	pr.from_invoice_date = filters.get("from_date")
	pr.to_invoice_date = filters.get("to_date")
	pr.from_payment_date = filters.get("from_date")
	pr.to_payment_date = filters.get("to_date")
	pr.invoice_limit = cint(filters.get("invoice_limit") or 0)
	pr.payment_limit = cint(filters.get("payment_limit") or 0)
	return pr


def _load_native_entries(company, supplier, filters):
	pr = _new_payment_reconciliation(company, supplier, filters)
	pr.get_unreconciled_entries()
	return pr


def _serialize_invoice(row, reconciliation_account=None):
	invoice_number = row.get("invoice_number")
	invoice_type = _doc_type(row.get("invoice_type") or "Purchase Invoice")
	due_date = None
	account = reconciliation_account
	if invoice_type in {"Purchase Invoice", "Sales Invoice"} and invoice_number:
		field = "credit_to" if invoice_type == "Purchase Invoice" else "debit_to"
		due_date, account = frappe.db.get_value(invoice_type, invoice_number, ["due_date", field]) or (None, reconciliation_account)

	return {
		"doctype": invoice_type,
		"reference_doctype": invoice_type,
		"invoice_type": invoice_type,
		"invoice_number": invoice_number,
		"posting_date": row.get("invoice_date"),
		"due_date": due_date,
		"outstanding_amount": flt(row.get("outstanding_amount")),
		"currency": row.get("currency"),
		"account": account or reconciliation_account,
	}


def _serialize_payment(row, payable_account=None):
	reference_name = row.get("reference_name")
	doctype = _doc_type(row.get("reference_type"))
	if not doctype and reference_name:
		if frappe.db.exists("Payment Entry", reference_name):
			doctype = "Payment Entry"
		elif frappe.db.exists("Journal Entry", reference_name):
			doctype = "Journal Entry"
	return {
		"doctype": doctype,
		"reference_doctype": doctype,
		"payment_type": doctype,
		"reference_name": reference_name,
		"posting_date": row.get("posting_date"),
		"unallocated_amount": flt(row.get("amount")),
		"currency": row.get("currency"),
		"account": payable_account,
		"reference_row": row.get("reference_row"),
	}


def _safe_native_entries(company, supplier, filters):
	try:
		pr = _load_native_entries(company, supplier, filters)
		return pr, None
	except Exception as exc:
		return None, str(exc)


def _party_name(party, party_type="Supplier"):
	if party_type == "Customer":
		return frappe.db.get_value("Customer", party, "customer_name") or party
	if party_type == "Supplier":
		return frappe.db.get_value("Supplier", party, "supplier_name") or party
	return party


def _supplier_name(supplier):
	return _party_name(supplier, "Supplier")


def _user_display(user):
	if not user:
		return ""
	return frappe.db.get_value("User", user, "full_name") or user


def _relative_start_display(estimated_start):
	if not estimated_start:
		return ""
	seconds = cint((get_datetime(estimated_start) - now_datetime()).total_seconds())
	if seconds <= 0:
		return _("Now")
	minutes = max(1, int((seconds + 59) / 60))
	return _("After {0} min").format(f"{minutes:02d}")


def _queue_status_display(status):
	return _("Waiting") if status == "Queued" else status


def _allocation_preview_from_pr(pr):
	invoices = [d.as_dict() for d in pr.invoices]
	payments = [d.as_dict() for d in pr.payments]
	if not invoices or not payments:
		return []

	pr.allocate_entries(frappe._dict({"invoices": invoices, "payments": payments}))
	return [d.as_dict(no_nulls=True) for d in pr.allocation]


def _build_supplier_row(company, supplier, filters):
	context = _payment_context(filters)
	if not context.party_type:
		return frappe._dict(_apply_row_eligibility({
			"party_type": "",
			"supplier": supplier,
			"supplier_name": supplier or _("Internal Transfer"),
			"supplier_id": supplier,
			"invoices_count": 0,
			"payments_count": 0,
			"invoice_amount": 0,
			"payment_amount": 0,
			"difference": 0,
			"match_status": "Needs Review",
			"allocation_status": "Pending Review",
			"invoice_refs_json": "[]",
			"payment_refs_json": "[]",
			"allocation_refs_json": "[]",
			"remarks": _("Internal Transfer has no invoice-side party context in native Payment Reconciliation."),
			"last_error": "",
		}))

	currency = _company_currency(company)
	precision = _currency_precision(currency)
	pr, error = _safe_native_entries(company, supplier, filters)
	reconciliation_account, _default_advance_account = _get_reconciliation_account(company, supplier, filters)
	party_name = _party_name(supplier, context.party_type)

	if error:
		return frappe._dict(_apply_row_eligibility({
			"party_type": context.party_type,
			"supplier": supplier,
			"supplier_name": party_name,
			"supplier_id": supplier,
			"invoices_count": 0,
			"payments_count": 0,
			"invoice_amount": 0,
			"payment_amount": 0,
			"difference": 0,
			"match_status": "Needs Review",
			"allocation_status": "Error",
			"invoice_refs_json": "[]",
			"payment_refs_json": "[]",
			"allocation_refs_json": "[]",
			"remarks": error,
			"last_error": error,
		}))

	invoices = [_serialize_invoice(d.as_dict(), reconciliation_account) for d in pr.invoices]
	payments = _payment_refs([_serialize_payment(d.as_dict(), reconciliation_account) for d in pr.payments])
	invoice_amount = flt(sum(flt(d.get("outstanding_amount")) for d in invoices), precision)
	payment_amount = flt(sum(flt(d.get("unallocated_amount")) for d in payments), precision)
	difference = flt(invoice_amount - payment_amount, precision)
	currencies = {d.get("currency") for d in invoices + payments if d.get("currency")}

	remarks = []
	match_status = "Needs Review"
	allocation_status = "Pending Review"
	allocations = []

	if not reconciliation_account:
		remarks.append(_("Missing {0} account").format(context.party_account_type.lower()))
	elif len(currencies) > 1:
		remarks.append(_("Currency mismatch"))
	elif invoice_amount <= 0 and payment_amount > 0:
		remarks.append(_("Payment exists without invoice"))
	elif payment_amount <= 0 and invoice_amount > 0:
		remarks.append(_("Invoice exists without payment"))
	elif invoice_amount < 0 or payment_amount < 0:
		remarks.append(_("Invalid/negative amount"))
	elif invoice_amount > 0 and payment_amount > 0:
		match_status = "Exact Match" if flt(difference, precision) == 0 else "Partial Match"
		try:
			allocations = _allocation_preview_from_pr(pr)
			if allocations:
				allocation_status = "Auto Allocated" if match_status == "Exact Match" else "Ready for Allocation"
			else:
				allocation_status = "Pending Review"
				remarks.append(_("No allocation preview could be generated"))
		except Exception as exc:
			allocation_status = "Error"
			remarks.append(str(exc))

	return frappe._dict(_apply_row_eligibility({
		"party_type": context.party_type,
		"supplier": supplier,
		"supplier_name": party_name,
		"supplier_id": supplier,
		"invoices_count": len(invoices),
		"payments_count": len(payments),
		"invoice_amount": invoice_amount,
		"payment_amount": payment_amount,
		"difference": difference,
		"match_status": match_status,
		"allocation_status": allocation_status,
		"invoice_refs_json": _json_dumps(invoices),
		"payment_refs_json": _json_dumps(payments),
		"allocation_refs_json": _json_dumps(allocations),
		"remarks": "; ".join(remarks),
		"last_error": "; ".join(remarks) if allocation_status == "Error" else "",
	}))


def _candidate_suppliers(company, filters):
	context = _payment_context(filters)
	if not context.party_type:
		return []

	parties = set()
	invoice_filters = {
		"company": company,
		"docstatus": 1,
		"outstanding_amount": (">", 0),
	}
	if filters.get("from_date") and filters.get("to_date"):
		invoice_filters["posting_date"] = ("between", [filters.from_date, filters.to_date])
	elif filters.get("from_date"):
		invoice_filters["posting_date"] = (">=", filters.from_date)
	elif filters.get("to_date"):
		invoice_filters["posting_date"] = ("<=", filters.to_date)

	for row in frappe.get_all(context.invoice_doctype, filters=invoice_filters, pluck=context.invoice_party_field):
		if row:
			parties.add(row)

	pe_filters = {
		"company": company,
		"docstatus": 1,
		"payment_type": context.payment_entry_type,
		"party_type": context.party_type,
		"unallocated_amount": (">", 0),
	}
	if filters.get("from_date") and filters.get("to_date"):
		pe_filters["posting_date"] = ("between", [filters.from_date, filters.to_date])
	elif filters.get("from_date"):
		pe_filters["posting_date"] = (">=", filters.from_date)
	elif filters.get("to_date"):
		pe_filters["posting_date"] = ("<=", filters.to_date)

	for row in frappe.get_all("Payment Entry", filters=pe_filters, pluck="party"):
		if row:
			parties.add(row)

	je = frappe.qb.DocType("Journal Entry")
	jea = frappe.qb.DocType("Journal Entry Account")
	positive_amount = (
		(jea.debit_in_account_currency - jea.credit_in_account_currency).gt(0)
		if context.journal_positive_side == "debit"
		else (jea.credit_in_account_currency - jea.debit_in_account_currency).gt(0)
	)
	conditions = [
		je.company == company,
		je.docstatus == 1,
		jea.party_type == context.party_type,
		((jea.reference_type == "") | jea.reference_type.isnull()),
		positive_amount,
	]
	if filters.get("from_date"):
		conditions.append(je.posting_date >= filters.from_date)
	if filters.get("to_date"):
		conditions.append(je.posting_date <= filters.to_date)
	if filters.get("payable_account"):
		conditions.append(jea.account == filters.payable_account)

	je_parties = (
		frappe.qb.from_(je)
		.inner_join(jea)
		.on(jea.parent == je.name)
		.select(jea.party)
		.where(Criterion.all(conditions))
		.distinct()
	).run(as_dict=True)
	for row in je_parties:
		if row.party:
			parties.add(row.party)

	return sorted(parties, key=lambda party: (_party_name(party, context.party_type) or party).lower())


def _make_or_update_run(company, filters):
	run = None
	run_name = filters.get("run_name")
	if run_name and frappe.db.exists(RUN_DOCTYPE, run_name) and not _is_bad_literal_run_name(run_name):
		candidate = frappe.get_doc(RUN_DOCTYPE, run_name)
		if candidate.company == company and candidate.status in _active_statuses() and _run_filters_match(candidate, filters):
			run = candidate

	run = run or _find_reusable_run(company, filters)
	if not run:
		run = frappe.new_doc(RUN_DOCTYPE)
		run.company = company

	if run.status in {"Queued", "Running"}:
		return run

	run.company = company
	run.payment_type = _payment_type(filters)
	run.payable_account = filters.get("payable_account")
	run.default_advance_account = filters.get("default_advance_account")
	run.from_date = filters.get("from_date")
	run.to_date = filters.get("to_date")
	run.status = "Draft"
	run.requested_by = frappe.session.user
	run.requested_on = now_datetime()
	run.error_log = ""
	run.current_supplier = None
	run.total_entries = 0
	run.processed_entries = 0
	run.progress_percent = 0
	run.remaining_time = ""
	run.last_updated_on = now_datetime()
	run.set("supplier_entries", [])
	return run


def _row_to_dict(row):
	data = row.as_dict(no_nulls=True) if hasattr(row, "as_dict") else frappe._dict(row)
	for key in ["doctype", "parent", "parentfield", "parenttype", "idx", "name", "owner", "creation", "modified", "modified_by"]:
		data.pop(key, None)
	return _apply_row_eligibility(data)


def _find_supplier_row(run, supplier):
	for row in run.supplier_entries:
		if row.supplier == supplier:
			return row
	return None


def _update_child_row(row, values):
	for fieldname, value in values.items():
		if fieldname in {"party_type", "supplier", "supplier_name", "supplier_id", "invoices_count", "payments_count", "invoice_amount", "payment_amount", "difference", "match_status", "allocation_status", "invoice_refs_json", "payment_refs_json", "allocation_refs_json", "remarks", "last_error", "reconciled_by", "reconciled_on", "duration_seconds", "duration_display"}:
			row.set(fieldname, value)


def _supplier_rows(run):
	rows = []
	for row in run.supplier_entries:
		row_data = _row_to_dict(row)
		if _has_unreconciled_values(row_data):
			rows.append(row_data)
	return rows


def _refresh_supplier_row(run, supplier, filters):
	new_values = _build_supplier_row(run.company, supplier, filters)
	row = _find_supplier_row(run, supplier)
	if not row:
		row = run.append("supplier_entries", {})
	_update_child_row(row, new_values)
	return row


def _run_filters(run):
	return frappe._dict(
		{
			"payment_type": "Pay",
			"payable_account": run.payable_account,
			"default_advance_account": run.default_advance_account,
			"from_date": run.from_date,
			"to_date": run.to_date,
		}
	)


@frappe.whitelist()
def get_unreconciled_entries(company, filters=None):
	_require_page_access(write=True)
	_validate_company(company)
	filters = _parse_filters(filters)

	run = _make_or_update_run(company, filters)
	if run.status not in {"Queued", "Running"}:
		suppliers = _candidate_suppliers(company, filters)
		for supplier in suppliers:
			row_data = _build_supplier_row(company, supplier, filters)
			if _has_unreconciled_values(row_data):
				run.append("supplier_entries", row_data)

		run.total_entries = len(run.supplier_entries)
		run.last_updated_on = now_datetime()
		run.insert(ignore_permissions=True) if run.is_new() else run.save(ignore_permissions=True)

	return {
		"run_name": run.name,
		"company": company,
		"currency": _company_currency(company),
		"payment_type": _payment_type(filters),
		"party_type": _payment_context(filters).party_type,
		"party_label": _payment_context(filters).party_label,
		"rows": _supplier_rows(run),
		"status": get_reconciliation_status(run_name=run.name),
	}


@frappe.whitelist()
def get_supplier_details(company, supplier, filters=None):
	_require_page_access()
	_validate_company(company)
	filters = _parse_filters(filters)
	run_name = filters.get("run_name")
	run = frappe.get_doc(RUN_DOCTYPE, run_name) if run_name and frappe.db.exists(RUN_DOCTYPE, run_name) else None
	row = _find_supplier_row(run, supplier) if run else None

	use_cached_row = bool(row and run and _run_filters_match(run, filters))
	if use_cached_row:
		invoices = _invoice_refs(_json_loads(row.invoice_refs_json))
		payments = _payment_refs(_json_loads(row.payment_refs_json))
		summary = _row_to_dict(row)
	else:
		row_data = _build_supplier_row(company, supplier, filters)
		invoices = _invoice_refs(_json_loads(row_data.invoice_refs_json))
		payments = _payment_refs(_json_loads(row_data.payment_refs_json))
		summary = dict(row_data)

	summary.update(
		{
			"company": company,
			"supplier": supplier,
			"supplier_name": summary.get("supplier_name") or _party_name(supplier, _payment_context(filters).party_type or "Supplier"),
			"supplier_id": supplier,
			"party_type": summary.get("party_type") or _payment_context(filters).party_type,
			"run_name": run.name if run else run_name,
		}
	)
	return {"summary": summary, "invoices": invoices, "payments": payments}


@frappe.whitelist()
def allocate_supplier(company, supplier, filters=None, preview=True):
	_require_page_access(write=True)
	_validate_company(company)
	filters = _parse_filters(filters)
	row_data = _build_supplier_row(company, supplier, filters)
	allocations = _json_loads(row_data.allocation_refs_json)
	return {
		"supplier": supplier,
		"allocations": allocations,
		"count": len(allocations),
		"can_allocate": row_data.can_allocate,
		"can_reconcile": row_data.can_reconcile,
		"eligibility_message": row_data.eligibility_message,
	}


@frappe.whitelist()
def allocate_selected(run_name, suppliers):
	_require_page_access(write=True)
	if not run_name or not frappe.db.exists(RUN_DOCTYPE, run_name):
		frappe.throw(_("Please get unreconciled entries first."))
	suppliers = _json_loads(suppliers) if isinstance(suppliers, str) else suppliers
	suppliers = suppliers or []

	result = {"total": len(suppliers), "allocated": 0, "skipped": 0, "failed": 0, "errors": [], "skipped_suppliers": []}

	def update_run(run):
		filters = _run_filters(run)
		filters.run_name = run.name
		for supplier in suppliers:
			row = _find_supplier_row(run, supplier)
			try:
				row_values = _build_supplier_row(run.company, supplier, filters)
				if not row:
					row = run.append("supplier_entries", {})
				_update_child_row(row, row_values)
				eligibility = _row_eligibility(row_values)
				if not eligibility["can_allocate"]:
					result["skipped"] += 1
					result["skipped_suppliers"].append({"supplier": supplier, "message": eligibility["eligibility_message"]})
				elif _has_valid_allocations(row_values.get("allocation_refs_json")):
					result["allocated"] += 1
				else:
					result["skipped"] += 1
					result["skipped_suppliers"].append({"supplier": supplier, "message": row_values.get("remarks") or _("Allocation preview is not available.")})
			except Exception as exc:
				result["failed"] += 1
				result["errors"].append({"supplier": supplier, "error": str(exc)})
				if not row:
					row = run.append("supplier_entries", {"party_type": _payment_context(filters).party_type, "supplier": supplier, "supplier_name": _party_name(supplier, _payment_context(filters).party_type or "Supplier"), "supplier_id": supplier})
				row.allocation_status = "Error"
				row.last_error = str(exc)
		return result

	try:
		run, result = _save_run_with_retry(run_name, update_run, retries=1)
	except frappe.TimestampMismatchError:
		return {
			"run_name": run_name,
			"total": len(suppliers),
			"allocated": 0,
			"skipped": 0,
			"failed": len(suppliers),
			"errors": [{"error": _("This run was updated by another process. Please try Allocate again.")}],
			"rows": _supplier_rows(frappe.get_doc(RUN_DOCTYPE, run_name)),
			"status": get_reconciliation_status(run_name=run_name),
		}

	return {
		**result,
		"run_name": run.name,
		"company": run.company,
		"currency": _company_currency(run.company),
		"rows": _supplier_rows(run),
		"status": get_reconciliation_status(run_name=run.name),
	}


def _set_run_duration(run, completed_on=None):
	completed_on = completed_on or now_datetime()
	run.completed_on = completed_on
	run.last_updated_on = completed_on
	if run.started_on:
		run.duration_seconds = _seconds_between(run.started_on, completed_on)
		run.duration_display = _duration_display(run.duration_seconds)


def _update_run_progress(run, processed, total, started_at=None):
	run.processed_entries = processed
	run.total_entries = total
	run.progress_percent = flt((processed / total) * 100, 2) if total else 0
	run.last_updated_on = now_datetime()
	if started_at and processed and processed < total:
		elapsed = max(_seconds_between(started_at, now_datetime()), 1)
		remaining = int((elapsed / processed) * (total - processed))
		run.remaining_time = _duration_display(remaining)
	else:
		run.remaining_time = ""


def _reconcile_supplier_for_run(run, supplier, user=None):
	user = user or frappe.session.user
	filters = _run_filters(run)
	started = now_datetime()
	savepoint = f"apr_{frappe.generate_hash(length=8)}"
	frappe.db.savepoint(savepoint)

	row = _find_supplier_row(run, supplier) or _refresh_supplier_row(run, supplier, filters)
	try:
		eligibility = _row_eligibility(_row_to_dict(row))
		if not eligibility["can_reconcile"]:
			row.remarks = eligibility["eligibility_message"] or _("Skipped suppliers without available Payment Entry or Invoice.")
			return {"supplier": supplier, "status": "skipped", "message": row.remarks}

		pr = _load_native_entries(run.company, supplier, filters)
		allocations = _allocation_preview_from_pr(pr)
		if not allocations:
			_refresh_supplier_row(run, supplier, filters)
			row = _find_supplier_row(run, supplier)
			row.remarks = row.remarks or _("No current allocations to reconcile. It may already be reconciled.")
			if flt(row.invoice_amount) == 0 and flt(row.payment_amount) == 0:
				row.allocation_status = "Reconciled"
			return {"supplier": supplier, "status": "skipped", "message": row.remarks}

		pr.validate_allocation()
		pr.reconcile_allocations()
		ended = now_datetime()
		duration = _seconds_between(started, ended)

		# Recompute from fresh ERPNext native Payment Reconciliation data after posting.
		# This refreshes invoice/payment counts, amounts, difference, statuses, and refs.
		row = _refresh_supplier_row(run, supplier, filters)
		row.allocation_status = "Reconciled"
		row.reconciled_by = user
		row.reconciled_on = ended
		row.duration_seconds = duration
		row.duration_display = _duration_display(duration)
		row.last_error = ""
		row.remarks = _("Reconciled successfully.")
		return {"supplier": supplier, "status": "reconciled"}
	except Exception as exc:
		frappe.db.rollback(save_point=savepoint)
		row.allocation_status = "Error"
		row.last_error = str(exc)
		row.remarks = str(exc)
		return {"supplier": supplier, "status": "failed", "error": str(exc)}


@frappe.whitelist()
def reconcile_supplier(company, supplier, allocations=None):
	_require_page_access(write=True)
	_validate_company(company)
	run = frappe.new_doc(RUN_DOCTYPE)
	run.company = company
	run.status = "Running"
	run.requested_by = frappe.session.user
	run.requested_on = now_datetime()
	run.started_by = frappe.session.user
	run.started_on = now_datetime()
	run.reconciled_by = frappe.session.user
	run.reconciled_on = now_datetime()
	_refresh_supplier_row(run, supplier, frappe._dict())
	result = _reconcile_supplier_for_run(run, supplier, frappe.session.user)
	_set_run_duration(run)
	run.status = "Completed" if result.get("status") != "failed" else "Failed"
	run.insert(ignore_permissions=True)
	return result


def _active_duplicate_for_company(company, exclude=None):
	filters = {"company": company, "status": ["in", ["Queued", "Running"]]}
	names = frappe.get_all(RUN_DOCTYPE, filters=filters, pluck="name", order_by="creation asc")
	for name in names:
		if name != exclude:
			return name
	return None


def _running_run(exclude=None):
	names = frappe.get_all(RUN_DOCTYPE, filters={"status": "Running"}, pluck="name", order_by="creation asc")
	for name in names:
		if name != exclude:
			return name
	return None


def _first_queued_run():
	return frappe.db.get_value(
		RUN_DOCTYPE,
		filters={"status": "Queued"},
		fieldname="name",
		order_by="requested_on asc, creation asc",
	)


def _queue_positions():
	queued = frappe.get_all(
		RUN_DOCTYPE,
		filters={"status": "Queued"},
		fields=["name"],
		order_by="requested_on asc, creation asc",
	)
	for idx, row in enumerate(queued, start=1):
		frappe.db.set_value(RUN_DOCTYPE, row.name, "queue_position", idx, update_modified=False)


@frappe.whitelist()
def reconcile_selected(run_name, suppliers):
	_require_page_access(write=True)
	run = frappe.get_doc(RUN_DOCTYPE, run_name)
	run.check_permission("write")
	suppliers = _json_loads(suppliers) if isinstance(suppliers, str) else suppliers
	if not suppliers:
		frappe.throw(_("Please select at least one supplier."))

	if run.status in {"Queued", "Running"}:
		return {
			"run_name": run.name,
			"status": run.status,
			"message": _("Reconciliation for this company is already {0}.").format(run.status.lower()),
		}

	duplicate = _active_duplicate_for_company(run.company, exclude=run.name)
	if duplicate:
		status = frappe.db.get_value(RUN_DOCTYPE, duplicate, "status")
		return {
			"run_name": duplicate,
			"status": status,
			"message": _("Reconciliation for this company is already {0}.").format((status or "queued").lower()),
		}

	eligible_suppliers = []
	skipped_suppliers = []
	for supplier in suppliers:
		row = _find_supplier_row(run, supplier)
		if not row:
			skipped_suppliers.append({"supplier": supplier, "message": _("Skipped suppliers without available Payment Entry or Invoice.")})
			continue
		eligibility = _row_eligibility(_row_to_dict(row))
		if eligibility["can_reconcile"]:
			eligible_suppliers.append(supplier)
		else:
			skipped_suppliers.append({"supplier": supplier, "message": eligibility["eligibility_message"] or _("Skipped suppliers without available Payment Entry or Invoice.")})

	if not eligible_suppliers:
		return {
			"run_name": run.name,
			"status": run.status,
			"message": _("Skipped suppliers without available Payment Entry or Invoice."),
			"skipped": skipped_suppliers,
			"rows": _supplier_rows(run),
			"status_data": get_reconciliation_status(run_name=run.name),
		}

	for row in run.supplier_entries:
		row.selected = 1 if row.supplier in eligible_suppliers else 0

	run.requested_by = frappe.session.user
	run.requested_on = now_datetime()
	run.reconciled_by = frappe.session.user
	run.reconciled_on = now_datetime()
	run.last_updated_on = now_datetime()
	run.total_entries = len(eligible_suppliers)
	run.processed_entries = 0
	run.progress_percent = 0
	run.error_log = _json_dumps(skipped_suppliers) if skipped_suppliers else ""
	run.status = "Queued"
	run.save(ignore_permissions=True)

	_queue_positions()
	if not _running_run(exclude=run.name) and _first_queued_run() == run.name:
		frappe.enqueue(
			method="auto_payment_reconciliation.api.process_reconciliation_run",
			queue="long",
			timeout=7200,
			is_async=True,
			enqueue_after_commit=True,
			run_name=run.name,
		)

	message = _("Reconciliation has been queued.")
	if skipped_suppliers:
		message = _("Reconciliation has been queued. Skipped suppliers without available Payment Entry or Invoice.")
	return {
		"run_name": run.name,
		"status": run.status,
		"message": message,
		"skipped": skipped_suppliers,
		"rows": _supplier_rows(run),
		"status_data": get_reconciliation_status(run_name=run.name),
	}


@frappe.whitelist()
def process_reconciliation_run(run_name):
	run = frappe.get_doc(RUN_DOCTYPE, run_name)
	if _running_run(exclude=run.name):
		run.status = "Queued"
		run.last_updated_on = now_datetime()
		run.save(ignore_permissions=True)
		_queue_positions()
		return
	if run.status == "Queued" and _first_queued_run() not in {None, run.name}:
		_queue_positions()
		return

	selected = [row.supplier for row in run.supplier_entries if row.selected]
	result = {"total": len(selected), "reconciled": 0, "skipped": 0, "failed": 0, "errors": []}
	try:
		started = now_datetime()
		run.status = "Running"
		run.started_by = run.reconciled_by or run.requested_by or frappe.session.user
		run.started_on = run.started_on or started
		run.completed_on = None
		run.current_supplier = None
		run.error_log = ""
		_update_run_progress(run, 0, len(selected), run.started_on)
		run.save(ignore_permissions=True)
		frappe.db.commit()

		for idx, supplier in enumerate(selected, start=1):
			run = frappe.get_doc(RUN_DOCTYPE, run.name)
			run.current_supplier = supplier
			_update_run_progress(run, idx - 1, len(selected), run.started_on)
			run.save(ignore_permissions=True)
			frappe.db.commit()

			supplier_result = _reconcile_supplier_for_run(run, supplier, run.reconciled_by)
			if supplier_result.get("status") == "reconciled":
				result["reconciled"] += 1
			elif supplier_result.get("status") == "skipped":
				result["skipped"] += 1
			else:
				result["failed"] += 1
				result["errors"].append(supplier_result)

			_update_run_progress(run, idx, len(selected), run.started_on)
			run.save(ignore_permissions=True)
			frappe.db.commit()

		run = frappe.get_doc(RUN_DOCTYPE, run.name)
		run.current_supplier = None
		run.error_log = _json_dumps(result["errors"])
		_set_run_duration(run)
		run.status = "Failed" if result["failed"] and not result["reconciled"] else "Completed"
		run.save(ignore_permissions=True)
		frappe.db.commit()
	except Exception:
		run = frappe.get_doc(RUN_DOCTYPE, run_name)
		run.current_supplier = None
		run.status = "Failed"
		run.error_log = frappe.get_traceback()
		_set_run_duration(run)
		run.save(ignore_permissions=True)
		frappe.db.commit()
		result["failed"] = result.get("failed", 0) or 1
		result["errors"].append({"error": run.error_log})

	_start_next_queued_run()
	return result


def _start_next_queued_run():
	if _running_run():
		return
	_queue_positions()
	next_run = _first_queued_run()
	if next_run:
		frappe.enqueue(
			method="auto_payment_reconciliation.api.process_reconciliation_run",
			queue="long",
			timeout=7200,
			is_async=True,
			enqueue_after_commit=True,
			run_name=next_run,
		)


@frappe.whitelist()
def export_unreconciled_entries(run_name, filters=None):
	_require_page_access()
	run = frappe.get_doc(RUN_DOCTYPE, run_name)
	run.check_permission("read")
	filters = _parse_filters(filters)
	filters.run_name = run_name
	if _run_filters_match(run, filters):
		rows = _supplier_rows(run)
	else:
		rows = []
		for supplier in _candidate_suppliers(run.company, filters):
			row_data = _build_supplier_row(run.company, supplier, filters)
			if _has_unreconciled_values(row_data):
				rows.append(row_data)
	output = StringIO()
	writer = csv.writer(output)
	writer.writerow(
		[
			"Supplier Name",
			"Supplier ID",
			"Invoices",
			"Payments",
			"Invoice Amt.",
			"Payment Amt.",
			"Difference",
			"Match Status",
			"Allocation Status",
			"Reconciled By",
			"Reconciled On",
			"Time Taken",
			"Invoice References JSON",
			"Payment References JSON",
		]
	)
	for row in rows:
		writer.writerow(
			[
				row.get("supplier_name"),
				row.get("supplier_id"),
				row.get("invoices_count"),
				row.get("payments_count"),
				row.get("invoice_amount"),
				row.get("payment_amount"),
				row.get("difference"),
				row.get("match_status"),
				row.get("allocation_status"),
				row.get("reconciled_by"),
				row.get("reconciled_on"),
				row.get("duration_display"),
				row.get("invoice_refs_json"),
				row.get("payment_refs_json"),
			]
		)

	return {
		"filename": f"{run.name}-supplier-wise-reconciliation.csv",
		"content": output.getvalue(),
		"content_type": "text/csv",
	}


def _queue_row(row, idx):
	estimated_start = row.get("estimated_start")
	if not estimated_start:
		estimated_start = add_to_date(now_datetime(), minutes=max(idx - 1, 0) * 5)
	estimated_duration = row.estimated_duration or row.duration_display or ""
	return {
		"position": idx,
		"queue_position": idx,
		"name": row.name,
		"company": row.company,
		"requested_by": row.requested_by,
		"requested_by_full_name": _user_display(row.requested_by),
		"requested_on": row.requested_on,
		"estimated_start": estimated_start,
		"estimated_start_display": _relative_start_display(estimated_start),
		"estimated_duration": estimated_duration,
		"estimated_duration_display": estimated_duration,
		"status": row.status,
		"status_display": _queue_status_display(row.status),
		"run_name": row.name,
	}


@frappe.whitelist()
def get_reconciliation_status(run_name=None, company=None):
	_require_page_access()
	running = frappe.get_all(
		RUN_DOCTYPE,
		filters={"status": "Running"},
		fields=[
			"name",
			"company",
			"status",
			"payment_type",
			"requested_by",
			"requested_on",
			"queue_position",
			"estimated_start",
			"estimated_duration",
			"started_by",
			"started_on",
			"reconciled_by",
			"reconciled_on",
			"completed_on",
			"duration_display",
			"current_supplier",
			"processed_entries",
			"total_entries",
			"progress_percent",
			"remaining_time",
			"last_updated_on",
			"error_log",
		],
		order_by="started_on asc",
		limit=1,
	)
	active = running[0] if running else None
	if run_name and not active and frappe.db.exists(RUN_DOCTYPE, run_name):
		active = frappe.db.get_value(
			RUN_DOCTYPE,
			run_name,
			[
				"name",
				"company",
				"status",
				"payment_type",
				"requested_by",
				"requested_on",
				"queue_position",
				"estimated_start",
				"estimated_duration",
				"started_by",
				"started_on",
				"reconciled_by",
				"reconciled_on",
				"completed_on",
				"duration_display",
				"current_supplier",
				"processed_entries",
				"total_entries",
				"progress_percent",
				"remaining_time",
				"last_updated_on",
				"error_log",
			],
			as_dict=True,
		)

	if active and active.get("status") == "Completed" and cint(active.get("total_entries")):
		active["progress_percent"] = 100

	if active:
		active["started_by_full_name"] = _user_display(active.get("started_by"))
		active["requested_by_full_name"] = _user_display(active.get("requested_by"))
		active["reconciled_by_full_name"] = _user_display(active.get("reconciled_by"))
		active["estimated_start_display"] = _relative_start_display(active.get("estimated_start"))
		active["estimated_duration_display"] = active.get("estimated_duration") or active.get("duration_display") or ""
		active["current_supplier_name"] = _supplier_name(active.get("current_supplier")) if active.get("current_supplier") else ""

	queued = frappe.get_all(
		RUN_DOCTYPE,
		filters={"status": "Queued"},
		fields=[
			"name",
			"company",
			"status",
			"requested_by",
			"requested_on",
			"estimated_start",
			"estimated_duration",
			"duration_display",
		],
		order_by="requested_on asc, creation asc",
	)
	queue = [_queue_row(row, idx) for idx, row in enumerate(queued, start=1)]

	status = {"active_run": active, "active": active, "queue": queue}
	if run_name and frappe.db.exists(RUN_DOCTYPE, run_name):
		run = frappe.get_doc(RUN_DOCTYPE, run_name)
		run.check_permission("read")
		status["rows"] = _supplier_rows(run)
		status["currency"] = _company_currency(run.company)
	return status
