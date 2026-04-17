from . import __version__ as app_version

app_name = "highcool_components"
app_title = "Highcool Components"
app_publisher = "Highcool"
app_description = "Supplier component deficiency tracking for Purchase Receipts"
app_email = "dev@example.com"
app_license = "MIT"
app_version = app_version

required_apps = ["erpnext"]

add_to_apps_screen = [
	{
		"name": app_name,
		"logo": "/assets/erpnext/images/erpnext-logo.svg",
		"title": app_title,
		"route": "/app",
	}
]

doctype_js = {
	"Purchase Receipt": "highcool_component_management/public/js/purchase_receipt.js",
	"Supplier": "highcool_component_management/public/js/supplier.js",
	"Item": "highcool_component_management/public/js/item.js",
}

doc_events = {
	"Purchase Receipt": {
		"validate": "highcool_components.highcool_component_management.events.purchase_receipt_events.validate",
		"on_submit": "highcool_components.highcool_component_management.events.purchase_receipt_events.on_submit",
		"on_cancel": "highcool_components.highcool_component_management.events.purchase_receipt_events.on_cancel",
	}
}

fixtures = ["custom_field.json"]
