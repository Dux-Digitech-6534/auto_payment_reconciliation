frappe.pages["auto_payment_reconciliation"].on_page_load = function (wrapper) {
	new AutoPaymentReconciliationPage(wrapper);
};

class AutoPaymentReconciliationPage {
	constructor(wrapper) {
		this.wrapper = $(wrapper);
		this.page = frappe.ui.make_app_page({
			parent: wrapper,
			title: __("Auto Payment Reconciliation"),
			single_column: true,
		});

		this.rows = [];
		this.filtered_rows = [];
		this.selected = new Set();
		this.run_name = null;
		this.currency = null;
		this.poller = null;
		this.status = null;
		this.company_control = null;
		this.date_range_control = null;
		this.party_label = __("Supplier Name");
		this.busy = false;

		this.inject_styles();
		this.render();
		this.make_company_control();
		this.make_date_range_control();
		this.bind_events();
		this.refresh_status();
	}

	inject_styles() {
		if (document.getElementById("apr-inline-style")) return;
		const css = `
			.apr-page{padding-bottom:24px}.apr-title-row,.apr-section-head,.apr-bottom-actions,.apr-page-actions,.apr-filters{display:flex;gap:10px}.apr-title-row{align-items:center;justify-content:space-between;margin-bottom:12px}.apr-breadcrumb{color:var(--text-color);font-size:16px;font-weight:600}.apr-muted,.apr-help{color:var(--text-muted);font-size:12px}.apr-card{background:var(--card-bg);border:1px solid var(--border-color);border-radius:8px;margin-bottom:12px;padding:14px}.apr-section-title{font-size:12px;font-weight:700;letter-spacing:.04em;margin-bottom:10px;text-transform:uppercase}.apr-company-control{max-width:420px}.apr-status-banner{background:#eef6ff;border:1px solid #cfe5ff;border-radius:8px;margin-bottom:12px;padding:14px}.apr-status-banner.apr-banner-completed{background:#effaf2;border-color:#cfeedd}.apr-status-banner.apr-banner-failed{background:#fff1f1;border-color:#ffd2d2}.apr-status-banner.apr-banner-neutral{background:var(--card-bg);border-color:var(--border-color)}.apr-banner-head{align-items:flex-start;display:flex;gap:12px;justify-content:space-between;margin-bottom:10px}.apr-banner-title{font-size:14px;font-weight:700}.apr-banner-subtitle{color:var(--text-muted);font-size:12px;margin-top:3px}.apr-banner-grid{display:grid;gap:10px;grid-template-columns:repeat(4,minmax(0,1fr));margin-top:12px}.apr-banner-item span{color:var(--text-muted);display:block;font-size:11px;margin-bottom:2px}.apr-banner-item strong{display:block;font-size:12px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.apr-status-pill,.apr-queue-badge,.apr-badge{border-radius:999px;display:inline-flex;font-size:11px;font-weight:600;line-height:1;padding:5px 8px}.apr-status-pill{align-items:center;gap:6px}.apr-status-dot{border-radius:50%;display:inline-block;height:8px;width:8px}.apr-status-running,.apr-status-completed{color:var(--green-700)}.apr-status-running .apr-status-dot,.apr-status-completed .apr-status-dot{background:var(--green-500,#16a34a)}.apr-status-queued,.apr-status-waiting{color:var(--blue-700)}.apr-status-queued .apr-status-dot,.apr-status-waiting .apr-status-dot{background:var(--blue-500,#2563eb)}.apr-status-failed{color:var(--red-700)}.apr-status-failed .apr-status-dot{background:var(--red-500,#dc2626)}.apr-status-not-started{color:var(--gray-700)}.apr-status-not-started .apr-status-dot{background:var(--gray-500,#6b7280)}.apr-progress-head{align-items:center;display:flex;font-size:12px;justify-content:space-between}.apr-progress-head span{color:var(--text-muted);font-size:11px}.apr-progress-head strong{font-size:12px}.apr-progress{background:rgba(255,255,255,.7);border-radius:999px;height:8px;overflow:hidden}.apr-progress-bar{background:var(--blue-500,#2563eb);height:8px;transition:width .2s ease;width:0}.apr-remaining{color:var(--orange-600,#c2410c);font-weight:700}.apr-queue-strip{background:var(--card-bg);border:1px solid var(--border-color);border-radius:8px;margin-bottom:12px;padding:12px 14px}.apr-queue-head{align-items:center;display:flex;justify-content:space-between;margin-bottom:8px}.apr-queue-body{display:grid;gap:8px}.apr-queue-row{align-items:center;border-top:1px solid var(--border-color);display:grid;gap:10px;grid-template-columns:30px minmax(0,1fr) auto;padding-top:8px}.apr-queue-row:first-child{border-top:0;padding-top:0}.apr-queue-position{align-items:center;background:var(--blue-500,#2563eb);border-radius:50%;color:#fff;display:inline-flex;font-size:12px;font-weight:700;height:24px;justify-content:center;width:24px}.apr-queue-company{font-size:12px;font-weight:700;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.apr-queue-requested,.apr-queue-time{color:var(--text-muted);font-size:11px}.apr-queue-badge{background:var(--blue-100);color:var(--blue-700);white-space:nowrap}.apr-filters{align-items:center;flex-wrap:wrap;margin:12px 0}.apr-filters .form-control{max-width:205px}.apr-check{align-items:center;color:var(--text-color);display:flex;font-size:12px;gap:6px;margin:0;min-height:32px}.apr-table-wrap{overflow-x:auto}.apr-table{background:var(--card-bg);font-size:12px;margin-bottom:0;white-space:nowrap}.apr-table thead th{background:var(--fg-color);border-color:var(--border-color);color:var(--text-muted);font-weight:600;vertical-align:middle}.apr-table tbody td{border-color:var(--border-color);vertical-align:middle}.apr-table tbody tr:hover{background:var(--highlight-color)}.apr-table tbody tr.apr-selected-row{background:#e7f1ff}.apr-select-col{text-align:center;width:34px}.apr-diff-zero{color:var(--green-600);font-weight:600}.apr-diff-nonzero{color:var(--red-600);font-weight:600}.apr-match-exact-match,.apr-allocation-auto-allocated,.apr-allocation-completed{background:var(--green-100);color:var(--green-700)}.apr-match-partial-match{background:var(--yellow-100);color:var(--yellow-700)}.apr-match-needs-review,.apr-allocation-error,.apr-allocation-failed{background:var(--red-100);color:var(--red-700)}.apr-allocation-ready-for-allocation,.apr-allocation-reconciled,.apr-allocation-running,.apr-allocation-queued{background:var(--blue-100);color:var(--blue-700)}.apr-allocation-pending-review,.apr-allocation-not-started,.apr-allocation-waiting{background:var(--gray-100);color:var(--gray-700)}.apr-bottom-actions{justify-content:flex-end;margin-top:12px}.apr-dialog-tabs{border-bottom:1px solid var(--border-color);display:flex;gap:4px;margin-bottom:14px}.apr-tab{background:transparent;border:0;border-bottom:2px solid transparent;color:var(--text-muted);font-weight:600;padding:8px 12px}.apr-tab.active{border-bottom-color:var(--primary);color:var(--text-color)}.apr-summary-grid{display:grid;gap:10px;grid-template-columns:repeat(2,minmax(0,1fr))}.apr-summary-item{border:1px solid var(--border-color);border-radius:8px;padding:10px}.apr-summary-item span{color:var(--text-muted);display:block;font-size:12px;margin-bottom:4px}.apr-summary-item strong{font-size:13px;word-break:break-word}.apr-doc-link{color:var(--blue-600);font-weight:600;text-decoration:none}.apr-doc-link:hover{text-decoration:underline}@media(max-width:1100px){.apr-banner-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:768px){.apr-title-row,.apr-page-actions,.apr-bottom-actions{align-items:stretch;flex-direction:column}.apr-filters .form-control{max-width:none;width:100%}.apr-summary-grid,.apr-banner-grid{grid-template-columns:1fr}.apr-queue-row{grid-template-columns:30px minmax(0,1fr)}.apr-queue-badge{grid-column:2}}
		`;
		$(`<style id="apr-inline-style">${css}</style>`).appendTo("head");
	}

