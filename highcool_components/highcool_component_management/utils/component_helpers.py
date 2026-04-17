# Copyright (c) 2026, Highcool and contributors
# License: MIT

import json

import frappe
from frappe.utils import flt


def get_item_component_definitions(item_code: str | None) -> list[dict]:
	"""Return component definition rows from Item.hc_item_components."""
	if not item_code:
		return []

	rows = frappe.get_all(
		"Item Component Row",
		filters={
			"parenttype": "Item",
			"parentfield": "hc_item_components",
			"parent": item_code,
		},
		fields=["item_code", "qty_per_unit"],
		order_by="idx asc",
	)
	return [
		{
			"component_item": row.item_code,
			"qty_per_unit": flt(row.qty_per_unit),
		}
		for row in rows
		if row.item_code
	]


def _parse_component_receipts_json(raw_value) -> list[dict]:
	if not raw_value:
		return []
	if isinstance(raw_value, list):
		return raw_value
	try:
		parsed = json.loads(raw_value)
	except Exception:
		return []
	return parsed if isinstance(parsed, list) else []


def sync_component_receipts_for_pr_item(pr_item_row, definitions: list[dict] | None = None):
	"""Store component receipt values as JSON on PR item row (no nested child table)."""
	if not pr_item_row.get("item_code"):
		pr_item_row.hc_component_receipts = "[]"
		return

	definitions = definitions if definitions is not None else get_item_component_definitions(pr_item_row.item_code)
	if not definitions:
		pr_item_row.hc_component_receipts = "[]"
		return

	existing_rows = _parse_component_receipts_json(pr_item_row.get("hc_component_receipts"))
	existing_received_by_component = {
		row.get("component_item"): max(flt(row.get("received_qty")), 0.0)
		for row in existing_rows
		if row.get("component_item")
	}

	parent_qty = max(flt(pr_item_row.get("qty")), 0.0)
	rows = []
	for definition in definitions:
		component_item = definition["component_item"]
		expected_qty = max(flt(definition["qty_per_unit"]) * parent_qty, 0.0)
		received_qty = existing_received_by_component.get(component_item, expected_qty)
		missing_qty = max(expected_qty - received_qty, 0.0)
		rows.append(
			{
				"component_item": component_item,
				"expected_qty": expected_qty,
				"received_qty": received_qty,
				"missing_qty": missing_qty,
			}
		)

	pr_item_row.hc_component_receipts = json.dumps(rows)


def get_missing_components_for_purchase_receipt(doc) -> list[dict]:
	"""Compute missing component rows from PR item component receipts JSON."""
	missing_rows = []
	definitions_by_item_code = {}

	for pr_item in doc.get("items") or []:
		item_code = pr_item.get("item_code")
		if not item_code:
			continue

		if item_code not in definitions_by_item_code:
			definitions_by_item_code[item_code] = get_item_component_definitions(item_code)
		definitions = definitions_by_item_code[item_code]
		if not definitions:
			continue

		receipt_rows = _parse_component_receipts_json(pr_item.get("hc_component_receipts"))
		entries_by_component = {
			row.get("component_item"): row for row in receipt_rows if row.get("component_item")
		}
		parent_qty = max(flt(pr_item.get("qty")), 0.0)

		for definition in definitions:
			component_item = definition["component_item"]
			expected_qty = max(flt(definition["qty_per_unit"]) * parent_qty, 0.0)
			entry = entries_by_component.get(component_item)
			received_qty = max(flt((entry or {}).get("received_qty")), 0.0)
			if not entry:
				received_qty = expected_qty
			missing_qty = max(expected_qty - received_qty, 0.0)
			if missing_qty <= 1e-9:
				continue

			missing_rows.append(
				{
					"component_item": component_item,
					"missing_qty": missing_qty,
					"batch_no": pr_item.get("batch_no"),
				}
			)

	return missing_rows
