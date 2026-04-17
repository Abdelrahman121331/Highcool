# Highcool Components

Custom ERPNext v15 app: component-based inventory definitions, Purchase Receipt batch completeness tracking, FIFO batch selection, and Sales Invoice validation with component-level stock deduction via a `Sales Invoice` controller override (`get_item_list`).

Install on your bench:

```bash
bench get-app /path/to/highcool_components  # or copy into apps/
bench --site [site] install-app highcool_components
bench --site [site] migrate
bench build --app highcool_components
```

Composite finished goods should use **batch tracking** on the Item so each Purchase Receipt line can register a `FIFO Batch Component Tracker` row.

**Stock note:** Sales invoices deduct **component** stock only (finished-good line is excluded from the stock ledger list). Finished-good on-hand from Purchase Receipts may need periodic **Stock Reconciliation** if you treat FG as a logical batch label only.