	render() {
		$(this.page.main).html(`
			<div class="apr-page">
				<div class="apr-title-row">
					<div>
						<div class="apr-breadcrumb">${__("Invoicing")} &gt; ${__("Auto Payment Reconciliation")}</div>
						<div class="apr-muted">${__("Supplier-wise automatic payment reconciliation using ERPNext accounting data.")}</div>
					</div>
					<div class="apr-page-actions">
						<button class="btn btn-default btn-sm apr-get">${__("Get Unreconciled Entries")}</button>
						<button class="btn btn-default btn-sm apr-allocate" disabled>${__("Allocate")}</button>
						<button class="btn btn-primary btn-sm apr-reconcile" disabled>${__("Reconcile")}</button>
					</div>
				</div>

				<section class="apr-status-banner apr-banner-neutral">
					<div class="apr-section-title">${__("Current Reconciliation")}</div>
					<div class="apr-status-banner-body"></div>
					<div class="apr-help">${__("Only one company reconciliation at a time. Next starts automatically.")}</div>
				</section>

				<section class="apr-queue-strip">
					<div class="apr-queue-head">
						<div class="apr-section-title">${__("Company Queue")}</div>
					</div>
					<div class="apr-queue-body"></div>
				</section>

				<section class="apr-card apr-company-section">
					<div class="apr-section-title">${__("Company Selection")}</div>
					<div class="apr-company-control"></div>
					<div class="apr-help">${__("Company is fetched from ERPNext Company Master.")}</div>
				</section>

				<section class="apr-card">
					<div class="apr-section-head">
						<div>
							<div class="apr-section-title">${__("Supplier-wise Unreconciled Entries")}</div>
							<div class="apr-help">${__("Suppliers are automatically fetched from ERPNext Supplier Master. No manual supplier selection required.")}</div>
						</div>
					</div>

					<div class="apr-filters">
						<input class="form-control apr-filter-search" type="text" placeholder="${__("Search Supplier")}">
						<select class="form-control apr-filter-status">
							<option value="">${__("All Match Statuses")}</option>
							<option value="Exact Match">${__("Exact Match")}</option>
							<option value="Partial Match">${__("Partial Match")}</option>
							<option value="Needs Review">${__("Needs Review")}</option>
						</select>
						<input class="form-control apr-filter-amount" type="text" placeholder="${__("Amount Range")}">
						<div class="apr-date-range-control"></div>
						<label class="apr-check">
							<input type="checkbox" class="apr-filter-exact"> ${__("Show Only Exact Matches")}
						</label>
					</div>

					<div class="apr-table-wrap">
						<table class="table table-bordered apr-table">
							<thead>
								<tr>
									<th class="apr-select-col"><input type="checkbox" class="apr-select-visible"></th>
									<th class="apr-party-name-label">${this.party_label}</th>
									<th>${__("Invoices")}</th>
									<th>${__("Payments")}</th>
									<th>${__("Invoice Amt.")}</th>
									<th>${__("Payment Amt.")}</th>
									<th>${__("Difference")}</th>
									<th>${__("Match Status")}</th>
									<th>${__("Allocation Status")}</th>
									<th>${__("Action")}</th>
								</tr>
							</thead>
							<tbody class="apr-table-body"></tbody>
						</table>
					</div>

					<div class="apr-bottom-actions">
						<button class="btn btn-default btn-sm apr-select-exact">${__("Select All Exact Matches")}</button>
						<button class="btn btn-default btn-sm apr-export" disabled>${__("Export")}</button>
					</div>
				</section>
			</div>
		`);
	}

