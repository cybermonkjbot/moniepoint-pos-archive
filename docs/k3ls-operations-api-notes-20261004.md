# K3LS operations API notes

Source inspection on 4 October 2026. For implementing workbook workflows against the installed code, not a report of site configuration or completed transactions.

ERPNext is **16.37.0**, commit `af63cde4941570ec7b9e12422c68302762cfcf91`. Frappe is **16.36.1**, commit `97a5dd93ca5883bcc9c4ef9834120c5cba397b67`. Versions come from [ERPNext __init__.py](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/erpnext/erpnext/__init__.py:9) and [Frappe __init__.py](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/frappe/frappe/__init__.py:58). File links below refer to these local checkouts. The ERPNext working diff was limited to `banking/yarn.lock`; Frappe had no working diff. App source already contains unrelated, uncommitted implementation changes. References to app behavior describe the source inspected during this task, not deployed behavior.

No site initialization, DB access, credentials, client data, tests, builds or servers were used. Examples are proposed server-side calls and were not executed. The research skill requests a background agent; that tool was unavailable, so the source research was completed directly. Only this note was written.

## Decisions that affect implementation

| Workbook operation | Installed API and fields |
| --- | --- |
| New shop-owned stock bought from a supplier | `Purchase Invoice`, `update_stock=1`, item `warehouse`, positive `qty`, purchase `rate`. Submit once. |
| Receipt without a supplier bill, including consigned intake | `Stock Entry`, `purpose="Material Receipt"`, item `t_warehouse`, positive `qty`, `basic_rate`. |
| Warehouse transfer | `Stock Entry`, `purpose="Material Transfer"`, item `s_warehouse` and `t_warehouse`, positive `qty`. Source bundle is Outward; core creates the destination bundle. |
| Opening stock/count correction | `Stock Reconciliation`, absolute target `qty`, `valuation_rate`, header `expense_account`. There is no `difference_account` document field. |
| Supplier invoice payment/customer debt collection | `get_payment_entry(dt=..., dn=...)` returns an unsaved Payment Entry. Customer settlement references a Sales Invoice, not a POS Invoice. |
| POS/SI return | The matching module's `make_sales_return(source_name=..., target_doc=None)` returns a draft. Keep original child-row references. |
| Consignment cost/liability accrual | Ordinary balanced `Journal Entry`. Expense debit and Supplier Payable credit use account-currency amount fields. |
| Owner payout | Supplier `Payment Entry`, `payment_type="Pay"`, referenced to the accrual Journal Entry. Payment debits the liability; it does not incur the cost again. |

The sections below give source evidence and concrete payloads for each row.

## Frappe document lifecycle and API boundary

Use `frappe.get_doc(payload).insert()` followed by `doc.submit()` for a new accounting/stock document. `insert()` performs normal permission and validation checks. `submit()` sets `docstatus=1` and saves; do not write ledger rows directly. Relevant implementation is [Document.insert](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/frappe/frappe/model/document.py:439), [Document._submit and submit](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/frappe/frappe/model/document.py:1329).

For browser calls, the whitelisted equivalents are `frappe.client.insert(doc=payload)`, `frappe.client.save(doc=payload)`, `frappe.client.submit(doc=payload)` and `frappe.client.cancel(doctype=..., name=...)`. `doc` accepts a dictionary or JSON string. Insert/save/submit allow POST and PUT; a custom workflow endpoint should use POST and enforce its own shop, document and account permissions. See [frappe/client.py:220-291](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/frappe/frappe/client.py:220).

Submission order is `before_validate`, `validate`, `before_submit`, persistence, `on_update`, then `on_submit`. For each event, the controller implementation runs before configured `doc_events` handlers. Handlers for the specific DocType precede wildcard handlers. Notifications, webhooks, server scripts and automations follow the composed controller/app event. See [run_before_save_methods](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/frappe/frappe/model/document.py:1393), [run_post_save_methods](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/frappe/frappe/model/document.py:1447), [run_method](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/frappe/frappe/model/document.py:1246), [Document.hook](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/frappe/frappe/model/document.py:1635).

Do not commit inside a document-event handler. Frappe disables transaction control while executing app hooks. Normal unsafe HTTP requests commit at the request boundary and exceptions roll back. The native POS merge wrapper also has its own commit/rollback behavior, discussed below. See [hook transaction-control guard](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/frappe/frappe/model/document.py:1638), [request transaction handling](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/frappe/frappe/app.py:458).

## Stock Entry receipts and transfers

### Single-item helper

Whitelisted import path:

```python
from erpnext.stock.doctype.stock_entry.stock_entry_utils import make_stock_entry
```

Runtime signature is `make_stock_entry(**args)`. Verified accepted keys include `item_code`, `qty`, `company`, `from_warehouse`, `to_warehouse`, `rate`, `basic_rate`, `serial_no`, `batch_no`, `batches`, `posting_date`, `posting_time`, `purpose`, `cost_center`, `expense_account`, `conversion_factor`, `use_serial_batch_fields`, `is_opening`, `add_to_transit`, `inspection_required`, `apply_putaway_rule`, `purchase_receipt_no`, `delivery_note_no`, `sales_invoice_no`, `do_not_save`, `do_not_submit`. The type overload advertises only a subset. See [stock_entry_utils.py:18-206](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/erpnext/erpnext/stock/doctype/stock_entry/stock_entry_utils.py:18).

The helper creates one child row. It infers Material Transfer when both warehouses exist, Material Issue for source only, and Material Receipt for target only. It maps `rate` to child `basic_rate`, derives company from a warehouse if omitted, and selects the standard Stock Entry Type. By default it **inserts and submits immediately**. `do_not_submit=True` gives a saved draft; `do_not_save=True` returns an unsaved Stock Entry. See the same source, lines 83-134 and 177-206.

```python
# Draft receipt, with caller-controlled submission.
receipt = make_stock_entry(
    item_code=item_code, qty=quantity, company=company,
    to_warehouse=warehouse, purpose="Material Receipt",
    rate=unit_inventory_cost, expense_account=difference_account,
    cost_center=cost_center, posting_date=posting_date,
    posting_time=posting_time, is_opening="No", do_not_submit=True,
)
# Later, after workflow-specific authorization and checks:
receipt.submit()

transfer = make_stock_entry(
    item_code=item_code, qty=quantity, company=company,
    from_warehouse=source_warehouse, to_warehouse=target_warehouse,
    purpose="Material Transfer", expense_account=difference_account,
    cost_center=cost_center, posting_date=posting_date,
    posting_time=posting_time, do_not_submit=True,
)
```

