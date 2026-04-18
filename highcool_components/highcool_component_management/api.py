# Copyright (c) 2026, Highcool and contributors
# License: MIT

import frappe
from frappe.exceptions import PermissionError


@frappe.whitelist()
def get_supplier_missing_component_dashboard(supplier: str):
	if not supplier:
		return {"details": [], "summary": []}

	if not frappe.has_permission("Supplier", "read", supplier):
		frappe.throw(frappe._("Not permitted"), PermissionError)

	details = frappe.db.sql(
		"""
		SELECT
			component_item,
			missing_qty,
			purchase_receipt,
			date,
			status
		FROM `tabSupplier Missing Component`
		WHERE supplier = %s
		ORDER BY date DESC, creation DESC
		""",
		(supplier,),
		as_dict=True,
	)

	summary = frappe.db.sql(
		"""
		SELECT
			component_item,
			SUM(missing_qty) AS total_missing_qty
		FROM `tabSupplier Missing Component`
		WHERE supplier = %s
		GROUP BY component_item
		ORDER BY total_missing_qty DESC, component_item ASC
		""",
		(supplier,),
		as_dict=True,
	)

	return {"details": details, "summary": summary}


@frappe.whitelist()
def get_grouped_unresolved_missing_components(supplier: str | None = None):
	"""Load open / partially resolved missing quantities grouped by component item (for Resolution screen)."""
	if not supplier:
		return []

	if not frappe.has_permission("Supplier", "read", supplier):
		frappe.throw(frappe._("Not permitted"), PermissionError)

	from highcool_components.highcool_component_management.utils.resolution_service import (
		get_grouped_unresolved_missing_components as fetch_grouped,
	)

	return fetch_grouped(supplier)