	make_company_control() {
		this.company_control = frappe.ui.form.make_control({
			parent: this.wrapper.find(".apr-company-control"),
			df: {
				fieldtype: "Link",
				fieldname: "company",
				label: __("Company"),
				options: "Company",
				reqd: 1,
			},
			render_input: true,
		});
		this.company_control.set_value(frappe.defaults.get_default("company"));
		this.wrapper.find(".apr-party-name-label").text(this.party_label);
	}

	make_date_range_control() {
		this.date_range_control = frappe.ui.form.make_control({
			parent: this.wrapper.find(".apr-date-range-control"),
			df: {
				fieldtype: "DateRange",
				fieldname: "date_range",
				placeholder: __("Date Range"),
			},
			render_input: true,
		});
		this.date_range_control.$input.addClass("apr-filter-date").attr("placeholder", __("Date Range"));
	}

	bind_events() {
		this.wrapper.on("click", ".apr-get", () => this.get_unreconciled_entries());
		this.wrapper.on("click", ".apr-allocate", () => this.allocate_selected());
		this.wrapper.on("click", ".apr-reconcile", () => this.reconcile_selected());
		this.wrapper.on("click", ".apr-select-exact", () => this.select_exact_matches());
		this.wrapper.on("click", ".apr-export", () => this.export_entries());
		this.wrapper.on("click", ".apr-view", (e) => this.view_supplier($(e.currentTarget).data("supplier")));
		this.wrapper.on("click", ".apr-doc-link", (e) => this.open_doc_link(e));
		this.wrapper.on("change", ".apr-row-check", (e) => {
			const supplier = $(e.currentTarget).data("supplier");
			if (e.currentTarget.checked) {
				this.selected.add(supplier);
			} else {
				this.selected.delete(supplier);
			}
			this.render_table();
			this.update_action_state();
		});
		this.wrapper.on("change", ".apr-select-visible", (e) => {
			for (const row of this.filtered_rows) {
				if (e.currentTarget.checked) {
					this.selected.add(row.supplier);
				} else {
					this.selected.delete(row.supplier);
				}
			}
			this.render_table();
			this.update_action_state();
		});
		this.wrapper.on("input change", ".apr-filter-search, .apr-filter-status, .apr-filter-amount, .apr-filter-date, .apr-filter-exact", () => {
			this.apply_filters();
		});
	}

	get_company() {
		return this.company_control && this.company_control.get_value();
	}

	get_filters() {
		const date_range = this.get_date_range();
		return {
			run_name: this.run_name,
			from_date: date_range && date_range.from_date,
			to_date: date_range && date_range.to_date,
		};
	}

	get_date_range() {
		const control_value = this.date_range_control && this.date_range_control.get_value();
		return this.parse_date_range(control_value || this.wrapper.find(".apr-filter-date").val());
	}

	get_selected_suppliers() {
		return Array.from(this.selected);
	}

	get_unreconciled_entries() {
		const company = this.get_company();
		if (!company) {
			frappe.msgprint(__("Please select Company first."));
			return;
		}
		frappe.dom.freeze(__("Fetching unreconciled supplier entries..."));
		frappe.call({
			method: "auto_payment_reconciliation.api.get_unreconciled_entries",
			args: {
				company,
				filters: this.get_filters(),
			},
			always: () => frappe.dom.unfreeze(),
			callback: (r) => {
				if (!r.message) return;
				this.run_name = r.message.run_name;
				this.currency = r.message.currency;
				this.rows = r.message.rows || [];
				this.selected.clear();
				this.apply_filters();
				this.render_status(r.message.status);
				if (this.should_poll(r.message.status)) {
					this.start_polling();
				}
				frappe.show_alert({
					message: this.rows.length ? __("Loaded {0} supplier rows", [this.rows.length]) : __("No unreconciled entries found"),
					indicator: this.rows.length ? "green" : "orange",
				});
			},
		});
	}