Do not use a receipt plus a stock-updating Purchase Invoice for the same units. A Stock Entry is an inventory transaction and does not itself create a Supplier invoice or payable. Core Stock Entry submission creates SLEs, then GL entries. Stock GL offsets the warehouse inventory account against the difference account. See [StockEntry.on_submit](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/erpnext/erpnext/stock/doctype/stock_entry/stock_entry.py:582), [StockController.get_gl_entries](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/erpnext/erpnext/controllers/stock_controller.py:767).

### Multiple rows and zero-value intake

For multiple products, create a Stock Entry directly. Payload fields are header `company`, `purpose`, `stock_entry_type`, `posting_date`, `posting_time`, `set_posting_time`, `is_opening`; child `item_code`, `qty`, `uom`, `stock_uom`, `conversion_factor`, `s_warehouse`, `t_warehouse`, `basic_rate`, `expense_account`, `cost_center`, `allow_zero_valuation_rate`, and either legacy serial fields or `serial_and_batch_bundle`. See [Stock Entry schema](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/erpnext/erpnext/stock/doctype/stock_entry/stock_entry.json:1), [Stock Entry Detail schema](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/erpnext/erpnext/stock/doctype/stock_entry_detail/stock_entry_detail.json:1).

```python
entry = frappe.get_doc({
    "doctype": "Stock Entry", "company": company,
    "purpose": "Material Receipt", "is_opening": "No",
    "posting_date": posting_date, "posting_time": posting_time,
    "set_posting_time": 1,
    "items": [{
        "item_code": item_code, "qty": quantity,
        "uom": stock_uom, "stock_uom": stock_uom,
        "conversion_factor": 1, "t_warehouse": warehouse,
        "basic_rate": 0, "allow_zero_valuation_rate": 1,
        "expense_account": difference_account, "cost_center": cost_center,
    }],
})
entry.set_stock_entry_type()
entry.insert()
entry.submit()
```

The helper does not copy arbitrary kwargs into its child row. In particular, passing `allow_zero_valuation_rate` to `make_stock_entry` does not set that field. For a non-customer-provided zero-value receipt, use a direct document or `do_not_save=True`, set the child flag, then insert/submit. Customer-provided validation sets the flag automatically. `do_not_save=True` is not a no-write guarantee if serial/batch arguments cause the helper to create a bundle first. See [helper child payload and persistence](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/erpnext/erpnext/stock/doctype/stock_entry/stock_entry_utils.py:139), [zero-valuation validation](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/erpnext/erpnext/controllers/stock_controller.py:1722).

For perpetual inventory, every Stock Entry row still needs a difference account, even for zero-value stock. It must not have account type `Stock`. Opening `is_opening="Yes"` rejects P&L difference accounts. `allow_zero_valuation_rate=1` can force a nonzero incoming `basic_rate` to zero, so do not set it on normal costed purchases. See [validate_difference_account](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/erpnext/erpnext/stock/doctype/stock_entry/stock_entry.py:901), [set_basic_rate](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/erpnext/erpnext/stock/doctype/stock_entry/stock_entry.py:1545).

### Serial/batch bundles

Server helper:

```python
from erpnext.stock.serial_batch_bundle import SerialBatchCreation

bundle = SerialBatchCreation({
    "item_code": item_code, "company": company,
    "warehouse": warehouse,
    "voucher_type": "Stock Entry",
    "type_of_transaction": "Inward",
    "total_qty": quantity,
    "serial_nos": serial_numbers,  # list[str], not newline text
    "batches": {},                # or {batch_name: positive_quantity}
    "posting_date": posting_date, "posting_time": posting_time,
    "do_not_submit": True,
}).make_serial_and_batch_bundle()
```

`SerialBatchCreation(args)` takes one dictionary. `.make_serial_and_batch_bundle(serial_nos=None, batch_nos=None)` returns a saved bundle document, or an empty `frappe._dict` when there are no entries. `do_not_submit=True` means **save a draft**, not no persistence. Without it, the helper submits. `qty` or `total_qty` establishes the required quantity; `posting_datetime` can replace date/time. `voucher_no` and `voucher_detail_no` can be supplied when known. The parent controller later links the bundle to its voucher and row. See [SerialBatchCreation](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/erpnext/erpnext/stock/serial_batch_bundle.py:1128), [bundle creation](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/erpnext/erpnext/stock/serial_batch_bundle.py:1215), [parent-link assignment](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/erpnext/erpnext/stock/doctype/serial_and_batch_bundle/serial_and_batch_bundle.py:951).

Pass `serial_nos` as a list. This class iterates it directly, creating one entry per serial with qty `+1` for Inward or `-1` for Outward. A newline string would be iterated character by character. Batch dictionaries hold positive quantities; core applies the transaction sign. For transfer, create an **Outward** bundle in the source warehouse and attach it to the Stock Entry Detail. Core creates a separate Inward bundle for the destination SLE; do not create an extra receipt. See [set_serial_batch_entries](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/erpnext/erpnext/stock/serial_batch_bundle.py:1421), [transfer source/target processing](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/erpnext/erpnext/stock/doctype/stock_entry/stock_entry.py:2315).

For explicit new serial masters, the whitelisted API is:

```python
from erpnext.stock.doctype.serial_and_batch_bundle.serial_and_batch_bundle import create_serial_nos
entries = create_serial_nos(item_code=item_code, serial_nos="\n".join(serial_numbers))
```

It returns entry dictionaries such as `{"serial_no": ..., "qty": 1}` and inserts missing Serial No masters. Creating a bundle with explicit serials is not, by itself, this master-creation call. Alternatively, legacy input `serial_no="\n".join(serial_numbers)`, `use_serial_batch_fields=1` on the parent row lets core parse the text and create missing masters on Inward flow. Do not attach both an independent bundle and conflicting legacy values. See [create_serial_nos](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/erpnext/erpnext/stock/doctype/serial_and_batch_bundle/serial_and_batch_bundle.py:2028), [legacy bundle creation](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/erpnext/erpnext/controllers/stock_controller.py:412), [legacy normalization](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/erpnext/erpnext/controllers/stock_controller.py:647), [Inward master creation](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/erpnext/erpnext/stock/serial_batch_bundle.py:1352).

Bundle validation requires Stock Settings `enable_serial_and_batch_no_for_item`. Serial/batch availability and quantity remain validated. Bundle naming also depends on Stock Settings; if bundle naming by naming series is enabled, `naming_series` must be supplied. No settings were read in this task. See [bundle validation](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/erpnext/erpnext/stock/doctype/serial_and_batch_bundle/serial_and_batch_bundle.py:91).

