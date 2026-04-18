# Copyright (c) 2026, Highcool and contributors
# License: MIT

"""Supplier Missing Component Resolution — allocation, stock valuation, and payment."""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt, get_time, now

from erpnext.accounts.party import get_party_account
from erpnext.stock.get_item_details import get_item_defaults

SETTLEMENT_ACCOUNT_NAME = "Stocks Adjustment"


def get_grouped_unresolved_missing_components(supplier: str) -> list[dict]:
	"""Group open Supplier Missing Component rows by component item (for UI)."""
	if not supplier:
		return []

	rows = frappe.db.sql(
		"""
		SELECT
			component_item AS item_code,
			SUM(missing_qty) AS total_missing_qty,
			SUM(IFNULL(resolved_qty, 0)) AS already_resolved_qty,
			SUM(missing_qty - IFNULL(resolved_qty, 0)) AS pending_qty
		FROM `tabSupplier Missing Component`
		WHERE supplier = %s
			AND status != 'Resolved'
		GROUP BY component_item
		HAVING pending_qty > 0.0000001
		ORDER BY component_item ASC
		""",
		(supplier,),
		as_dict=True,
	)
	return rows


def validate_resolution_document(doc) -> None:
	if not doc.supplier:
		frappe.throw(_("Supplier is mandatory."))

	seen_items: set[str] = set()
	for row in doc.get("items") or []:
		if row.item_code in seen_items:
			frappe.throw(_("Duplicate Item {0} in Items. Use a single row per item.").format(row.item_code))
		seen_items.add(row.item_code)

	for row in doc.get("items") or []:
		row.pending_qty = flt(row.pending_qty)
		row.resolve_qty = flt(row.resolve_qty)
		row.total_missing_qty = flt(row.total_missing_qty)
		row.already_resolved_qty = flt(row.already_resolved_qty)

		if doc.resolution_type == "Payment":
			row.rate = flt(row.rate)
			row.amount = flt(row.resolve_qty) * row.rate
		else:
			row.rate = 0.0
			row.amount = 0.0

		if row.resolve_qty < 0:
			frappe.throw(_("Resolve Qty cannot be negative for item {0}.").format(row.item_code))
		if row.resolve_qty > row.pending_qty + 1e-6:
			frappe.throw(
				_("Resolve Qty ({0}) cannot exceed Pending Qty ({1}) for item {2}.").format(
					row.resolve_qty, row.pending_qty, row.item_code
				)
			)
		if doc.resolution_type == "Payment" and row.resolve_qty > 0 and row.rate <= 0:
			frappe.throw(_("Rate is required for Payment when Resolve Qty is positive ({0}).").format(row.item_code))

	total_amt = sum(flt(r.amount) for r in doc.get("items") or [])
	doc.total_resolve_amount = total_amt

	if doc.resolution_type == "Payment" and total_amt <= 0:
		frappe.throw(_("Total resolve amount must be greater than zero for Payment type."))

	if not any(flt(r.resolve_qty) > 0 for r in doc.get("items") or []):
		frappe.throw(_("Enter Resolve Qty on at least one item line."))


def process_resolution_submit(doc) -> None:
	doc.set("allocations", [])

	if doc.resolution_type == "Payment":
		process_payment_resolution(doc)
	else:
		process_receive_resolution(doc)


def process_receive_resolution(doc) -> None:
	allocations = build_fifo_allocations(doc)
	_append_allocations_to_doc(doc, allocations)
	apply_allocations_to_smc(doc, allocations)


def process_payment_resolution(doc) -> None:
	"""Settle supplier shortage financially without changing stock qty or valuation."""
	allocations = build_fifo_allocations(doc)
	_append_allocations_to_doc(doc, allocations)

	doc.db_set("stock_reconciliation", None, update_modified=False)

	je_name = create_settlement_journal_entry(doc)
	if je_name:
		doc.db_set("journal_entry", je_name, update_modified=False)

	apply_allocations_to_smc(doc, allocations)


def build_fifo_allocations(doc) -> list[frappe._dict]:
	"""FIFO allocate each item's resolve_qty across Supplier Missing Component rows."""
	out: list[frappe._dict] = []

	for row in doc.get("items") or []:
		qty = flt(row.resolve_qty)
		if qty <= 0:
			continue

		smc_rows = frappe.db.sql(
			"""
			SELECT name, missing_qty, IFNULL(resolved_qty, 0) AS resolved_qty
			FROM `tabSupplier Missing Component`
			WHERE supplier = %s
				AND component_item = %s
				AND status != 'Resolved'
			ORDER BY date ASC, creation ASC, name ASC
			""",
			(doc.supplier, row.item_code),
			as_dict=True,
		)

		remaining = qty
		for smc in smc_rows:
			if remaining <= 1e-9:
				break
			pending = flt(smc.missing_qty) - flt(smc.resolved_qty)
			if pending <= 1e-9:
				continue
			take = min(remaining, pending)
			out.append(
				frappe._dict(
					supplier_missing_component=smc.name,
					item_code=row.item_code,
					allocated_qty=take,
				)
			)
			remaining -= take

		if remaining > 1e-6:
			frappe.throw(
				_("Could not allocate {0} units for item {1}; insufficient open missing quantity.").format(
					remaining, row.item_code
				)
			)

	return out


