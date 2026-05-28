from frappe import _


def get_data():
	return [
		{
			"module_name": "Auto Payment Reconciliation",
			"type": "module",
			"label": _("Auto Payment Reconciliation"),
			"color": "blue",
			"icon": "octicon octicon-sync",
			"description": _("Supplier-wise automatic payment reconciliation"),
		}
	]