## Stock Reconciliation and opening difference account

Whitelisted lookup:

```python
from erpnext.stock.doctype.stock_reconciliation.stock_reconciliation import get_difference_account
account = get_difference_account(purpose="Opening Stock", company=company)
```

`purpose="Stock Reconciliation"` returns the Company's `stock_adjustment_account`; other purposes look up a non-group Account in that company with `account_type="Temporary"`. The return can be empty if no matching account exists. The document field is **`expense_account`**, labelled “Difference Account”. The Desk JS fetches the helper and assigns this field. Server validation does not perform that Opening Stock lookup automatically; when the field is empty it defaults to the company stock adjustment account, which can then fail opening validation. See [get_difference_account](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/erpnext/erpnext/stock/doctype/stock_reconciliation/stock_reconciliation.py:1556), [schema](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/erpnext/erpnext/stock/doctype/stock_reconciliation/stock_reconciliation.json:108), [Desk assignment](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/erpnext/erpnext/stock/doctype/stock_reconciliation/stock_reconciliation.js:249), [server default](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/erpnext/erpnext/stock/doctype/stock_reconciliation/stock_reconciliation.py:67).

```python
reconciliation = frappe.get_doc({
    "doctype": "Stock Reconciliation", "company": company,
    "purpose": "Opening Stock", "expense_account": opening_account,
    "cost_center": cost_center, "posting_date": posting_date,
    "posting_time": posting_time, "set_posting_time": 1,
    "items": [{
        "item_code": item_code, "warehouse": warehouse,
        "qty": counted_quantity, "valuation_rate": unit_inventory_cost,
        "allow_zero_valuation_rate": int(unit_inventory_cost == 0),
    }],
})
reconciliation.insert()
reconciliation.submit()
```

`qty` is the target count, not an incoming increment. Non-batch SLE construction sets `qty_after_transaction` from the row. For serialized stock, core removes the applicable current bundle and adds the target bundle. Opening GL derives `is_opening="Yes"` from `purpose`; Stock Reconciliation does not need a separate `is_opening` payload field. See [get_sle_for_items](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/erpnext/erpnext/stock/doctype/stock_reconciliation/stock_reconciliation.py:906), [opening GL derivation](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/erpnext/erpnext/controllers/stock_controller.py:992).

With perpetual inventory, opening purpose, or a completely empty Stock Ledger Entry table, rejects a P&L `expense_account`. The empty-ledger check is global, not company-filtered. Choose a company-specific non-group balance-sheet opening account. `cost_center` is required when producing stock GL. See [validate_expense_account](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/erpnext/erpnext/stock/doctype/stock_reconciliation/stock_reconciliation.py:1045).

For serial/batch opening rows, use `serial_and_batch_bundle` with Inward target entries or `use_serial_batch_fields=1` plus explicit `serial_no`/`batch_no`. Do not send a serialized row with neither a bundle nor legacy/reconcile-all mode. `reconcile_all_serial_batch` changes the scope to all applicable serial/batch stock; it is not an ordinary additive restock flag. Customer-provided reconciliation forces nonzero valuation to zero. See [current bundle guard](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/erpnext/erpnext/stock/doctype/stock_reconciliation/stock_reconciliation.py:172), [set_new_serial_and_batch_bundle](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/erpnext/erpnext/stock/doctype/stock_reconciliation/stock_reconciliation.py:453), [customer-provided valuation](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/erpnext/erpnext/stock/doctype/stock_reconciliation/stock_reconciliation.py:1068).

Source-review finding in current app: `products.set_stock` selects `Opening Stock` for an empty ledger but omits `expense_account`, so it can default to a P&L adjustment account and fail. It also excludes serialized/customer-provided/third-party stock and rejects count correction while that product has pending POS sales. No fix was made. See [products.py:66-108](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/moniepoint_pos/moniepoint_pos/products.py:66).

## Purchase Invoice intake and payment

For ordinary supplier-owned purchases becoming shop inventory, one stock-updating Purchase Invoice can receive stock and incur the payable:

```python
invoice = frappe.get_doc({
    "doctype": "Purchase Invoice", "company": company,
    "supplier": supplier, "credit_to": supplier_payable_account,
    "currency": "NGN", "conversion_rate": 1,
    "posting_date": posting_date, "posting_time": posting_time,
    "set_posting_time": 1, "due_date": due_date,
    "update_stock": 1, "is_paid": 0, "is_opening": "No",
    "cost_center": cost_center,
    "items": [{
        "item_code": item_code, "item_name": item_name,
        "description": description, "qty": quantity, "rate": unit_purchase_price,
        "uom": stock_uom, "stock_uom": stock_uom, "conversion_factor": 1,
        "warehouse": warehouse, "expense_account": purchase_expense_account,
        "cost_center": cost_center,
        # For explicit serial intake, alternatively attach an Inward bundle:
        "use_serial_batch_fields": 1, "serial_no": "\n".join(serial_numbers),
    }],
})
invoice.insert()
invoice.submit()
```

Omit serial fields for untracked items. Example assumes NGN document/company/accounts; use actual currency/rates otherwise. Schema fields are verified in [Purchase Invoice schema](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/erpnext/erpnext/accounts/doctype/purchase_invoice/purchase_invoice.json:1), [Purchase Invoice Item schema](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/erpnext/erpnext/accounts/doctype/purchase_invoice_item/purchase_invoice_item.json:1).

Submission processes return/legacy bundles and stock ledger before GL. Supplier GL credits `credit_to` with `party_type="Supplier"`, `party=supplier`. The item/stock entries follow perpetual-inventory configuration. A child `purchase_receipt` link is a hard blocker to `update_stock=1`, since the receipt already received the stock. If buying settings require PO/PR, ordinary invoice validation still applies. See [PurchaseInvoice.validate](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/erpnext/erpnext/accounts/doctype/purchase_invoice/purchase_invoice.py:270), [stock-update guard and submit](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/erpnext/erpnext/accounts/doctype/purchase_invoice/purchase_invoice.py:801), [supplier GL](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/erpnext/erpnext/accounts/doctype/purchase_invoice/purchase_invoice.py:979).

Two distinct payment routes are supported:

- Separate Payment Entry: leave `is_paid=0`, submit the invoice, then use the Payment Entry helper below. This gives a named payment record and supports partial payments.
- Inline paid Purchase Invoice: set header `is_paid=1`, `cash_bank_account=<Account name>`, `paid_amount=<amount>`, optionally `mode_of_payment`. Core adds supplier debit and cash/bank credit to the **Purchase Invoice's GL**, not a separate Payment Entry document. `base_paid_amount` is calculated. Never also post a Payment Entry for the same inline paid amount.

