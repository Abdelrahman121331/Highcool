# Copyright (c) 2026, Highcool and contributors
# License: MIT

import frappe


def execute():
	_convert_custom_field_to_json_storage()
	_remove_nested_child_doctype()
	frappe.clear_cache(doctype="Purchase Receipt Item")


def _convert_custom_field_to_json_storage():
	custom_field_name = frappe.db.get_value(
		"Custom Field",
		{"dt": "Purchase Receipt Item", "fieldname": "hc_component_receipts"},
		"name",
	)
	if not custom_field_name:
		return

	frappe.db.set_value(
		"Custom Field",
		custom_field_name,
		{
			"fieldtype": "Small Text",
			"options": "",
			"hidden": 1,
			"label": "Component receipts (JSON)",
		},
	)


def _remove_nested_child_doctype():
	if frappe.db.exists("DocType", "Purchase Receipt Component Entry"):
		frappe.delete_doc("DocType", "Purchase Receipt Component Entry", force=1, ignore_permissions=True)
