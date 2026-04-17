# Copyright (c) 2026, Highcool and contributors
# License: MIT

import frappe


def execute():
	_remove_legacy_custom_fields()
	_remove_legacy_doctypes()



def _remove_legacy_custom_fields():
	legacy_custom_fields = [
		("Purchase Receipt Item", "hc_component_checks"),
		("Sales Invoice Item", "hc_si_component_section"),
		("Sales Invoice Item", "parent_item"),
		("Sales Invoice Item", "parent_detail_docname"),
		("Sales Invoice Item", "is_component"),
		("Sales Invoice Item", "component_source"),
	]

	for dt, fieldname in legacy_custom_fields:
		custom_field_name = frappe.db.get_value(
			"Custom Field",
			{"dt": dt, "fieldname": fieldname},
			"name",
		)
		if custom_field_name:
			frappe.delete_doc("Custom Field", custom_field_name, force=1, ignore_permissions=True)



def _remove_legacy_doctypes():
	legacy_doctypes = [
		"FIFO Batch Component Tracker",
		"FIFO Batch Component Line",
		"Purchase Receipt Component Status",
	]

	for doctype_name in legacy_doctypes:
		if frappe.db.exists("DocType", doctype_name):
			frappe.delete_doc("DocType", doctype_name, force=1, ignore_permissions=True)