`cash_bank_account` is mandatory when `is_paid=1`; paid amount plus write-off cannot exceed the invoice total. A zero paid amount on a paid invoice can auto-fill from outstanding, so use `is_paid=0` to mean unpaid. See [calculate_paid_amount](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/erpnext/erpnext/controllers/accounts_controller.py:827), [validate_cash](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/erpnext/erpnext/accounts/doctype/purchase_invoice/purchase_invoice.py:378), [make_payment_gl_entries](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/erpnext/erpnext/accounts/doctype/purchase_invoice/purchase_invoice.py:1667).

## Payment Entry for Supplier and Customer

Whitelisted helper and exact signature:

```python
from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry

get_payment_entry(
    dt, dn, party_amount=None, bank_account=None, bank_amount=None,
    party_type=None, payment_type=None, reference_date=None,
    created_from_payment_request=False,
)
```

The helper checks create/read permissions and returns an **unsaved** Payment Entry. It derives Supplier from Purchase Invoice/Order and Customer from Sales Invoice/Order/Dunning. Positive Purchase Invoice outstanding defaults to Pay; positive Sales Invoice outstanding defaults to Receive. Negative invoice outstanding flips the direction. `bank_account` here means a ledger **Account** name, not a Bank Account DocType name. `reference_date` does not set `posting_date`, which defaults to today. See [get_payment_entry](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/erpnext/erpnext/accounts/doctype/payment_entry/payment_entry.py:2898), [party/payment/amount helpers](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/erpnext/erpnext/accounts/doctype/payment_entry/payment_entry.py:3252).

```python
payment = get_payment_entry(
    dt="Purchase Invoice", dn=purchase_invoice_name,
    bank_account=bank_or_cash_ledger, reference_date=payment_date,
)
payment.posting_date = payment_date
payment.reference_no = transaction_reference
payment.mode_of_payment = mode_of_payment
payment.paid_amount = payment.received_amount = amount  # same-currency case
# Ordinary single-reference case. For payment-term invoices keep term rows
# and distribute the amount over the intended terms instead.
payment.references[0].allocated_amount = amount
payment.set_amounts()
payment.insert()
payment.submit()
```

Use `dt="Sales Invoice"` for customer collection. `paid_from` is the customer receivable and `paid_to` cash/bank for Receive; `paid_from` is cash/bank and `paid_to` supplier payable for Pay. The helper derives these. Bank transactions require both `reference_no` and `reference_date`. `paid_amount`, `received_amount`, and both exchange rates must be nonzero; submission requires `difference_amount=0`. See [party-account setup](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/erpnext/erpnext/accounts/doctype/payment_entry/payment_entry.py:158), [mandatory fields](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/erpnext/erpnext/accounts/doctype/payment_entry/payment_entry.py:671), [bank reference validation](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/erpnext/erpnext/accounts/doctype/payment_entry/payment_entry.py:1248), [submit](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/erpnext/erpnext/accounts/doctype/payment_entry/payment_entry.py:204).

Important helper behavior:

- `party_amount`, when truthy, replaces both helper grand total and helper outstanding. Prefer deriving the actual invoice then changing payment/allocation amounts, rather than treating this as an innocent partial-payment flag.
- `bank_amount` only influences cross-currency calculation; same-currency calculation uses absolute outstanding regardless of this kwarg.
- The invoice's existing `mode_of_payment` can override the passed `bank_account` through `get_default_bank_cash_account`. Check the returned accounts before saving. Set explicit accounts when the workflow mandates a particular ledger.
- Payment terms can generate several references. Normal validation refreshes reference details and checks current outstanding and term allocation, not stale browser amounts. Supplier hold restrictions remain enforced.

Sources: [amount calculation](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/erpnext/erpnext/accounts/doctype/payment_entry/payment_entry.py:3311), [mode-of-payment account selection](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/erpnext/erpnext/accounts/doctype/journal_entry/journal_entry.py:1354), [term references](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/erpnext/erpnext/accounts/doctype/payment_entry/payment_entry.py:2992), [latest allocation validation](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/erpnext/erpnext/accounts/doctype/payment_entry/payment_entry.py:428), [supplier hold check](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/erpnext/erpnext/accounts/doctype/payment_entry/payment_entry.py:2327).

Customer valid references are Sales Order, Sales Invoice, Journal Entry, Dunning, Payment Entry. Supplier valid references are Purchase Order, Purchase Invoice, Journal Entry, Payment Entry. **POS Invoice is not accepted.** A submitted reference must belong to the party and use the matching party account; Journal Entry has its own matching checks. See [validate_reference_documents/get_valid_reference_doctypes](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/erpnext/erpnext/accounts/doctype/payment_entry/payment_entry.py:676).

For original POS customer debts, wait for or perform the appropriate consolidation workflow, then reference `POS Invoice.consolidated_invoice`. Preserve the original POS-to-payment allocation in app-owned data if several original sales share a consolidated receivable. The consolidated account can settle accounting outstanding but cannot identify which original receipt a partial payment covered by itself. This is an implementation inference from the consolidation mapping and Payment Entry's invoice-level references.

For on-account Supplier/Customer money without an invoice, create Payment Entry directly with `company`, `payment_type`, `party_type`, `party`, `paid_from`, `paid_to`, `paid_amount`, `received_amount`, dates and bank reference. Empty `references` means unallocated money, not a matched invoice settlement. Company advance-account settings can change the account treatment. Do not call `get_payment_entry(dt="Supplier", ...)` or `dt="Customer"` as if these masters were invoice sources. See [set_party_type](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/erpnext/erpnext/accounts/doctype/payment_entry/payment_entry.py:3273), [set_missing_values](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/erpnext/erpnext/accounts/doctype/payment_entry/payment_entry.py:532), [advance liability-account treatment](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/erpnext/erpnext/accounts/doctype/payment_entry/payment_entry.py:238).

## Returns from POS Invoice and Sales Invoice

Matching whitelisted wrappers:

```python
from erpnext.accounts.doctype.pos_invoice.pos_invoice import make_sales_return as make_pos_return
from erpnext.accounts.doctype.sales_invoice.sales_invoice import make_sales_return as make_si_return

return_doc = make_pos_return(source_name=original_pos_invoice, target_doc=None)
# Or, for an ordinary non-consolidated Sales Invoice:
return_doc = make_si_return(source_name=original_sales_invoice, target_doc=None)
```