	apply_filters() {
		const search = (this.wrapper.find(".apr-filter-search").val() || "").toLowerCase();
		const status = this.wrapper.find(".apr-filter-status").val();
		const exact_only = this.wrapper.find(".apr-filter-exact").is(":checked");
		const amount_range = this.parse_range(this.wrapper.find(".apr-filter-amount").val());
		const date_range = this.get_date_range();

		this.filtered_rows = this.rows.map((row) => this.date_filtered_row(row, date_range)).filter(Boolean).filter((row) => {
			const text = `${row.supplier_name || ""} ${row.supplier_id || ""} ${row.supplier || ""}`.toLowerCase();
			if (search && !text.includes(search)) return false;
			if (status && row.match_status !== status) return false;
			if (exact_only && row.match_status !== "Exact Match") return false;
			if (amount_range) {
				const amount = Math.max(flt(row.invoice_amount), flt(row.payment_amount));
				if (amount < amount_range.min || amount > amount_range.max) return false;
			}
			return true;
		});
		this.render_table();
	}

	parse_range(value) {
		if (!value) return null;
		const parts = String(value)
			.replace(/,/g, "")
			.split(/-|to/i)
			.map((part) => flt(part.trim()))
			.filter((part) => !isNaN(part));
		if (!parts.length) return null;
		return { min: parts[0] || 0, max: parts[1] || Number.MAX_SAFE_INTEGER };
	}

	parse_date_range(value) {
		if (!value) return null;
		if (Array.isArray(value)) {
			const from_date = this.normalize_date(value[0]);
			const to_date = this.normalize_date(value[1] || value[0]);
			return from_date ? { from_date, to_date: to_date || from_date } : null;
		}

		const parsed = this.date_range_control && this.date_range_control.parse && this.date_range_control.parse(value);
		if (Array.isArray(parsed)) return this.parse_date_range(parsed);

		const parts = String(value)
			.split(/\s+to\s+|,/i)
			.map((part) => part.trim())
			.filter(Boolean);
		if (!parts.length) return null;
		const from_date = this.normalize_date(parts[0]);
		const to_date = this.normalize_date(parts[1] || parts[0]) || from_date;
		return from_date ? { from_date, to_date } : null;
	}

	normalize_date(value) {
		if (!value) return null;
		if (moment(value, "YYYY-MM-DD", true).isValid()) return value;
		const parsed = frappe.datetime.user_to_str(value);
		return parsed && parsed !== "Invalid date" ? parsed : null;
	}

	date_filtered_row(row, range) {
		if (!range) return row;
		const invoices = this.safe_json(row.invoice_refs_json).filter((ref) => this.ref_in_date_range(ref, range));
		const payments = this.safe_json(row.payment_refs_json).filter((ref) => this.ref_in_date_range(ref, range));
		if (!invoices.length && !payments.length) return null;

		const invoice_amount = invoices.reduce((total, ref) => total + flt(ref.outstanding_amount), 0);
		const payment_amount = payments.reduce((total, ref) => total + flt(ref.unallocated_amount), 0);
		const difference = flt(invoice_amount - payment_amount);
		const display_row = {
			...row,
			invoices_count: invoices.length,
			payments_count: payments.length,
			invoice_amount,
			payment_amount,
			difference,
			invoice_refs_json: JSON.stringify(invoices),
			payment_refs_json: JSON.stringify(payments),
		};

		if (invoice_amount > 0 && payment_amount > 0) {
			display_row.match_status = Math.abs(difference) < 0.000001 ? "Exact Match" : "Partial Match";
			if (!["Reconciled", "Error"].includes(display_row.allocation_status)) {
				display_row.allocation_status = display_row.match_status === "Exact Match" ? "Auto Allocated" : "Ready for Allocation";
			}
		} else {
			display_row.match_status = "Needs Review";
			if (display_row.allocation_status !== "Reconciled") display_row.allocation_status = "Pending Review";
		}

		return display_row;
	}

	ref_in_date_range(ref, range) {
		const date = this.normalize_date(ref.posting_date || ref.invoice_date || ref.due_date);
		if (!date) return false;
		return date >= range.from_date && date <= range.to_date;
	}

	safe_json(value) {
		try {
			return value ? JSON.parse(value) : [];
		} catch (e) {
			return [];
		}
	}

	render_table() {
		const body = this.wrapper.find(".apr-table-body");
		if (!this.filtered_rows.length) {
			body.html(`<tr><td colspan="10" class="text-muted text-center">${__("No unreconciled entries found")}</td></tr>`);
			this.update_action_state();
			return;
		}

		body.html(
			this.filtered_rows
				.map((row) => {
					const checked = this.selected.has(row.supplier);
					const selected_class = checked ? "apr-selected-row" : "";
					return `
						<tr class="${selected_class}">
							<td class="apr-select-col">
								<input type="checkbox" class="apr-row-check" data-supplier="${frappe.utils.escape_html(row.supplier)}" ${checked ? "checked" : ""}>
							</td>
							<td><strong>${frappe.utils.escape_html(row.supplier_name || row.supplier)}</strong></td>
							<td>${cint(row.invoices_count)}</td>
							<td>${cint(row.payments_count)}</td>
							<td>${this.currency_value(row.invoice_amount)}</td>
							<td>${this.currency_value(row.payment_amount)}</td>
							<td class="${flt(row.difference) === 0 ? "apr-diff-zero" : "apr-diff-nonzero"}">${this.currency_value(row.difference)}</td>
							<td>${this.badge(row.match_status, "match")}</td>
							<td>${this.badge(row.allocation_status, "allocation")}</td>
							<td><button class="btn btn-link btn-xs apr-view" data-supplier="${frappe.utils.escape_html(row.supplier)}">${__("View")}</button></td>
						</tr>
					`;
				})
				.join("")
		);
		this.wrapper.find(".apr-select-visible").prop(
			"checked",
			this.filtered_rows.length > 0 && this.filtered_rows.every((row) => this.selected.has(row.supplier))
		);
		this.update_action_state();
	}

