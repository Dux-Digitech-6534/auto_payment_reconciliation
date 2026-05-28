import re

import frappe
from frappe.model.document import Document
from frappe.utils import getdate, nowdate


def _sanitize_code(value, fallback=""):
	value = (value or "").strip().upper()
	value = re.sub(r"[^A-Z0-9]+", "", value)
	return value or fallback


def _initials(value):
	parts = re.findall(r"[A-Za-z0-9]+", value or "")
	return "".join(part[0] for part in parts).upper()


def _company_value(company, fieldnames):
	meta = frappe.get_meta("Company")
	available = [fieldname for fieldname in fieldnames if meta.has_field(fieldname)]
	if not available:
		return None

	values = frappe.db.get_value("Company", company, available, as_dict=True) or {}
	for fieldname in available:
		if values.get(fieldname):
			return values.get(fieldname)
	return None


def _financial_year_code(posting_date=None):
	date = getdate(posting_date or nowdate())
	start_year = date.year if date.month >= 4 else date.year - 1
	end_year = start_year + 1
	return f"{str(start_year)[-2:]}-{str(end_year)[-2:]}"


def _next_run_name(prefix):
	latest = frappe.get_all(
		"Auto Payment Reconciliation Run",
		filters={"name": ["like", f"{prefix}%"]},
		pluck="name",
		order_by="name desc",
		limit=1,
	)
	number = 1
	if latest:
		match = re.search(r"/(\d{4,})$", latest[0])
		if match:
			number = int(match.group(1)) + 1
	return f"{prefix}{number:04d}"


def _run_name_prefix(abbr, location, financial_year):
	abbr = _sanitize_code(abbr, "APR")
	location = _sanitize_code(location)
	segments = [abbr]
	if location and location != abbr:
		segments.append(location)
	segments.extend(["APR", financial_year])
	return "/".join(segments) + "/"


def _company_abbr(company):
	abbr = _company_value(company, ["abbr", "company_abbr", "abbreviation"])
	return _sanitize_code(abbr, _sanitize_code(_initials(company), "APR"))


def _company_location(company):
	return _sanitize_code(
		_company_value(
			company,
			[
				"location",
				"custom_location",
				"campus",
				"custom_campus",
				"branch",
				"custom_branch",
				"city",
				"custom_city",
			],
		)
	)


def _company_run_prefix(company, posting_date=None):
	return _run_name_prefix(_company_abbr(company), _company_location(company), _financial_year_code(posting_date))


def _has_duplicate_abbr_segment(name, company):
	abbr = _company_abbr(company)
	return bool(re.match(rf"^{re.escape(abbr)}/{re.escape(abbr)}/APR/\d{{2}}-\d{{2}}/\d{{4,}}$", name or ""))


def _assign_run_name(doc):
	doc.name = _next_run_name(_company_run_prefix(doc.company, doc.from_date))


class AutoPaymentReconciliationRun(Document):
	def autoname(self):
		_assign_run_name(self)

	def before_insert(self):
		if not self.name or _has_duplicate_abbr_segment(self.name, self.company):
			_assign_run_name(self)

	def validate(self):
		if self.company and self.payable_account:
			account_company = frappe.db.get_value("Account", self.payable_account, "company")
			if account_company and account_company != self.company:
				frappe.throw("Payable Account must belong to the selected Company.")

		if self.company and self.default_advance_account:
			account_company = frappe.db.get_value("Account", self.default_advance_account, "company")
			if account_company and account_company != self.company:
				frappe.throw("Default Advance Account must belong to the selected Company.")