Both call `erpnext.controllers.sales_and_purchase_return.make_return_doc(doctype, source_name, target_doc=None, return_against_rejected_qty=False)`. They map a submitted source to an unsaved same-DocType return. Core sets `is_return=1`, `return_against=source.name`, negative quantities, original rates, and return child references. POS child `pos_invoice_item` identifies the original POS Invoice Item; SI child `sales_invoice_item` identifies the original Sales Invoice Item. See [POS wrapper](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/erpnext/erpnext/accounts/doctype/pos_invoice/pos_invoice.py:1036), [SI wrapper](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/erpnext/erpnext/accounts/doctype/sales_invoice/sales_invoice.py:2556), [mapper](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/erpnext/erpnext/controllers/sales_and_purchase_return.py:446), [sales child mapping](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/erpnext/erpnext/controllers/sales_and_purchase_return.py:629).

The mapper rejects a Sales Invoice with both `is_consolidated=1` and `is_pos=1`. Return its **original POS Invoice**, even after consolidation. The merge flow creates a consolidated credit note against the correct original consolidated SI. Original sales must already be consolidated or be included with their returns in the same merge. See [consolidated SI return prohibition](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/erpnext/erpnext/controllers/sales_and_purchase_return.py:454), [merge return guard](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/erpnext/erpnext/accounts/doctype/pos_invoice_merge_log/pos_invoice_merge_log.py:78), [return grouping](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/erpnext/erpnext/accounts/doctype/pos_invoice_merge_log/pos_invoice_merge_log.py:188).

For partial returns, keep only intended rows, set their negative quantities, preserve the source-row IDs and recalculate totals. Mapping takes account of quantities already returned, but the caller must select the actual requested amount. Core enforces original company/submitted reference, date/time not earlier than the sale, matching conversion rate, return quantity limits and original-row/rate constraints. SI cannot enable `update_stock` if its source did not update stock. See [return validation](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/erpnext/erpnext/controllers/sales_and_purchase_return.py:22), [quantity limits](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/erpnext/erpnext/controllers/sales_and_purchase_return.py:189), [already-returned row grouping](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/erpnext/erpnext/controllers/sales_and_purchase_return.py:296).

The mapper initially negates original payment rows and paid amounts. Those amounts are not automatically a correct partial refund or the correct refund tender. Replace them with the actual refund amounts/tender and recalculate; POS returns reject positive payment amounts and excessive refunds. Do not both retain an inline POS refund and issue a second Customer Payment Entry for the same cash movement. See [mapped payments](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/erpnext/erpnext/controllers/sales_and_purchase_return.py:495), [POS return payment validation](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/erpnext/erpnext/accounts/doctype/pos_invoice/pos_invoice.py:557).

A non-POS SI credit note can be refunded via Customer Pay Payment Entry. Use the invoice that actually holds negative outstanding. SI customer GL sets `against_voucher=return_against` when `is_return=1`, `return_against` exists and `update_outstanding_for_self=0`; otherwise it uses the SI's own name. Do not assume the credit note itself has refundable outstanding. Payment amounts are positive but allocated invoice credit amounts retain their negative sign. See [SI customer outstanding routing](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/erpnext/erpnext/accounts/doctype/sales_invoice/sales_invoice.py:1661), [payment direction](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/erpnext/erpnext/accounts/doctype/payment_entry/payment_entry.py:3299), [negative invoice refund GL](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/erpnext/erpnext/accounts/doctype/payment_entry/payment_entry.py:1385).

For serialized returns, do not reuse the original Outward bundle as the return bundle. Core's missing-bundle return path uses original-row references to derive an Inward bundle at submission. Its default selection takes a subset of available original serials by quantity; that does not establish which physical unit the operator chose. For specific returned serials, attach a new explicit Inward bundle with the selected serial list and original return-row relationship, and preserve `pos_invoice_item`/`sales_invoice_item`. Validate source membership and already-returned identities in the workflow. See [return reference eligibility](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/erpnext/erpnext/controllers/stock_controller.py:593), [core return bundle creation](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/erpnext/erpnext/controllers/stock_controller.py:550), [serial subset selection](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/erpnext/erpnext/controllers/sales_and_purchase_return.py:1164), [make_serial_batch_bundle_for_return](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/erpnext/erpnext/controllers/sales_and_purchase_return.py:1247).

## POS consolidation links and event timing

Verified sequence:

```text
Original POS Invoice.submit()
  -> POS controller on_submit: status, return/legacy bundles, bundle submit
  -> POS Invoice app on_submit handlers

POS Closing Entry controller on_submit
  -> consolidate_pos_invoices(closing_entry=self)
  -> merge log save + submit, immediately or in background
     -> POS Invoice Merge Log controller on_submit
        -> map sales into a Sales Invoice
           -> each SI item gets pos_invoice + pos_invoice_item
           -> is_consolidated=1, save, submit
              -> SI controller on_submit: stock ledger then GL
              -> Sales Invoice app on_submit handlers
        -> create and submit consolidated return credit notes
        -> save merge log consolidated invoice references
        -> reload original POS invoices
        -> set consolidated_invoice, status, save originals
     -> POS Invoice Merge Log app on_submit handlers
```

Sources: [POS on_submit](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/erpnext/erpnext/accounts/doctype/pos_invoice/pos_invoice.py:240), [closing on_submit](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/erpnext/erpnext/accounts/doctype/pos_closing_entry/pos_closing_entry.py:209), [merge on_submit](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/erpnext/erpnext/accounts/doctype/pos_invoice_merge_log/pos_invoice_merge_log.py:116), [SI creation/submission](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/erpnext/erpnext/accounts/doctype/pos_invoice_merge_log/pos_invoice_merge_log.py:143), [item links](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/erpnext/erpnext/accounts/doctype/pos_invoice_merge_log/pos_invoice_merge_log.py:234), [original link update](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/erpnext/erpnext/accounts/doctype/pos_invoice_merge_log/pos_invoice_merge_log.py:376).

Consequences:

- In consolidated SI `before_submit` or `on_submit`, the SI's own child `pos_invoice` and `pos_invoice_item` fields already exist. The reverse `POS Invoice.consolidated_invoice` links are not yet updated. Do not query originals by their new header link at that event.
- There is one mapped SI item per original POS item, even for repeated item codes. Payment rows are combined by account plus mode of payment. Derive ownership/cost from original child identity, not item code or combined tender totals.
- Updating an original submitted POS Invoice during consolidation invokes update-after-submit events, not a second POS `on_submit`. An accrual tied only to original submission will not naturally fire again during that save.
- A merge-log app `on_submit` handler sees completed original header links. A closing-entry app `on_submit` handler might only see Queued state, because ten or more invoices with a closing entry take the background path. It is not a universal consolidation-complete event.