def _append_allocations_to_doc(doc, allocations: list[frappe._dict]) -> None:
	for a in allocations:
		doc.append(
			"allocations",
			{
				"supplier_missing_component": a.supplier_missing_component,
				"item_code": a.item_code,
				"allocated_qty": a.allocated_qty,
			},
		)


def apply_allocations_to_smc(doc, allocations: list[frappe._dict]) -> None:
	"""Increase resolved_qty on each Supplier Missing Component row and set status."""
	# Merge quantities per SMC name (in case of duplicate lines)
	by_smc: dict[str, float] = {}
	for a in allocations:
		key = a.supplier_missing_component
		by_smc[key] = by_smc.get(key, 0.0) + flt(a.allocated_qty)

	for smc_name, add_qty in by_smc.items():
		smc = frappe.get_doc("Supplier Missing Component", smc_name)
		smc.resolved_qty = flt(smc.resolved_qty) + add_qty
		if flt(smc.resolved_qty) > flt(smc.missing_qty) + 1e-6:
			frappe.throw(
				_("Resolved Qty cannot exceed Missing Qty for {0}.").format(smc_name)
			)
		pending = flt(smc.missing_qty) - flt(smc.resolved_qty)
		if pending <= 1e-9:
			smc.status = "Resolved"
		elif flt(smc.resolved_qty) > 0:
			smc.status = "Partially Resolved"
		else:
			smc.status = "Open"
		smc.save(ignore_permissions=True)


def create_stock_reconciliation_for_valuation_reduction(doc) -> str | None:
	"""Reduce stock *value* without changing qty (re-rates existing on-hand stock).

	ERPNext ties valuation adjustments to a warehouse row with positive qty. If there is no on-hand
	stock, there is nothing to revalue in the stock ledger; we skip Stock Reconciliation for those
	lines and still complete Payment Entry + Supplier Missing Component updates.
	"""
	from erpnext.accounts.utils import get_company_default

	sr = frappe.new_doc("Stock Reconciliation")
	sr.company = doc.company
	sr.posting_date = doc.posting_date
	sr.posting_time = doc.posting_time or get_time(now())
	sr.purpose = "Stock Reconciliation"
	sr.expense_account = get_company_default(doc.company, "stock_adjustment_account")
	sr.cost_center = get_company_default(doc.company, "cost_center")
	if not sr.expense_account:
		frappe.throw(_("Please set Stock Adjustment Account for company {0}.").format(doc.company))

	has_row = False
	skipped: list[str] = []

	for row in doc.get("items") or []:
		if flt(row.resolve_qty) <= 0 or flt(row.amount) <= 0:
			continue

		item_code = row.item_code
		if not frappe.db.get_value("Item", item_code, "is_stock_item"):
			skipped.append(
				_("{0}: not a stock item — inventory valuation not adjusted (payment still posted).").format(
					item_code
				)
			)
			continue

		warehouse = get_default_warehouse(item_code, doc.company)
		if not warehouse:
			skipped.append(
				_("{0}: no default warehouse — skipped inventory valuation adjustment.").format(item_code)
			)
			continue

		bin_data = frappe.db.get_value(
			"Bin",
			{"item_code": item_code, "warehouse": warehouse},
			["actual_qty", "stock_value"],
			as_dict=True,
		)
		if not bin_data or flt(bin_data.actual_qty) <= 0:
			skipped.append(
				_(
					"{0}: no on-hand qty in {1} — skipped inventory valuation adjustment (qty is unchanged; payment still posted)."
				).format(item_code, warehouse)
			)
			continue

		current_qty = flt(bin_data.actual_qty)
		current_amount = flt(bin_data.stock_value)
		current_valuation_rate = current_amount / current_qty if current_qty else 0
		adj_amount = flt(row.amount)
		new_amount = max(current_amount - adj_amount, 0.0)
		new_valuation_rate = new_amount / current_qty if current_qty else 0

		sr.append(
			"items",
			{
				"item_code": item_code,
				"warehouse": warehouse,
				"qty": current_qty,
				"valuation_rate": new_valuation_rate,
				"current_qty": current_qty,
				"current_valuation_rate": current_valuation_rate,
			},
		)
		has_row = True

	if skipped:
		frappe.msgprint(
			"\n".join(skipped),
			title=_("Inventory valuation adjustment skipped"),
			indicator="orange",
		)

	if not has_row:
		return None

	sr.insert(ignore_permissions=True)
	sr.submit()
	return sr.name


def get_default_warehouse(item_code: str, company: str) -> str | None:
	d = get_item_defaults(item_code, company) or {}
	wh = d.get("default_warehouse")
	if wh:
		return wh
	return frappe.db.get_value("Company", company, "default_warehouse")


