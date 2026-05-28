import json
import frappe
from frappe import _
from frappe.utils import cint, flt, getdate, now_datetime, today

TEST_PREFIX = "APR-TEST"
TEST_ITEM_CODE = f"{TEST_PREFIX}-SERVICE-ITEM"
SCENARIOS = {
	"EXACT": "exact_match",
	"PARTIAL": "partial_match",
	"INVOICE": "invoice_only",
	"PAYMENT": "payment_only",
}


def _as_bool(value, default=False):
	if value is None:
		return default
	if isinstance(value, bool):
		return value
	return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def _parse_companies(companies):
	if not companies:
		return []
	if isinstance(companies, str):
		try:
			companies = json.loads(companies)
		except Exception:
			companies = [item.strip() for item in companies.split(",") if item.strip()]
	return list(companies or [])


def _sanitize_code(value, fallback="APR"):
	import re

	value = (value or "").strip().upper()
	value = re.sub(r"[^A-Z0-9]+", "", value)
	return value or fallback


def _company_abbr(company):
	meta = frappe.get_meta("Company")
	fields = [field for field in ["abbr", "company_abbr", "abbreviation"] if meta.has_field(field)]
	if fields:
		values = frappe.db.get_value("Company", company, fields, as_dict=True) or {}
		for field in fields:
			if values.get(field):
				return _sanitize_code(values.get(field))
	return _sanitize_code("".join(part[0] for part in company.split() if part), "APR")


def _enabled_companies(limit=4):
	meta = frappe.get_meta("Company")
	filters = {}
	if meta.has_field("disabled"):
		filters["disabled"] = 0
	return frappe.get_all("Company", filters=filters, pluck="name", order_by="name asc", limit=limit)


def _first_existing(doctype, names):
	for name in names:
		if name and frappe.db.exists(doctype, name):
			return name
	return None


def _first_record(doctype, filters=None, fieldname="name", order_by="name asc"):
	rows = frappe.get_all(doctype, filters=filters or {}, pluck=fieldname, order_by=order_by, limit=1)
	return rows[0] if rows else None


def _company_field(company, fieldnames):
	meta = frappe.get_meta("Company")
	fields = [field for field in fieldnames if meta.has_field(field)]
	if not fields:
		return None
	values = frappe.db.get_value("Company", company, fields, as_dict=True) or {}
	for field in fields:
		if values.get(field):
			return values.get(field)
	return None


def _account(company, account_types=None, root_type=None):
	filters = {"company": company, "is_group": 0}
	if account_types:
		filters["account_type"] = ["in", account_types]
	if root_type:
		filters["root_type"] = root_type
	return _first_record("Account", filters=filters)


def _cost_center(company):
	company_default = _company_field(company, ["cost_center", "default_cost_center"])
	if company_default:
		return company_default
	return _first_record("Cost Center", filters={"company": company, "is_group": 0})


def _mode_of_payment():
	preferred = _first_existing("Mode of Payment", ["Bank", "Cash"])
	if preferred:
		return preferred
	filters = {"enabled": 1} if frappe.get_meta("Mode of Payment").has_field("enabled") else {}
	return _first_record("Mode of Payment", filters=filters)


def _supplier_group():
	return _first_record("Supplier Group", filters={"is_group": 0}) or _first_existing("Supplier Group", ["All Supplier Groups"])


def _item_group():
	return _first_record("Item Group", filters={"is_group": 0}) or _first_existing("Item Group", ["All Item Groups", "Products"])


def _uom():
	return _first_existing("UOM", ["Nos", "Unit", "No"]) or _first_record("UOM")


def _company_defaults(company):
	payable = _company_field(company, ["default_payable_account"]) or _account(company, ["Payable"], "Liability")
	bank_cash = _company_field(company, ["default_bank_account", "default_cash_account"]) or _account(company, ["Bank", "Cash"], "Asset")
	expense = _company_field(company, ["default_expense_account"]) or _account(company, None, "Expense")
	cost_center = _cost_center(company)
	mode_of_payment = _mode_of_payment()
	currency = _company_field(company, ["default_currency"]) or frappe.db.get_default("currency")
	missing = []
	if not payable:
		missing.append("payable account")
	if not bank_cash:
		missing.append("bank/cash account")
	if not expense:
		missing.append("expense account")
	if not cost_center:
		missing.append("cost center")
	if not mode_of_payment:
		missing.append("mode of payment")
	return frappe._dict(
		{
			"payable_account": payable,
			"bank_cash_account": bank_cash,
			"expense_account": expense,
			"cost_center": cost_center,
			"mode_of_payment": mode_of_payment,
			"currency": currency,
			"missing": missing,
		}
	)


