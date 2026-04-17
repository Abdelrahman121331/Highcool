// Copyright (c) 2026, Highcool and contributors
// License: MIT

frappe.ui.form.on("Supplier", {
	refresh(frm) {
		render_missing_component_sections(frm);
	},
});

function render_missing_component_sections(frm) {
	const details_field = frm.get_field("hc_missing_components_detail_html");
	const summary_field = frm.get_field("hc_missing_components_summary_html");
	if (!details_field || !summary_field) {
		return;
	}

	if (frm.is_new() || !frm.doc.name) {
		details_field.$wrapper.html("<p class='text-muted'>Save supplier to view component deficiencies.</p>");
		summary_field.$wrapper.html("<p class='text-muted'>Save supplier to view grouped summary.</p>");
		return;
	}

	details_field.$wrapper.html("<p class='text-muted'>Loading missing component records...</p>");
	summary_field.$wrapper.html("<p class='text-muted'>Loading grouped summary...</p>");

	frappe.call({
		method: "highcool_components.highcool_component_management.api.get_supplier_missing_component_dashboard",
		args: { supplier: frm.doc.name },
		freeze: false,
		callback: (response) => {
			const payload = response.message || {};
			const details = payload.details || [];
			const summary = payload.summary || [];

			details_field.$wrapper.html(render_details_table(details));
			summary_field.$wrapper.html(render_summary_table(summary));
		},
		error: () => {
			details_field.$wrapper.html("<p class='text-danger'>Unable to load detailed data.</p>");
			summary_field.$wrapper.html("<p class='text-danger'>Unable to load grouped summary.</p>");
		},
	});
}

function render_details_table(rows) {
	if (!rows.length) {
		return "<p class='text-muted'>No missing component records for this supplier.</p>";
	}

	const body = rows
		.map((row) => {
			const component_item = esc(row.component_item);
			const missing_qty = format_float(row.missing_qty);
			const purchase_receipt = esc(row.purchase_receipt || "");
			const date = row.date ? frappe.datetime.str_to_user(row.date) : "";
			const status = esc(row.status || "");

			return `
				<tr>
					<td>${component_item}</td>
					<td class="text-right">${missing_qty}</td>
					<td>${purchase_receipt}</td>
					<td>${esc(date)}</td>
					<td>${status}</td>
				</tr>
			`;
		})
		.join("");

	return `
		<div class="table-responsive">
			<table class="table table-bordered table-sm">
				<thead>
					<tr>
						<th>${__("Component Item")}</th>
						<th class="text-right">${__("Missing Qty")}</th>
						<th>${__("Purchase Receipt")}</th>
						<th>${__("Date")}</th>
						<th>${__("Status")}</th>
					</tr>
				</thead>
				<tbody>${body}</tbody>
			</table>
		</div>
	`;
}

function render_summary_table(rows) {
	if (!rows.length) {
		return "<p class='text-muted'>No grouped missing quantity data.</p>";
	}

	const body = rows
		.map((row) => {
			const component_item = esc(row.component_item);
			const total_missing_qty = format_float(row.total_missing_qty);
			return `
				<tr>
					<td>${component_item}</td>
					<td class="text-right">${total_missing_qty}</td>
				</tr>
			`;
		})
		.join("");

	return `
		<div class="table-responsive">
			<table class="table table-bordered table-sm">
				<thead>
					<tr>
						<th>${__("Component Item")}</th>
						<th class="text-right">${__("Total Missing Qty")}</th>
					</tr>
				</thead>
				<tbody>${body}</tbody>
			</table>
		</div>
	`;
}

function esc(value) {
	return frappe.utils.escape_html(String(value || ""));
}

function format_float(value) {
	return frappe.format(value || 0, { fieldtype: "Float" });
}
