// Copyright (c) 2026, Highcool and contributors
// License: MIT

frappe.ui.form.on("Supplier Missing Component Resolution", {
	supplier(frm) {
		load_grouped_items(frm);
	},
	company(frm) {
		load_grouped_items(frm);
	},
	resolution_type(frm) {
		recalculate_all_rows(frm);
	},
});

frappe.ui.form.on("Supplier Missing Component Resolution Item", {
	resolve_qty(frm, cdt, cdn) {
		recalculate_row(frm, cdt, cdn);
	},
	rate(frm, cdt, cdn) {
		recalculate_row(frm, cdt, cdn);
	},
});

function load_grouped_items(frm) {
	if (frm.doc.docstatus !== 0) {
		return;
	}
	if (!frm.doc.supplier || !frm.doc.company) {
		return;
	}

	frappe.call({
		method: "highcool_components.highcool_component_management.api.get_grouped_unresolved_missing_components",
		args: { supplier: frm.doc.supplier },
		callback(r) {
			frm.clear_table("items");
			(r.message || []).forEach((row) => {
				frm.add_child("items", {
					item_code: row.item_code,
					total_missing_qty: row.total_missing_qty,
					already_resolved_qty: row.already_resolved_qty,
					pending_qty: row.pending_qty,
					resolve_qty: 0,
					rate: 0,
					amount: 0,
				});
			});
			frm.refresh_field("items");
			recalculate_all_rows(frm);
		},
	});
}

function recalculate_row(frm, cdt, cdn) {
	const row = locals[cdt][cdn];
	if (frm.doc.resolution_type === "Payment") {
		row.amount = frappe.utils.flt(row.resolve_qty) * frappe.utils.flt(row.rate);
	} else {
		row.rate = 0;
		row.amount = 0;
	}
	frm.refresh_field("items");
}

function recalculate_all_rows(frm) {
	(frm.doc.items || []).forEach((row) => {
		if (frm.doc.resolution_type === "Payment") {
			row.amount = frappe.utils.flt(row.resolve_qty) * frappe.utils.flt(row.rate);
		} else {
			row.rate = 0;
			row.amount = 0;
		}
	});
	frm.refresh_field("items");
}
