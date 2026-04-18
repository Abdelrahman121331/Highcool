# Copyright (c) 2026, Highcool and contributors
# License: MIT

import json

import frappe
from frappe.utils import flt

from highcool_components.highcool_component_management.utils.component_helpers import (
	get_item_component_definitions,
	get_missing_components_for_purchase_receipt,
	sync_component_receipts_for_pr_item,
)


def validate(doc, method=None):
	"""Keep PR item component expected/missing quantities in sync with item qty."""
	definitions_by_item_code = {}

	for pr_item in doc.get("items") or []:
		item_code = pr_item.get("item_code")
		if not item_code:
			sync_component_receipts_for_pr_item(pr_item, definitions=[])
			continue

		if item_code not in definitions_by_item_code:
			definitions_by_item_code[item_code] = get_item_component_definitions(item_code)
		sync_component_receipts_for_pr_item(pr_item, definitions=definitions_by_item_code[item_code])
		_validate_positive_received_qty(pr_item)


def _validate_positive_received_qty(pr_item):
	"""Reject saving if any component received quantity is zero or negative."""
	try:
		rows = json.loads(pr_item.get("hc_component_receipts") or "[]")
	except Exception:
		rows = []

	if not isinstance(rows, list):
		return

	for row in rows:
		if not isinstance(row, dict):
			continue
		component_item = row.get("component_item")
		if not component_item:
			continue
		received_qty = flt(row.get("received_qty"))
		if received_qty <= 0:
			frappe.throw(
				frappe._(
					"Row {0}: Received Qty must be greater than 0 for component {1}."
				).format(pr_item.get("idx") or "?", component_item)
			)


def on_submit(doc, method=None):
	# Idempotent safety: clear any previously created rows for the same PR.
	frappe.db.delete("Supplier Missing Component", {"purchase_receipt": doc.name})

	if not doc.get("supplier"):
		return

	for missing in get_missing_components_for_purchase_receipt(doc):
		frappe.get_doc(
			{
				"doctype": "Supplier Missing Component",
				"supplier": doc.supplier,
				"component_item": missing["component_item"],
				"missing_qty": missing["missing_qty"],
				"purchase_receipt": doc.name,
				"batch_no": missing.get("batch_no") or "",
				"date": doc.posting_date,
				"status": "Open",
			}
		).insert(ignore_permissions=True)


def on_cancel(doc, method=None):
	frappe.db.delete("Supplier Missing Component", {"purchase_receipt": doc.name})
