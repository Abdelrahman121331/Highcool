// Copyright (c) 2026, Highcool and contributors
// License: MIT

frappe.ui.form.on("Purchase Receipt", {
	refresh(frm) {
		if (frm.doc.docstatus !== 0) {
			return;
		}
	},
});

frappe.ui.form.on("Purchase Receipt Item", {
	item_code(frm, cdt, cdn) {
		seed_component_receipts_for_row(frm, locals[cdt][cdn]);
	},
	qty(frm, cdt, cdn) {
		seed_component_receipts_for_row(frm, locals[cdt][cdn]);
	},
	hc_edit_component_receipts(frm, cdt, cdn) {
		open_component_receipts_dialog_for_row(frm, locals[cdt][cdn]);
	},
});

function seed_component_receipts_for_row(frm, row) {
	if (!row) {
		return Promise.resolve();
	}

	if (!row.item_code) {
		row.hc_component_receipts = "[]";
		refresh_pr_item_row(frm, row);
		return Promise.resolve();
	}

	const item_code = row.item_code;
	const parent_qty = to_non_negative(row.qty || 0);

	return frappe.model.with_doc("Item", item_code).then(() => {
		if (!row.item_code || row.item_code !== item_code) {
			return;
		}

		const item = frappe.get_doc("Item", item_code) || {};
		const definitions = (item.hc_item_components || []).filter((line) => line.item_code);
		if (!definitions.length) {
			row.hc_component_receipts = "[]";
			refresh_pr_item_row(frm, row);
			return;
		}

		const existing = get_component_receipts_from_row(row);
		const existing_received = {};
		existing.forEach((line) => {
			if (line.component_item) {
				existing_received[line.component_item] = to_non_negative(line.received_qty);
			}
		});

		const rows = definitions.map((definition) => {
			const expected_qty = to_non_negative(definition.qty_per_unit) * parent_qty;
			const received_qty =
				existing_received[definition.item_code] !== undefined
					? existing_received[definition.item_code]
					: 0;
			return {
				component_item: definition.item_code,
				expected_qty,
				received_qty,
				missing_qty: Math.max(expected_qty - received_qty, 0),
			};
		});

		row.hc_component_receipts = JSON.stringify(rows);
		refresh_pr_item_row(frm, row);
	});
}

function open_component_receipts_dialog_for_row(frm, row) {
	if (!row) {
		return;
	}
	if (!row.item_code) {
		frappe.msgprint(__("Set Item Code on the selected row first."));
		return;
	}

	return seed_component_receipts_for_row(frm, row).then(() => {
		const source_rows = get_component_receipts_from_row(row);
		if (!source_rows.length) {
			frappe.msgprint(__("Selected item has no component definition."));
			return;
		}

		const dialog = new frappe.ui.Dialog({
			title: __("Component Receipts (Row {0})", [row.idx]),
			fields: [
				{
					fieldname: "component_receipts",
					fieldtype: "Table",
					label: __("Components"),
					cannot_add_rows: true,
					in_place_edit: true,
					data: source_rows,
					get_data: () => source_rows,
					fields: [
						{
							fieldtype: "Link",
							fieldname: "component_item",
							label: __("Component"),
							options: "Item",
							in_list_view: 1,
							read_only: 1,
						},
						{
							fieldtype: "Float",
							fieldname: "expected_qty",
							label: __("Expected Qty"),
							in_list_view: 1,
							read_only: 1,
						},
						{
							fieldtype: "Float",
							fieldname: "received_qty",
							label: __("Received Qty"),
							in_list_view: 1,
							reqd: 1,
						},
						{
							fieldtype: "Float",
							fieldname: "missing_qty",
							label: __("Missing Qty"),
							in_list_view: 1,
							read_only: 1,
						},
					],
				},
			],
			primary_action_label: __("Apply"),
			primary_action(values) {
				const rows = (values && values.component_receipts) || source_rows;
				const invalid_row = rows.find((dialog_row) => {
					if (!dialog_row.component_item) {
						return false;
					}
					return to_non_negative(dialog_row.received_qty) <= 0;
				});
				if (invalid_row) {
					frappe.msgprint(
						__("Received Qty must be greater than 0 for component {0}.", [
							invalid_row.component_item,
						])
					);
					return;
				}

				const normalized_rows = rows
					.filter((dialog_row) => dialog_row.component_item)
					.map((dialog_row) => {
						const expected_qty = to_non_negative(dialog_row.expected_qty);
						const received_qty = to_non_negative(dialog_row.received_qty);
						return {
							component_item: dialog_row.component_item,
							expected_qty,
							received_qty,
							missing_qty: Math.max(expected_qty - received_qty, 0),
						};
					});

				row.hc_component_receipts = JSON.stringify(normalized_rows);
				refresh_pr_item_row(frm, row);
				frm.dirty();
				dialog.hide();
			},
		});

		dialog.show();
	});
}

function get_component_receipts_from_row(row) {
	let parsed = [];
	try {
		parsed = JSON.parse(row.hc_component_receipts || "[]");
	} catch (e) {
		parsed = [];
	}
	if (!Array.isArray(parsed)) {
		parsed = [];
	}
	return parsed
		.filter((line) => line && line.component_item)
		.map((line) => {
			const expected_qty = to_non_negative(line.expected_qty);
			const received_qty = to_non_negative(line.received_qty);
			return {
				component_item: line.component_item,
				expected_qty,
				received_qty,
				missing_qty: Math.max(expected_qty - received_qty, 0),
			};
		});
}

function to_non_negative(value) {
	const num = Number(value);
	if (!Number.isFinite(num) || num < 0) {
		return 0;
	}
	return num;
}

function refresh_pr_item_row(frm, row) {
	const grid = frm.get_field("items") && frm.get_field("items").grid;
	if (grid && row && row.name) {
		grid.refresh_row(row.name);
	} else {
		frm.refresh_field("items");
	}
}