	currency_value(value) {
		const currency = this.currency || frappe.defaults.get_default("currency");
		return format_currency(flt(value), currency);
	}

	badge(value, type) {
		const key = String(value || "").toLowerCase().replace(/\s+/g, "-");
		return `<span class="apr-badge apr-${type}-${key}">${frappe.utils.escape_html(value || "")}</span>`;
	}

	selected_rows() {
		return this.rows.filter((row) => this.selected.has(row.supplier));
	}

	first_selection_message(rows) {
		const row = rows.find((item) => item.eligibility_message) || rows[0];
		return row && row.eligibility_message ? row.eligibility_message : __("Payment Entry not available for selected supplier.");
	}

	update_action_state() {
		const has_run = Boolean(this.run_name);
		const has_rows = has_run && this.rows.length > 0;
		const rows = this.selected_rows();
		const can_allocate = rows.some((row) => row.can_allocate);
		const can_reconcile = rows.some((row) => row.can_reconcile);
		const message = rows.length ? this.first_selection_message(rows) : __("Select supplier rows first.");
		this.wrapper.find(".apr-allocate").prop("disabled", !can_allocate || this.busy).attr("title", can_allocate ? "" : message);
		this.wrapper.find(".apr-reconcile").prop("disabled", !can_reconcile || this.busy).attr("title", can_reconcile ? "" : message);
		this.wrapper.find(".apr-export").prop("disabled", !has_rows);
	}

	select_exact_matches() {
		this.selected.clear();
		for (const row of this.rows) {
			if (row.match_status === "Exact Match") {
				this.selected.add(row.supplier);
			}
		}
		this.apply_filters();
	}

	allocate_selected() {
		if (!this.run_name) {
			frappe.msgprint(__("Please get unreconciled entries first."));
			return;
		}
		const suppliers = this.get_selected_suppliers();
		const rows = this.selected_rows();
		if (!suppliers.length) {
			frappe.msgprint(__("Please select at least one supplier."));
			return;
		}
		if (!rows.some((row) => row.can_allocate)) {
			frappe.msgprint(this.first_selection_message(rows));
			return;
		}
		frappe.call({
			method: "auto_payment_reconciliation.api.allocate_selected",
			args: { run_name: this.run_name, suppliers },
			callback: (r) => {
				if (!r.message) return;
				this.apply_server_update(r.message, suppliers);
				const skipped = cint(r.message.skipped || 0);
				frappe.msgprint({
					title: __("Allocation Summary"),
					message: __("Allocated: {0}<br>Skipped: {1}<br>Failed: {2}", [r.message.allocated || 0, skipped, r.message.failed || 0]),
					indicator: r.message.failed ? "orange" : "green",
				});
			},
		});
	}

	reconcile_selected() {
		if (!this.run_name) {
			frappe.msgprint(__("Please get unreconciled entries first."));
			return;
		}
		const suppliers = this.get_selected_suppliers();
		const rows = this.selected_rows();
		if (!suppliers.length) {
			frappe.msgprint(__("Please select at least one supplier."));
			return;
		}
		if (!rows.some((row) => row.can_reconcile)) {
			frappe.msgprint(this.first_selection_message(rows));
			return;
		}

		frappe.confirm(__("Reconcile selected suppliers using ERPNext native Payment Reconciliation?"), () => {
			frappe.call({
				method: "auto_payment_reconciliation.api.reconcile_selected",
				args: { run_name: this.run_name, suppliers },
				callback: (r) => {
					if (!r.message) return;
					this.apply_server_update(r.message, suppliers);
					frappe.msgprint({
						title: __("Reconciliation Queued"),
						message: r.message.message,
						indicator: r.message.status === "Queued" ? "blue" : "orange",
					});
					this.start_polling();
				},
			});
		});
	}

	apply_server_update(message, keep_selected) {
		if (message.run_name) this.run_name = message.run_name;
		if (message.currency) this.currency = message.currency;
		if (message.rows) {
			const keep = new Set(keep_selected || this.get_selected_suppliers());
			this.rows = message.rows || [];
			this.selected = new Set(this.rows.filter((row) => keep.has(row.supplier)).map((row) => row.supplier));
			this.apply_filters();
		}
		const status = typeof message.status === "object" ? message.status : message.status_data;
		this.render_status(status || this.status);
	}