def create_settlement_journal_entry(doc) -> str:
	"""Post supplier shortage settlement without touching inventory value.

	Debits the supplier payable and credits a non-stock settlement account such as Stock Adjustment,
	Price Difference, or Supplier Claims.
	"""
	total = sum(flt(r.amount) for r in doc.get("items") or [])
	if total <= 0:
		frappe.throw(_("Settlement amount must be positive."))

	payable = get_party_account("Supplier", doc.supplier, doc.company)
	settlement_account = get_or_create_settlement_account(doc.company)
	_validate_non_stock_account(settlement_account)

	cc = frappe.get_cached_value("Company", doc.company, "cost_center")
	if not cc:
		frappe.throw(_("Set Default Cost Center for company {0}.").format(doc.company))

	je = frappe.new_doc("Journal Entry")
	je.voucher_type = "Journal Entry"
	je.company = doc.company
	je.posting_date = doc.posting_date
	je.posting_time = doc.posting_time or get_time(now())
	je.user_remark = _("Component shortage settlement (inventory, not cash) — {0}").format(doc.name)
	je.append(
		"accounts",
		{
			"account": payable,
			"party_type": "Supplier",
			"party": doc.supplier,
			"debit_in_account_currency": total,
			"credit_in_account_currency": 0.0,
			"cost_center": cc,
		},
	)
	je.append(
		"accounts",
		{
			"account": settlement_account,
			"debit_in_account_currency": 0.0,
			"credit_in_account_currency": total,
			"cost_center": cc,
		},
	)

	je.insert(ignore_permissions=True)
	je.submit()
	return je.name


def get_or_create_settlement_account(company: str) -> str:
	company_abbr = frappe.get_cached_value("Company", company, "abbr")
	if not company_abbr:
		frappe.throw(_("Company abbreviation is not set for {0}.").format(company))

	account_name = SETTLEMENT_ACCOUNT_NAME
	account_full_name = f"{account_name} - {company_abbr}"

	if frappe.db.exists("Account", account_full_name):
		return account_full_name

	existing_by_label = frappe.db.get_value(
		"Account",
		{"company": company, "account_name": account_name, "is_group": 0},
		"name",
	)
	if existing_by_label:
		return existing_by_label

	parent_account = _get_settlement_parent_account(company, company_abbr)
	account = frappe.get_doc(
		{
			"doctype": "Account",
			"account_name": account_name,
			"company": company,
			"parent_account": parent_account,
			"is_group": 0,
			"root_type": "Expense",
			"report_type": "Profit and Loss",
			"account_type": "Stock Adjustment",
		}
	)
	account.insert(ignore_permissions=True)
	return account.name


def _get_settlement_parent_account(company: str, company_abbr: str) -> str:
	candidate_names = [
		f"Indirect Expenses - {company_abbr}",
		f"Direct Expenses - {company_abbr}",
		f"Expenses - {company_abbr}",
	]
	for account_name in candidate_names:
		if frappe.db.exists("Account", {"name": account_name, "company": company, "is_group": 1}):
			return account_name

	parent_account = frappe.db.get_value(
		"Account",
		{
			"company": company,
			"root_type": "Expense",
			"is_group": 1,
			"parent_account": ["is", "set"],
		},
		"name",
		order_by="lft asc",
	)
	if parent_account:
		return parent_account

	frappe.throw(
		_("Could not find an Expense parent account for company {0} to create {1}.").format(
			company, SETTLEMENT_ACCOUNT_NAME
		)
	)


def _validate_non_stock_account(account: str) -> None:
	if frappe.db.get_value("Account", account, "account_type") == "Stock":
		frappe.throw(
			_(
				"Account {0} is a stock account. Please set Stock Adjustment Account to a non-stock account for payment resolutions."
			).format(account)
		)


def process_resolution_cancel(doc) -> None:
	if getattr(doc, "journal_entry", None):
		je = frappe.get_doc("Journal Entry", doc.journal_entry)
		if je.docstatus == 1:
			je.cancel()

	# Legacy vouchers from older versions
	if getattr(doc, "payment_entry", None):
		pe = frappe.get_doc("Payment Entry", doc.payment_entry)
		if pe.docstatus == 1:
			pe.cancel()

	if getattr(doc, "stock_reconciliation", None):
		sr = frappe.get_doc("Stock Reconciliation", doc.stock_reconciliation)
		if sr.docstatus == 1:
			sr.cancel()

	# Reverse resolved quantities on source missing-component rows
	for row in doc.get("allocations") or []:
		smc = frappe.get_doc("Supplier Missing Component", row.supplier_missing_component)
		smc.resolved_qty = max(flt(smc.resolved_qty) - flt(row.allocated_qty), 0.0)
		pending = flt(smc.missing_qty) - flt(smc.resolved_qty)
		if pending <= 1e-9:
			smc.status = "Resolved"
		elif flt(smc.resolved_qty) > 0:
			smc.status = "Partially Resolved"
		else:
			smc.status = "Open"
		smc.save(ignore_permissions=True)

	doc.db_set(
		{"journal_entry": None, "stock_reconciliation": None},
		update_modified=False,
	)