def _scenario_plan(total):
	total = max(cint(total), 1)
	exact = int(total * 0.40)
	partial = int(total * 0.25)
	invoice_only = int(total * 0.20)
	payment_only = total - exact - partial - invoice_only
	plan = []
	for scenario, count in [
		("EXACT", exact),
		("PARTIAL", partial),
		("INVOICE", invoice_only),
		("PAYMENT", payment_only),
	]:
		plan.extend([scenario] * count)
	return plan


def _amounts(scenario, index):
	if scenario == "EXACT":
		amount = 5000 + (index * 100)
		return amount, amount
	if scenario == "PARTIAL":
		return 10000 + (index * 100), 6000 + (index * 50)
	if scenario == "INVOICE":
		return 7000 + (index * 100), 0
	return 0, 4000 + (index * 100)


def _batch_suffix(force):
	return now_datetime().strftime("%Y%m%d%H%M%S") if force else "BASE"


def _record_key(company_abbr, scenario, index, batch):
	base = f"{TEST_PREFIX}-{company_abbr}-{scenario}-{index:03d}"
	return base if batch == "BASE" else f"{base}-{batch}"


def _exists(doctype, filters):
	return frappe.db.exists(doctype, filters)


def _ensure_item(dry_run, summary):
	if frappe.db.exists("Item", TEST_ITEM_CODE):
		summary["existing_items"] = summary.get("existing_items", 0) + 1
		return TEST_ITEM_CODE
	if dry_run:
		summary["planned_items"] = summary.get("planned_items", 0) + 1
		return TEST_ITEM_CODE

	item_group = _item_group()
	uom = _uom()
	if not item_group or not uom:
		frappe.throw(_("Cannot create APR test item because Item Group or UOM was not found."))

	item = frappe.get_doc(
		{
			"doctype": "Item",
			"item_code": TEST_ITEM_CODE,
			"item_name": "APR TEST Service Item",
			"item_group": item_group,
			"stock_uom": uom,
			"is_stock_item": 0,
			"is_purchase_item": 1,
			"is_sales_item": 0,
			"description": "APR-TEST service item for Auto Payment Reconciliation testing.",
		}
	)
	item.insert(ignore_permissions=True)
	summary["created_items"] = summary.get("created_items", 0) + 1
	return item.name


def _supplier_by_test_name(supplier_name):
	return frappe.db.exists("Supplier", supplier_name) or frappe.db.get_value("Supplier", {"supplier_name": supplier_name}, "name")


def _ensure_supplier(supplier_name, dry_run, summary):
	existing = _supplier_by_test_name(supplier_name)
	if existing:
		summary["existing_suppliers"] += 1
		return existing
	if dry_run:
		summary["planned_suppliers"] += 1
		return supplier_name

	supplier_group = _supplier_group()
	if not supplier_group:
		frappe.throw(_("Supplier Group was not found."))

	supplier = frappe.get_doc(
		{
			"doctype": "Supplier",
			"supplier_name": supplier_name,
			"supplier_group": supplier_group,
			"supplier_type": "Company",
		}
	)
	supplier.insert(ignore_permissions=True)
	summary["created_suppliers"] += 1
	return supplier.name


def _purchase_invoice_exists(company, supplier, marker):
	return _exists("Purchase Invoice", {"company": company, "supplier": supplier, "bill_no": marker})


def _payment_entry_exists(company, supplier, marker):
	return _exists("Payment Entry", {"company": company, "party_type": "Supplier", "party": supplier, "reference_no": marker})


def _create_purchase_invoice(company, supplier, marker, amount, posting_date, accounts, item_code, submit_docs, dry_run, summary):
	if _purchase_invoice_exists(company, supplier, marker):
		summary["existing_purchase_invoices"] += 1
		return None
	if dry_run:
		summary["planned_purchase_invoices"] += 1
		return None

	invoice = frappe.get_doc(
		{
			"doctype": "Purchase Invoice",
			"company": company,
			"supplier": supplier,
			"posting_date": posting_date,
			"due_date": posting_date,
			"bill_no": marker,
			"bill_date": posting_date,
			"set_posting_time": 1,
			"credit_to": accounts.payable_account,
			"remarks": marker,
			"items": [
				{
					"item_code": item_code,
					"qty": 1,
					"rate": flt(amount),
					"expense_account": accounts.expense_account,
					"cost_center": accounts.cost_center,
				}
			],
		}
	)
	invoice.insert(ignore_permissions=True)
	if submit_docs:
		invoice.submit()
	summary["purchase_invoices"] += 1
	return invoice.name