	export_entries() {
		if (!this.run_name) {
			frappe.msgprint(__("Please get unreconciled entries first."));
			return;
		}
		frappe.call({
			method: "auto_payment_reconciliation.api.export_unreconciled_entries",
			args: { run_name: this.run_name, filters: this.get_filters() },
			callback: (r) => {
				if (!r.message) return;
				const blob = new Blob([r.message.content], { type: r.message.content_type || "text/csv" });
				const url = URL.createObjectURL(blob);
				const link = document.createElement("a");
				link.href = url;
				link.download = r.message.filename;
				document.body.appendChild(link);
				link.click();
				document.body.removeChild(link);
				URL.revokeObjectURL(url);
			},
		});
	}

	view_supplier(supplier) {
		const company = this.get_company();
		frappe.call({
			method: "auto_payment_reconciliation.api.get_supplier_details",
			args: {
				company,
				supplier,
				filters: this.get_filters(),
			},
			callback: (r) => {
				if (!r.message) return;
				this.show_supplier_dialog(r.message);
			},
		});
	}

	show_supplier_dialog(data) {
		const summary = data.summary || {};
		const dialog = new frappe.ui.Dialog({
			title: __("Supplier Details: {0} ({1})", [summary.supplier_name || summary.supplier, summary.supplier_id || summary.supplier]),
			size: "extra-large",
			fields: [
				{
					fieldtype: "HTML",
					fieldname: "details",
					options: this.supplier_details_html(data),
				},
			],
		});
		dialog.show();
		dialog.$wrapper.on("click", ".apr-doc-link", (e) => this.open_doc_link(e));
		dialog.$wrapper.on("click", ".apr-tab", function () {
			const tab = $(this).data("tab");
			dialog.$wrapper.find(".apr-tab").removeClass("active");
			$(this).addClass("active");
			dialog.$wrapper.find(".apr-tab-panel").addClass("hide");
			dialog.$wrapper.find(`.apr-tab-panel[data-panel="${tab}"]`).removeClass("hide");
		});
	}

	supplier_details_html(data) {
		const summary = data.summary || {};
		const invoice_rows = (data.invoices || [])
			.map(
				(row) => `
					<tr>
						<td>${frappe.utils.escape_html(row.invoice_type || "")}</td>
						<td>${this.doc_link(row.reference_doctype || row.doctype || row.invoice_type || "Purchase Invoice", row.invoice_number)}</td>
						<td>${frappe.datetime.str_to_user(row.posting_date || "")}</td>
						<td>${frappe.datetime.str_to_user(row.due_date || "")}</td>
						<td>${this.currency_value(row.outstanding_amount)}</td>
						<td>${frappe.utils.escape_html(row.currency || "")}</td>
						<td>${frappe.utils.escape_html(row.account || "")}</td>
					</tr>
				`
			)
			.join("");
		const payment_rows = (data.payments || [])
			.map(
				(row) => `
					<tr>
						<td>${frappe.utils.escape_html(row.payment_type || "")}</td>
						<td>${this.doc_link(row.reference_doctype || row.doctype || row.payment_type, row.reference_name)}</td>
						<td>${frappe.datetime.str_to_user(row.posting_date || "")}</td>
						<td>${this.currency_value(row.unallocated_amount)}</td>
						<td>${frappe.utils.escape_html(row.currency || "")}</td>
						<td>${frappe.utils.escape_html(row.account || "")}</td>
					</tr>
				`
			)
			.join("");

		return `
			<div class="apr-dialog-tabs">
				<button class="apr-tab active" data-tab="summary">${__("Summary")}</button>
				<button class="apr-tab" data-tab="invoices">${__("Invoices")}</button>
				<button class="apr-tab" data-tab="payments">${__("Payments")}</button>
			</div>
			<div class="apr-tab-panel" data-panel="summary">
				<div class="apr-summary-grid">
					${this.summary_item(__("Supplier"), summary.supplier_name || summary.supplier)}
					${this.summary_item(__("Supplier ID"), summary.supplier_id || summary.supplier)}
					${this.summary_item(__("Company"), summary.company)}
					${this.summary_item(__("Run ID"), summary.run_name)}
					${this.summary_item(__("Invoice count"), summary.invoices_count)}
					${this.summary_item(__("Payment count"), summary.payments_count)}
					${this.summary_item(__("Invoice total"), this.currency_value(summary.invoice_amount))}
					${this.summary_item(__("Payment total"), this.currency_value(summary.payment_amount))}
					${this.summary_item(__("Difference"), this.currency_value(summary.difference))}
					${this.summary_item(__("Match status"), summary.match_status)}
					${this.summary_item(__("Allocation status"), summary.allocation_status)}
					${this.summary_item(__("Reconciled By"), summary.reconciled_by)}
					${this.summary_item(__("Reconciled On"), frappe.datetime.str_to_user(summary.reconciled_on || ""))}
					${this.summary_item(__("Time Taken"), summary.duration_display)}
					${this.summary_item(__("Remarks/errors"), summary.last_error || summary.remarks)}
				</div>
			</div>
			<div class="apr-tab-panel hide" data-panel="invoices">
				${this.details_table(["Invoice Type", "Invoice Number", "Posting Date", "Due Date", "Outstanding Amount", "Currency", "Account"], invoice_rows)}
			</div>
			<div class="apr-tab-panel hide" data-panel="payments">
				${this.details_table(["Payment Document", "Reference Name", "Posting Date", "Unallocated Amount", "Currency", "Account"], payment_rows)}
			</div>
		`;
	}

