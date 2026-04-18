# Copyright (c) 2026, Highcool and contributors
# License: MIT

from frappe.model.document import Document


class SupplierMissingComponentResolution(Document):
	def validate(self):
		from highcool_components.highcool_component_management.utils.resolution_service import (
			validate_resolution_document,
		)

		validate_resolution_document(self)

	def on_submit(self):
		from highcool_components.highcool_component_management.utils.resolution_service import (
			process_resolution_submit,
		)

		process_resolution_submit(self)

	def on_cancel(self):
		from highcool_components.highcool_component_management.utils.resolution_service import (
			process_resolution_cancel,
		)

		process_resolution_cancel(self)