def _create_payment_entry(company, supplier, marker, amount, posting_date, accounts, submit_docs, dry_run, summary):
	if _payment_entry_exists(company, supplier, marker):
		summary["existing_payment_entries"] += 1
		return None
	if dry_run:
		summary["planned_payment_entries"] += 1
		return None

	payment = frappe.get_doc(
		{
			"doctype": "Payment Entry",
			"payment_type": "Pay",
			"party_type": "Supplier",
			"party": supplier,
			"company": company,
			"posting_date": posting_date,
			"mode_of_payment": accounts.mode_of_payment,
			"paid_from": accounts.bank_cash_account,
			"paid_to": accounts.payable_account,
			"paid_amount": flt(amount),
			"received_amount": flt(amount),
			"reference_no": marker,
			"reference_date": posting_date,
			"remarks": marker,
		}
	)
	if hasattr(payment, "set_missing_values"):
		payment.set_missing_values()
	payment.insert(ignore_permissions=True)
	if submit_docs:
		payment.submit()
	summary["payment_entries"] += 1
	return payment.name


def _company_summary(company):
	return {
		"company": company,
		"created_suppliers": 0,
		"existing_suppliers": 0,
		"planned_suppliers": 0,
		"purchase_invoices": 0,
		"existing_purchase_invoices": 0,
		"planned_purchase_invoices": 0,
		"payment_entries": 0,
		"existing_payment_entries": 0,
		"planned_payment_entries": 0,
		"exact_match": 0,
		"partial_match": 0,
		"invoice_only": 0,
		"payment_only": 0,
		"skipped": 0,
		"errors": [],
	}


@frappe.whitelist()
def create_bulk_reconciliation_test_data(
	companies=None,
	suppliers_per_company=25,
	posting_date=None,
	dry_run=True,
	submit_docs=True,
	force=False,
):
	"""Create idempotent APR-TEST suppliers, Purchase Invoices, and Payment Entries.

	The default dry_run=True reports the plan only. This function never deletes old records.
	With force=True it creates a new timestamped APR-TEST batch instead of reusing BASE keys.
	"""
	companies = _parse_companies(companies) or _enabled_companies(limit=4)
	suppliers_per_company = cint(suppliers_per_company or 25)
	posting_date = str(getdate(posting_date or today()))
	dry_run = _as_bool(dry_run, default=True)
	submit_docs = _as_bool(submit_docs, default=True)
	force = _as_bool(force, default=False)
	batch = _batch_suffix(force)
	result = {
		"dry_run": dry_run,
		"submit_docs": submit_docs,
		"force": force,
		"batch": batch,
		"posting_date": posting_date,
		"companies": [],
		"next_steps": [
			"Open /app/auto_payment_reconciliation",
			"Select company",
			"Click Get Unreconciled Entries",
			"Test Allocate/Reconcile",
			"Start second company while first is running to verify queue",
		],
	}

	if not companies:
		result["errors"] = ["No enabled companies were found."]
		return result

	for company in companies:
		summary = _company_summary(company)
		result["companies"].append(summary)
		if not frappe.db.exists("Company", company):
			summary["skipped"] = suppliers_per_company
			summary["errors"].append(f"Skipped company because Company was not found: {company}")
			continue

		accounts = _company_defaults(company)
		if accounts.missing:
			summary["skipped"] = suppliers_per_company
			summary["errors"].append(
				"Skipped company because default " + ", ".join(accounts.missing) + " was not found."
			)
			continue

		try:
			item_code = _ensure_item(dry_run, summary)
		except Exception as exc:
			summary["skipped"] = suppliers_per_company
			summary["errors"].append(str(exc))
			continue

		abbr = _company_abbr(company)
		for index, scenario in enumerate(_scenario_plan(suppliers_per_company), start=1):
			marker = _record_key(abbr, scenario, index, batch)
			supplier_name = marker
			invoice_amount, payment_amount = _amounts(scenario, index)
			summary[SCENARIOS[scenario]] += 1
			try:
				supplier = _ensure_supplier(supplier_name, dry_run, summary)
				if invoice_amount:
					_create_purchase_invoice(
						company,
						supplier,
						marker,
						invoice_amount,
						posting_date,
						accounts,
						item_code,
						submit_docs,
						dry_run,
						summary,
					)
				if payment_amount:
					_create_payment_entry(
						company,
						supplier,
						marker,
						payment_amount,
						posting_date,
						accounts,
						submit_docs,
						dry_run,
						summary,
					)
			except Exception as exc:
				summary["skipped"] += 1
				summary["errors"].append(f"{marker}: {exc}")

	return result