	doc_link(doctype, name) {
		if (!doctype || !name) return frappe.utils.escape_html(name || "");
		const href = this.form_link(doctype, name);
		return `<a href="${frappe.utils.escape_html(href)}" class="apr-doc-link" data-doctype="${frappe.utils.escape_html(doctype)}" data-name="${frappe.utils.escape_html(name)}" target="_blank" rel="noopener noreferrer">${frappe.utils.escape_html(name)}</a>`;
	}

	form_link(doctype, name) {
		const slug = String(doctype || "")
			.trim()
			.toLowerCase()
			.replace(/\s+/g, "-");
		return `/app/${encodeURIComponent(slug)}/${encodeURIComponent(name)}`;
	}

	open_doc_link(e) {
		e.preventDefault();
		const href = e.currentTarget.getAttribute("href");
		if (href) {
			const opened = window.open(href, "_blank", "noopener,noreferrer");
			if (opened) opened.opener = null;
			return;
		}
		const doctype = $(e.currentTarget).data("doctype");
		const name = $(e.currentTarget).data("name");
		if (doctype && name) {
			const opened = window.open(this.form_link(doctype, name), "_blank", "noopener,noreferrer");
			if (opened) opened.opener = null;
		}
	}

	summary_item(label, value) {
		const display = value === undefined || value === null ? "" : value;
		return `<div class="apr-summary-item"><span>${frappe.utils.escape_html(label)}</span><strong>${frappe.utils.escape_html(display)}</strong></div>`;
	}

	details_table(headers, rows) {
		return `
			<div class="apr-table-wrap">
				<table class="table table-bordered apr-table">
					<thead><tr>${headers.map((header) => `<th>${__(header)}</th>`).join("")}</tr></thead>
					<tbody>${rows || `<tr><td colspan="${headers.length}" class="text-muted text-center">${__("No entries found.")}</td></tr>`}</tbody>
				</table>
			</div>
		`;
	}

	start_polling() {
		if (!this.poller) {
			this.poller = setInterval(() => this.refresh_status(), 4000);
		}
		this.refresh_status();
	}

	should_poll(status) {
		const current = status || {};
		const active = current.active_run || current.active || {};
		const queue = current.queue || [];
		return ["Queued", "Running"].includes(active.status) || queue.some((row) => ["Queued", "Running", "Waiting"].includes(row.status));
	}

	refresh_status() {
		frappe.call({
			method: "auto_payment_reconciliation.api.get_reconciliation_status",
			args: {
				run_name: this.run_name,
				company: this.get_company(),
			},
			callback: (r) => {
				this.apply_polled_rows(r.message);
				this.render_status(r.message);
				if (this.should_poll(r.message)) {
					if (!this.poller) this.poller = setInterval(() => this.refresh_status(), 4000);
				} else {
					if (this.poller) clearInterval(this.poller);
					this.poller = null;
				}
			},
		});
	}

	apply_polled_rows(message) {
		if (!message || !Array.isArray(message.rows)) return;
		const keep = new Set(this.get_selected_suppliers());
		this.currency = message.currency || this.currency;
		this.rows = message.rows || [];
		this.selected = new Set(this.rows.filter((row) => keep.has(row.supplier)).map((row) => row.supplier));
		this.apply_filters();
	}