Evidence for mapping/payments is [merge_pos_invoice_into](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/erpnext/erpnext/accounts/doctype/pos_invoice_merge_log/pos_invoice_merge_log.py:207). Event evidence is the Frappe lifecycle above. Queue threshold and return splitting are [consolidate_pos_invoices/split_invoices](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/erpnext/erpnext/accounts/doctype/pos_invoice_merge_log/pos_invoice_merge_log.py:521). Grouping is by customer and accounting dimensions/cost center/project, not an owner-supplier field. See [get_invoice_customer_map](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/erpnext/erpnext/accounts/doctype/pos_invoice_merge_log/pos_invoice_merge_log.py:485).

The native POS controller submits bundles but does not run stock ledger or GL posting there. Stock/GL posting occurs through the consolidated SI, while app availability accounts for pending POS quantities. Do not add a second stock issue at POS submit. Another core route immediately creates a consolidated return SI when `POS Settings.invoice_type == "Sales Invoice"`; that SI also has original POS child links and must not incur a duplicate owner cost. See [POS on_submit](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/erpnext/erpnext/accounts/doctype/pos_invoice/pos_invoice.py:240), [immediate return SI route](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/erpnext/erpnext/accounts/doctype/pos_invoice/pos_invoice.py:311), [SI stock/GL order](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/erpnext/erpnext/accounts/doctype/sales_invoice/sales_invoice.py:493), [app pending counts](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/moniepoint_pos/moniepoint_pos/products.py:33).

Serial/batch bundles can be relinked to the SI voucher and SI item during consolidation. Do not use the bundle's current `voucher_no` as the permanent original-sale ID. Use explicit POS item links and stored sale identities. See [bundle parent reassignment](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/erpnext/erpnext/stock/doctype/serial_and_batch_bundle/serial_and_batch_bundle.py:951).

`create_merge_logs` rolls back on exception, records failure on a closing entry, then commits in `finally` and publishes `closing_process_complete`. Its top-level consolidation function is not whitelisted. Calling it inside a custom transaction is not equivalent to a commit-free atomic helper. See [create_merge_logs transaction handling](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/erpnext/erpnext/accounts/doctype/pos_invoice_merge_log/pos_invoice_merge_log.py:602), [enqueue_job](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/erpnext/erpnext/accounts/doctype/pos_invoice_merge_log/pos_invoice_merge_log.py:682).

The selected integration creates and submits `POS Invoice Merge Log` directly, using its validated document payload, rather than calling `consolidate_pos_invoices` / `create_merge_logs` inside the workflow transaction:

```python
merge_log = frappe.get_doc(validated_merge_log_payload)
merge_log.insert()
merge_log.submit()
```

This invokes the Merge Log controller sequence above without entering the wrapper's internal commit path. The custom endpoint must enforce source selection, grouping, permissions and concurrency itself. Downstream app hooks still need call review for transaction behavior. Normal Frappe request commit remains at the outer boundary. Direct submission also does not invoke the wrapper's closing-status/event code. See [Merge Log on_submit](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/erpnext/erpnext/accounts/doctype/pos_invoice_merge_log/pos_invoice_merge_log.py:116), [Frappe request transaction handling](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/frappe/frappe/app.py:458).

## Customer-provided zero-value consignment stock

**Source finding: `is_customer_provided_item=1` does not itself prohibit selling through POS Invoice or Sales Invoice.** Item validation prohibits `is_purchase_item=1` and nonzero Item `valuation_rate`, then sets `default_material_request_type="Customer Provided"`. It does not clear `is_sales_item` or reject selling. Selling validation checks `is_sales_item`; POS discovery filters active sale-enabled, non-template, non-fixed-asset Items without excluding customer-provided Items. Stock validation sets sale-row `allow_zero_valuation_rate=1`. See [Item.validate_customer_provided_part](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/erpnext/erpnext/stock/doctype/item/item.py:271), [SellingController.validate_items](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/erpnext/erpnext/controllers/selling_controller.py:881), [POS discovery](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/erpnext/erpnext/selling/page/point_of_sale/point_of_sale.py:191), [StockController.validate_customer_provided_item](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/erpnext/erpnext/controllers/stock_controller.py:1722).

Core Item fields for this approach:

```python
{
    "is_stock_item": 1,
    "is_sales_item": 1,
    "is_purchase_item": 0,
    "is_customer_provided_item": 1,
    "valuation_rate": 0,
    "stock_uom": "Nos",
    # has_serial_no / has_batch_no according to the real identity model
}
```

Use Stock Entry Material Receipt with zero `basic_rate`, no capitalized owner-payout amount, and proper serial intake. The Item schema explicitly describes this flag as customer-provided stock received via Stock Entry. Normal Purchase Invoice buying validation requires `is_purchase_item`, so it conflicts with these customer-provided Item fields. See [Item field description](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/erpnext/erpnext/stock/doctype/item/item.json:642), [buying validation](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/erpnext/erpnext/controllers/buying_controller.py:1297).

This is an API-compatible use of the flag, not a built-in consignment ownership/liability system. It does not establish owner identity, payout terms, ownership transfer, tax policy or commission-only revenue treatment. `Item.customer_items` is not an owner payable field; Frappe document `owner` means the user who created the document. Use app-owned supplier/ownership and frozen payout terms, not those fields. The distinction follows from the Item schema and Journal Entry party fields, not from any site data.

Zero Item `valuation_rate` is not proof that existing inventory layers are zero. The stock controller only enables zero valuation; it does not rewrite historical ledger cost. Do not mix shop-owned valued stock and zero-value consigned stock under one untracked identity. Existing supplier/customer restrictions, stock availability, POS profile/opening, serial settings and account validations still apply. Relevant guards are [stock valuation](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/erpnext/erpnext/stock/doctype/stock_entry/stock_entry.py:1527), [party restrictions](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/erpnext/erpnext/controllers/accounts_controller.py:2544), [POS validation chain](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/erpnext/erpnext/accounts/doctype/pos_invoice/pos_invoice.py:199).

Current app blockers, all observed in source:

- `shop_setup.validate_sale` rejects `Sister Owned` and `Third-party Owner` products on ordinary POS sale submission. Remove/replace this guard only when the payout implementation exists.
- `products.set_stock` excludes these ownership values and customer-provided Items. The new consignment intake workflow must not use it.
- `products.add_configuration` creates `is_purchase_item=1` and shop-owned configurations. Do not reuse that creation payload unchanged for consigned items.

Sources: [sale ownership guard](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/moniepoint_pos/moniepoint_pos/shop_setup.py:136), [stock correction guard](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/moniepoint_pos/moniepoint_pos/products.py:66), [configuration creation](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/moniepoint_pos/moniepoint_pos/products.py:148).

## Journal Entry accrual, expenses and owner payout

For the proposed sale-triggered owner obligation, use an ordinary Journal Entry. Example assumes NGN company and account currencies:

```python
accrual = frappe.get_doc({
    "doctype": "Journal Entry", "voucher_type": "Journal Entry",
    "company": company, "posting_date": sale_posting_date,
    "is_opening": "No", "multi_currency": 0,
    "user_remark": sale_reference_text,
    "accounts": [
        {
            "account": consignment_cost_account,
            "debit_in_account_currency": owner_cost_amount,
            "credit_in_account_currency": 0,
            "cost_center": cost_center,
        },
        {
            "account": owner_payable_account,
            "party_type": "Supplier", "party": owner_supplier,
            "debit_in_account_currency": 0,
            "credit_in_account_currency": owner_cost_amount,
            "cost_center": cost_center,
            "reference_type": "", "reference_name": "",
            "is_advance": "No",
        },
    ],
})
accrual.insert()
accrual.submit()
```

Use `debit_in_account_currency` / `credit_in_account_currency`, not just `debit` / `credit`. JE validation recalculates company-currency debit/credit from those input fields and exchange rates. Rows cannot have both sides, cannot have both sides zero, and total debit must equal credit. `account_currency` is derived from Account; foreign accounts require `multi_currency=1` and appropriate rates. The cost account must be a suitable P&L expense account; the owner ledger must have account type `Payable` with Supplier party fields. A plain Liability account without Payable type will not produce the Supplier payment-ledger outstanding required for settlement. See [JE validation](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/erpnext/erpnext/accounts/doctype/journal_entry/journal_entry.py:128), [party validation](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/erpnext/erpnext/accounts/doctype/journal_entry/journal_entry.py:597), [amount validation/conversion](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/erpnext/erpnext/accounts/doctype/journal_entry/journal_entry.py:942), [payment-ledger account selection](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/erpnext/erpnext/accounts/utils.py:1991).

Keep original sale/line/allocation IDs in separate app fields or records. JE Account `reference_type` does not include POS Invoice. Setting its payable row to `reference_type="Sales Invoice"` is also wrong for a Supplier obligation and prevents the unmatched-JE payout validation from finding it. Leave accrual reference fields empty. `user_remark` is useful human context, not an idempotency key. See [JE Account reference options](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/erpnext/erpnext/accounts/doctype/journal_entry_account/journal_entry_account.json:183), [PaymentEntry.validate_journal_entry](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/erpnext/erpnext/accounts/doctype/payment_entry/payment_entry.py:779).

For another supplier expense, the same debit-expense/credit-Supplier-Payable pattern applies. For an actual immediate expense payment without supplier debt, debit expense and credit cash/bank in a balanced JE. Do not post both that immediate payment credit and a second Supplier Payment Entry. JE does not receive stock. Core also restricts direct adjustments to Stock accounts in perpetual inventory. See [JE GL map](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/erpnext/erpnext/accounts/doctype/journal_entry/journal_entry.py:1152), [stock account guard](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/erpnext/erpnext/accounts/doctype/journal_entry/journal_entry.py:360).

### Pay an accrued owner liability

Create Payment Entry directly for a JE obligation, rather than using `get_payment_entry(dt="Journal Entry", ...)`. That invoice helper derives party from header fields; a JE stores the Supplier on account rows and the helper has no JE-specific party extraction. Use the verified reference-details helper:

```python
from erpnext.accounts.doctype.payment_entry.payment_entry import get_reference_details

details = get_reference_details(
    reference_doctype="Journal Entry", reference_name=accrual.name,
    party_account_currency="NGN", party_type="Supplier", party=owner_supplier,
)
payout = frappe.get_doc({
    "doctype": "Payment Entry", "company": company,
    "payment_type": "Pay", "party_type": "Supplier", "party": owner_supplier,
    "posting_date": payment_date, "reference_date": payment_date,
    "reference_no": transaction_reference, "mode_of_payment": mode_of_payment,
    "paid_from": bank_or_cash_ledger, "paid_to": owner_payable_account,
    "paid_amount": payment_amount, "received_amount": payment_amount,
    "source_exchange_rate": 1, "target_exchange_rate": 1,
    "cost_center": cost_center,
    "references": [{
        "reference_doctype": "Journal Entry", "reference_name": accrual.name,
        "total_amount": details.total_amount,
        "outstanding_amount": details.outstanding_amount,
        "allocated_amount": payment_amount,
    }],
})
payout.insert()
payout.submit()
```

The helper checks reference read permission and gets JE total/outstanding from Payment Ledger Entry for that party. Payment validation refreshes details. Pay against JE requires a submitted **credit** row for the same payable account and party with reference type empty or an allowed order type. Customer Receive against JE instead requires an unmatched debit row. See [get_reference_details](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/erpnext/erpnext/accounts/doctype/payment_entry/payment_entry.py:2808), [JE outstanding](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/erpnext/erpnext/accounts/doctype/payment_entry/payment_entry.py:2775), [JE payment matching](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/erpnext/erpnext/accounts/doctype/payment_entry/payment_entry.py:779).

Payout entries debit the Supplier liability and credit bank/cash. Do not debit the consignment expense again. Preserve allocation per accrual/owner. Using one JE per owner avoids ambiguous party aggregation; `get_outstanding_on_journal_entry` groups by JE and party, not account, so avoid mixing several payable accounts for one owner in a single JE. See [payment GL](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/erpnext/erpnext/accounts/doctype/payment_entry/payment_entry.py:1350), [JE outstanding query](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/erpnext/erpnext/accounts/doctype/payment_entry/payment_entry.py:2775).

## Allocate owner costs once across POS and SI

Recommended implementation for the requested original-sale accrual plan, not an existing core feature:

1. Freeze owner Supplier, payout terms, cost basis, unit payout and selected serial identities on the **original** POS or ordinary SI line before submission. Do not derive past obligations from today's mutable Item price/cost.
2. Accrue in app `POS Invoice.on_submit`, and in `Sales Invoice.on_submit` **only when not `is_consolidated`**. Use one deterministic allocation identity per original source line and owner, with a persistent uniqueness/concurrency guard. Submit the JE and save allocation links in the same transaction.
3. Consolidation must not incur another cost. If it needs display/reporting snapshots, resolve each SI item's `pos_invoice` / `pos_invoice_item`. Do not depend on the yet-unset reverse header link. Also skip the immediate consolidated return SI route.
4. A return is its own source event. Use the original sale-line reference to reverse the frozen unit obligation for returned quantity/serials, not the current Item terms or a fresh positive accrual.
5. Payment settles the existing JE allocation. Cancellation of a Payment Entry restores the liability; it must not cancel the original cost. Cancellation of an original sale reverses the applicable accrual, with a guard against repeating a return reversal.

This follows from the Frappe event order, core links and payment GL above. Core has no owner-payout-on-POS field or automatic once-only owner cost allocation in the inspected paths. An ordinary JE remark or “find existing JE then insert” alone is not a concurrency-safe allocation guard. The guard must be backed by a unique persistent identity or locked source record.

Existing cost snapshot code is already designed to skip consolidated SI and preserve original return-line costs. Its custom child fields have `no_copy=1` on both POS Invoice Item and Sales Invoice Item, so **core consolidation does not copy those snapshots automatically**. Current `product_profit` intentionally counts all original submitted POS lines plus non-consolidated SI lines and excludes consolidated SI. Any owner-cost extension should preserve that reporting identity or explicitly reconstruct consolidated snapshots. See [snapshot_sale_costs](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/moniepoint_pos/moniepoint_pos/pricing.py:145), [custom no-copy fields](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/moniepoint_pos/moniepoint_pos/products.py:204), [Frappe mapper no-copy handling](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/frappe/frappe/model/mapper.py:189), [product_profit](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/moniepoint_pos/moniepoint_pos/pricing.py:178).

Posting owner expense immediately at original POS submission means P&L expense can precede consolidated sales revenue within an open till period. That is a timing consequence of this plan, not a duplicate-cost defect. Current P&L reporting already identifies unconsolidated sales. Preserve that distinction in reporting; do not “fix” it with a second expense at consolidation. See [POS vs SI submit methods](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/erpnext/erpnext/accounts/doctype/pos_invoice/pos_invoice.py:240), [current profit period handling](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/moniepoint_pos/moniepoint_pos/pricing.py:117).

### Cancellation and returns of owner obligations

Two different native operations exist:

```python
# Cancel the actual submitted accrual, if cancellation is valid:
frappe.get_doc("Journal Entry", accrual_name).cancel()

# Or create a separate reversing JE draft:
from erpnext.accounts.doctype.journal_entry.journal_entry import make_reverse_journal_entry
reverse = make_reverse_journal_entry(source_name=accrual_name, target_doc=None)
reverse.posting_date = reversal_date
reverse.insert()
reverse.submit()
```

JE cancellation reverses its GL. `make_reverse_journal_entry` maps debit/credit and account-currency amounts to opposite sides, sets `reversal_of=source.name`, requires a submitted source and read permission, and rejects reversing a reverse or creating a second submitted reversal. It returns a draft, not a posted reversal. Do not both cancel and reverse the same obligation. See [JournalEntry.on_cancel](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/erpnext/erpnext/accounts/doctype/journal_entry/journal_entry.py:296), [make_reverse_journal_entry](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/erpnext/erpnext/accounts/doctype/journal_entry/journal_entry.py:1802).

The full-reversal helper is not an automatic partial-return allocation API. For partial returns, build a balanced JE for only that allocation's amount. To reduce the original unpaid accrual's outstanding, the reversing Supplier debit row can use `reference_type="Journal Entry"`, `reference_name=original_accrual`, while the expense credit stays unreferenced. `reversal_of` alone is provenance and does not populate the JE Account reference fields. Core uses those child reference fields for payment-ledger attribution. Validate original unmatched rows and current allocations before reversal. See [JE-to-JE validation](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/erpnext/erpnext/accounts/doctype/journal_entry/journal_entry.py:692), [JE GL reference mapping](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/erpnext/erpnext/accounts/doctype/journal_entry/journal_entry.py:1187), [payment-ledger fallback](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/erpnext/erpnext/accounts/utils.py:2031).

If the owner was already paid, reversing the expense/liability does **not** recover cash. Record the owner recovery/offset and its allocation separately; do not pretend that cancelling a sale reverses a completed payout. Core JE cancellation may be blocked by links or may unlink payments when the configured cancellation setting permits it. This task did not inspect that setting. Preserve payment history and prevent reversals exceeding unreturned frozen allocations. See [AccountsController.on_cancel](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/erpnext/erpnext/controllers/accounts_controller.py:2103).

A consolidated original POS Invoice cannot be cancelled while its linked SI remains submitted. Core instructs cancellation of the POS Closing Entry first. Unconsolidation cancels linked SIs and clears original links but does not itself cancel original POS invoices. Therefore a cost accrued on original POS submission must remain on unconsolidation alone and reverse only on the actual original sale/return event. A consolidated SI `on_cancel` handler must not reverse an original POS accrual merely because closing is reopened. See [POS before_cancel](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/erpnext/erpnext/accounts/doctype/pos_invoice/pos_invoice.py:266), [merge on_cancel](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/erpnext/erpnext/accounts/doctype/pos_invoice_merge_log/pos_invoice_merge_log.py:135), [original link clearing](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/erpnext/erpnext/accounts/doctype/pos_invoice_merge_log/pos_invoice_merge_log.py:376).

Keep generated accrual JEs small if they must post synchronously in a sale event. The installed JE controller queues submission when it has more than 100 account rows and metadata does not already select background queuing. See [JournalEntry.submit](/Users/joshua/Documents/ChatGPT/erpnext-dev/bench/apps/erpnext/erpnext/accounts/doctype/journal_entry/journal_entry.py:186).

## Remaining implementation inputs

The source establishes the API shapes. It cannot establish company account names, account types/currencies, perpetual-inventory and advance-account settings, POS invoice mode, serial/batch activation/naming, Supplier hold status, live custom-field installation or workbook-specific owner terms without prohibited site/client-data reads. Implementation needs those inputs explicitly, including whether payout is due on sale or customer collection, which costs reduce owner proceeds, and the paid-owner recovery policy.

No source changes or operational validation were made. The supplied code snippets are workflow guidance to implement with permissions, allocation guards and the relevant existing app hooks intact.