	render_status(status) {
		this.status = status || {};
		const active = this.status.active_run || this.status.active || {};
		const queue = this.status.queue || [];
		const status_value = active.status || "Not Started";
		const progress = status_value === "Completed" ? 100 : Math.min(Math.max(flt(active.progress_percent), 0), 100);
		const banner = this.wrapper.find(".apr-status-banner");
		const body = this.wrapper.find(".apr-status-banner-body");
		const company = active.company || this.get_company() || "";
		const current_supplier = active.current_supplier_name || active.current_supplier || "";
		const processed = `${cint(active.processed_entries)} / ${cint(active.total_entries)} ${__("suppliers")}`;

		this.busy = ["Queued", "Running"].includes(active.status) && active.company === this.get_company();
		this.update_action_state();

		banner.removeClass("apr-banner-running apr-banner-queued apr-banner-completed apr-banner-failed apr-banner-neutral");

		if (!active.name && !active.status) {
			banner.addClass("apr-banner-neutral");
			body.html(`<div class="apr-muted">${__("No active reconciliation.")}</div>`);
			this.render_queue(queue);
			return;
		}

		banner.addClass(`apr-banner-${String(status_value).toLowerCase().replace(/\s+/g, "-")}`);

		let title = `${company || __("Company")} — ${__("Reconciliation")} ${frappe.utils.escape_html(status_value)}`;
		let subtitle = "";
		let detail_html = "";

		if (status_value === "Running") {
			title = `${company} — ${__("Reconciliation in Progress")}`;
			subtitle = `${__("Started by")}: ${frappe.utils.escape_html(active.started_by_full_name || active.started_by || "")} · ${this.datetime_value(active.started_on)}`;
			detail_html = `
				${this.banner_item(__("Current Supplier"), current_supplier)}
				${this.banner_item(__("Processed"), processed)}
				${this.banner_item(__("Remaining Time"), active.remaining_time || "", "apr-remaining")}
				${this.banner_item(__("Last Updated"), this.datetime_value(active.last_updated_on))}
			`;
		} else if (status_value === "Queued") {
			title = `${company} — ${__("Reconciliation Queued")}`;
			subtitle = `${__("Requested by")}: ${frappe.utils.escape_html(active.requested_by_full_name || active.requested_by || "")}`;
			detail_html = `
				${this.banner_item(__("Queue Position"), active.queue_position || "")}
				${this.banner_item(__("Estimated Start"), active.estimated_start_display || this.relative_time(active.estimated_start) || "")}
				${this.banner_item(__("Estimated Duration"), active.estimated_duration_display || active.estimated_duration || "")}
				${this.banner_item(__("Requested On"), this.datetime_value(active.requested_on))}
			`;
		} else if (status_value === "Completed") {
			title = `${company} — ${__("Reconciliation Completed")}`;
			subtitle = `${__("Reconciled by")}: ${frappe.utils.escape_html(active.reconciled_by_full_name || active.reconciled_by || "")}`;
			detail_html = `
				${this.banner_item(__("Completed On"), this.datetime_value(active.completed_on))}
				${this.banner_item(__("Time Taken"), active.duration_display || "")}
				${this.banner_item(__("Processed"), `${cint(active.total_entries)} / ${cint(active.total_entries)} ${__("suppliers")}`)}
				${this.banner_item(__("Progress"), "100%")}
			`;
		} else if (status_value === "Failed") {
			title = `${company} — ${__("Reconciliation Failed")}`;
			subtitle = `${__("Error")}: ${frappe.utils.escape_html(active.error_log || "")}`;
			detail_html = `
				${this.banner_item(__("Time Taken"), active.duration_display || "")}
				${this.banner_item(__("Completed On"), this.datetime_value(active.completed_on))}
				${this.banner_item(__("Processed"), processed)}
				${this.banner_item(__("Progress"), `${progress}%`)}
			`;
		} else {
			title = `${company || __("Company")} — ${__("No active reconciliation")}`;
			subtitle = __("No active reconciliation.");
			detail_html = `
				${this.banner_item(__("Status"), status_value === "Draft" ? __("Not Started") : status_value)}
				${this.banner_item(__("Company"), company)}
				${this.banner_item(__("Processed"), processed)}
				${this.banner_item(__("Progress"), `${progress}%`)}
			`;
		}

		body.html(`
			<div class="apr-banner-head">
				<div>
					<div class="apr-banner-title">${frappe.utils.escape_html(title)}</div>
					<div class="apr-banner-subtitle">${subtitle}</div>
				</div>
				${this.status_pill(status_value === "Draft" ? __("Not Started") : status_value)}
			</div>
			<div class="apr-progress-head"><span>${__("Progress")}</span><strong>${progress}% ${__("complete")}</strong></div>
			<div class="apr-progress"><div class="apr-progress-bar"></div></div>
			<div class="apr-banner-grid">${detail_html}</div>
		`);
		this.wrapper.find(".apr-progress-bar").css("width", `${progress || 0}%`);
		this.render_queue(queue);
	}

	render_queue(queue) {
		const queue_html = queue.length
			? queue.map((row) => this.queue_row(row)).join("")
			: `<div class="text-muted small">${__("No company is queued.")}</div>`;
		this.wrapper.find(".apr-queue-body").html(queue_html);
	}

	queue_row(row) {
		const position = String(row.position || row.queue_position || "");
		const company = row.company || "";
		const requested_by = row.requested_by_full_name || row.requested_by || "";
		const status = row.status_display || row.status || __("Waiting");
		const start = row.estimated_start_display || this.relative_time(row.estimated_start) || "";
		const duration = row.estimated_duration_display || row.estimated_duration || "";
		return `
			<div class="apr-queue-row">
				<span class="apr-queue-position">${frappe.utils.escape_html(position)}</span>
				<div>
					<div class="apr-queue-company" title="${frappe.utils.escape_html(company)}">${frappe.utils.escape_html(company)}</div>
					<div class="apr-queue-requested">${__("Requested by")}: ${frappe.utils.escape_html(requested_by)}</div>
					<div class="apr-queue-time">${__("Start")}: ${frappe.utils.escape_html(start)} | ${__("Est.")}: ${frappe.utils.escape_html(duration)}</div>
				</div>
				<div class="apr-queue-badge">${frappe.utils.escape_html(status)}</div>
			</div>
		`;
	}

	banner_item(label, value, value_class = "") {
		return `<div class="apr-banner-item"><span>${frappe.utils.escape_html(label)}</span><strong class="${value_class}">${frappe.utils.escape_html(value || "")}</strong></div>`;
	}

	status_pill(status) {
		const key = String(status || __("Not Started")).toLowerCase().replace(/\s+/g, "-");
		return `<span class="apr-status-pill apr-status-${frappe.utils.escape_html(key)}"><span class="apr-status-dot"></span>${frappe.utils.escape_html(status)}</span>`;
	}

	relative_time(value) {
		if (!value) return "";
		const diff = moment(value).diff(moment(), "minutes");
		if (diff <= 0) return __("Now");
		return __("After {0} min", [String(diff).padStart(2, "0")]);
	}

	datetime_value(value) {
		return value ? frappe.datetime.str_to_user(value) : "";
	}

	status_line(label, value) {
		return `<div class="apr-status-line"><span>${frappe.utils.escape_html(label)}</span><strong>${value || ""}</strong></div>`;
	}
}
